"""
enforcement_patterns.py — Prompt-Based vs Programmatic Enforcement
===================================================================
This file is a teaching document. It shows the SAME workflow implemented
two ways so you can see exactly why prompt-based ordering fails and what
programmatic enforcement looks like under the hood.

Key exam insight: When the exam asks "what most effectively addresses
a reliability issue where an agent skips a required step," the answer
is ALWAYS a programmatic gate, never enhanced prompts.
"""

import anthropic
import random

client = anthropic.Anthropic()

# ══════════════════════════════════════════════════════════════════
# APPROACH 1: PROMPT-BASED ENFORCEMENT (probabilistic — FAILS 12%)
# ══════════════════════════════════════════════════════════════════

WEAK_SYSTEM_PROMPT = """
You are a customer support agent.

IMPORTANT: Always call get_customer BEFORE calling lookup_order or process_refund.
You must verify the customer's identity before any order operations.
"""
# ↑ This is what Q1 Option B looks like.
# The model "usually" follows it but deviates in ~12% of cases.
# Real-world failure modes:
#   - Customer says "My order #12345 was damaged" → model has order ID, skips get_customer
#   - Customer says "I'm Alice Johnson, order 5501" → model does name lookup (ambiguous!)
#   - Long conversation context → instruction gets "lost in the middle"


STRONGER_PROMPT_WITH_FEW_SHOT = """
You are a customer support agent.

ALWAYS follow this exact sequence:
  Step 1: get_customer (REQUIRED first)
  Step 2: lookup_order or check_policy
  Step 3: process_refund (only after Steps 1 and 2)

EXAMPLES of correct behaviour:

Customer: "My order #5501 was damaged, I need a refund."
Correct: Call get_customer first (even though you have the order ID)
Wrong: Call lookup_order directly

Customer: "I'm Alice Johnson and order ORD-5501 hasn't arrived."
Correct: Call get_customer("Alice Johnson") first
Wrong: Call lookup_order("ORD-5501") directly
"""
# ↑ This is Q1 Option C (few-shot examples).
# Better than WEAK_SYSTEM_PROMPT, but still probabilistic.
# A sophisticated model will still sometimes skip verification when
# the "shortcut" seems obviously correct in context.
# Exam: this is NOT the right answer. It improves but doesn't eliminate bypass.


# ══════════════════════════════════════════════════════════════════
# APPROACH 2: PROGRAMMATIC ENFORCEMENT (deterministic — ZERO bypasses)
# ══════════════════════════════════════════════════════════════════

class EnforcedWorkflow:
    """
    The correct implementation (Q1 Option A).

    The gate is in the RUNTIME. The model prompt can say nothing
    about it — the system physically prevents process_refund from
    executing until verified_customer_id is set.

    There is NO way for the model to bypass this through any
    phrasing, reasoning shortcut, or context manipulation.
    """

    def __init__(self):
        # This state is in the runtime, not in the conversation.
        # Claude cannot see or modify it.
        self._verified_customer_id: str | None = None
        self._policy_checked: bool = False
        self._call_sequence: list[str] = []

    # ── Tool A: get_customer (no prerequisites) ────────────────────
    def call_get_customer(self, identifier: str) -> dict:
        """Step 1: Always allowed."""
        self._call_sequence.append("get_customer")

        # Simulate backend call
        result = {
            "verified_customer_id": f"VER-{identifier}",
            "name": "Alice Johnson",
            "email": "alice@example.com",
        }

        # Update state on success
        self._verified_customer_id = result["verified_customer_id"]
        return result

    # ── Tool B: lookup_order (soft prerequisite) ────────────────────
    def call_lookup_order(self, order_id: str) -> dict:
        """Step 2: Allowed but warns if customer not verified."""
        self._call_sequence.append("lookup_order")

        if not self._verified_customer_id:
            # Read-only operation — soft warning, not hard block
            return {
                "warning": "Customer identity not verified. Verify before financial ops.",
                "order_id": order_id,
                "status": "delivered",
                "total": 149.99,
            }

        return {"order_id": order_id, "status": "delivered", "total": 149.99}

    # ── Tool C: check_policy (no prerequisites) ────────────────────
    def call_check_policy(self, policy_type: str) -> dict:
        """Policy check: always allowed."""
        self._call_sequence.append("check_policy")
        self._policy_checked = True
        return {"eligible": True, "max_refund": 500.0}

    # ── Tool D: process_refund (HARD prerequisites) ─────────────────
    def call_process_refund(self, order_id: str, amount: float, reason: str) -> dict:
        """
        Step 3: BLOCKED until:
          (a) get_customer has been called and returned verified_customer_id
          (b) check_policy has been called
        """
        self._call_sequence.append("process_refund_attempt")

        # ── GATE 1: Identity verification ──────────────────────────
        if not self._verified_customer_id:
            return {
                "blocked": True,
                "error": "GATE BLOCKED: Identity not verified.",
                "required_action": "Call get_customer first.",
                "gate": "identity_verification",
            }

        # ── GATE 2: Policy confirmation ──────────────────────────
        if not self._policy_checked:
            return {
                "blocked": True,
                "error": "GATE BLOCKED: Policy not checked.",
                "required_action": "Call check_policy first.",
                "gate": "policy_confirmation",
            }

        # ── GATE 3: Amount threshold (PostToolUse-style) ───────────
        if amount > 500:
            return {
                "blocked": True,
                "error": f"GATE BLOCKED: Amount ${amount:.2f} exceeds $500 limit.",
                "required_action": "Use escalate_to_human for amounts above $500.",
                "gate": "amount_threshold",
            }

        # All gates passed — execute
        self._call_sequence.append("process_refund_success")
        return {
            "refund_id": f"REF-{order_id}",
            "amount": amount,
            "status": "approved",
            "verified_by": self._verified_customer_id,
        }

    def get_call_sequence(self) -> list[str]:
        return self._call_sequence.copy()


# ══════════════════════════════════════════════════════════════════
# COMPARISON DEMONSTRATION
# ══════════════════════════════════════════════════════════════════

def demonstrate_prompt_failure():
    """
    Simulates how prompt-based enforcement fails probabilistically.
    The model deviates from instructions when context makes the
    "shortcut" seem reasonable.
    """
    print("\n" + "="*70)
    print("DEMONSTRATION: Prompt-Based Enforcement Failure")
    print("="*70)

    # Simulate 10 interactions, random ~12% failure rate
    failures = 0
    for i in range(10):
        # Simulate: did the model follow the prompt instruction?
        followed = random.random() > 0.12   # 88% follow rate

        if not followed:
            failures += 1
            print(f"  Run {i+1:2d}: ❌ SKIPPED get_customer — called lookup_order directly")
        else:
            print(f"  Run {i+1:2d}: ✓  Followed prompt correctly")

    print(f"\nFailure rate: {failures}/10 = {failures*10}%")
    print("With prompt-based enforcement, failures are a statistical certainty")
    print("at scale. 12% of 10,000 daily transactions = 1,200 unverified refunds.")


def demonstrate_programmatic_enforcement():
    """
    Demonstrates that programmatic gates have ZERO failure rate.
    The model cannot bypass them regardless of what it reasons.
    """
    print("\n" + "="*70)
    print("DEMONSTRATION: Programmatic Enforcement (Zero Failures)")
    print("="*70)

    workflow = EnforcedWorkflow()

    # Attempt 1: Try to skip directly to refund (as model might)
    print("\nAttempt 1: Call process_refund without verification...")
    result = workflow.call_process_refund("ORD-5501", 149.99, "damaged")
    print(f"  Result: {result}")
    assert result["blocked"], "Gate must block this"

    # Attempt 2: Verify customer, then try refund without policy
    print("\nAttempt 2: Verify customer, skip policy, try refund...")
    workflow.call_get_customer("C10023")
    result = workflow.call_process_refund("ORD-5501", 149.99, "damaged")
    print(f"  Result: {result}")
    assert result["blocked"], "Gate must still block (policy not checked)"

    # Attempt 3: Complete all prerequisites
    print("\nAttempt 3: Complete all prerequisites in correct order...")
    workflow.call_check_policy("damage_claim")
    result = workflow.call_process_refund("ORD-5501", 149.99, "damaged")
    print(f"  Result: {result}")
    assert not result.get("blocked"), "Should succeed now"

    print(f"\nCall sequence: {workflow.get_call_sequence()}")
    print("✓ Zero bypasses — enforcement is deterministic")


def demonstrate_hook_vs_prompt_for_threshold():
    """
    Shows why a $500 threshold is better enforced by a hook
    than a prompt instruction.
    """
    print("\n" + "="*70)
    print("DEMONSTRATION: Hook vs Prompt for Threshold Enforcement")
    print("="*70)

    # Approach A: Prompt only (fragile)
    weak_prompt_excerpt = """
    Do not process refunds above $500.
    For amounts above $500, use escalate_to_human instead.
    """
    print("\nPrompt-only approach:")
    print("  Instruction:", weak_prompt_excerpt.strip()[:80])
    # Failure modes:
    print("  Failure modes:")
    print("    - 'The customer really needs $750' → model may override its judgement")
    print("    - Long context → instruction gets forgotten")
    print("    - $499.99 × 2 for same order → model may not detect the split")

    # Approach B: Hook (deterministic)
    print("\nHook approach:")
    print("  Code: if inputs['amount'] > 500: return {blocked: True}")
    print("  Result: 100% enforcement, no exceptions possible")

    workflow = EnforcedWorkflow()
    workflow.call_get_customer("C10023")
    workflow.call_check_policy("damage_claim")

    print("\nTesting hook on $750 refund...")
    result = workflow.call_process_refund("ORD-5501", 750.00, "large claim")
    print(f"  Result: {result}")
    assert result["blocked"] and result["gate"] == "amount_threshold"
    print("✓ Hook blocked the over-limit refund deterministically")


# ══════════════════════════════════════════════════════════════════
# EXAM QUESTION WALKTHROUGH
# ══════════════════════════════════════════════════════════════════

def q1_answer_walkthrough():
    """
    Step-by-step explanation of why Q1 Answer is A, not B, C, or D.
    """
    print("\n" + "="*70)
    print("Q1 WALKTHROUGH: Why Each Answer Is Right/Wrong")
    print("="*70)

    reasoning = {
        "A": {
            "text": "Programmatic prerequisite blocking lookup_order and process_refund until get_customer returns verified ID",
            "correct": True,
            "reason": (
                "This is the ONLY approach that guarantees zero bypasses. "
                "The gate lives in the runtime — the model cannot reason around it. "
                "No matter what the customer says or what context exists, "
                "process_refund will not execute until verified_customer_id is set."
            ),
        },
        "B": {
            "text": "Enhance system prompt to state verification is mandatory",
            "correct": False,
            "reason": (
                "This IS the current approach that's failing 12% of the time. "
                "Strengthening the prompt instruction improves compliance but "
                "cannot eliminate bypasses — the model is still making a "
                "probabilistic text prediction. This is not a correct fix for "
                "a critical financial security requirement."
            ),
        },
        "C": {
            "text": "Few-shot examples showing get_customer called first",
            "correct": False,
            "reason": (
                "Few-shot examples improve output format and ambiguous-case handling "
                "(Task 4.2), but they don't create deterministic enforcement. "
                "The model can still deviate when the shortcut seems obviously correct. "
                "Better than Option B but still probabilistic."
            ),
        },
        "D": {
            "text": "Routing classifier that limits tool subset per request type",
            "correct": False,
            "reason": (
                "This addresses tool AVAILABILITY, not tool ORDERING. "
                "Even if you give the agent only {get_customer, lookup_order} for "
                "one request type, it doesn't enforce that get_customer must come "
                "before lookup_order. The root problem is ordering, not access."
            ),
        },
    }

    for letter, info in reasoning.items():
        status = "✅ CORRECT" if info["correct"] else "❌ Wrong"
        print(f"\n{letter}) {status}")
        print(f"   Option: {info['text']}")
        print(f"   Why: {info['reason']}")


if __name__ == "__main__":
    demonstrate_prompt_failure()
    demonstrate_programmatic_enforcement()
    demonstrate_hook_vs_prompt_for_threshold()
    q1_answer_walkthrough()
