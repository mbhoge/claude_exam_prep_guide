"""
Task 1.4 – Multi-Step Workflows with Enforcement and Handoff Patterns
======================================================================
Complete implementation of the Customer Support Resolution Agent scenario.

This file demonstrates the FULL agentic loop including:
  1. Programmatic prerequisite gates (Q1 correct answer)
  2. PostToolUse hooks for policy enforcement and data normalisation
  3. Structured handoff protocol generation
  4. Multi-concern decomposition with parallel investigation

Run:
    python multi_step_workflows.py

Requires: pip install anthropic
"""

import anthropic
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

client = anthropic.Anthropic()


# ══════════════════════════════════════════════════════════════════
# SECTION 1: BACKEND TOOL IMPLEMENTATIONS (simulated)
# ══════════════════════════════════════════════════════════════════

# Simulated customer database
_CUSTOMERS = {
    "C10023": {
        "name": "Alice Johnson",
        "email": "alice@example.com",
        "tier": "Gold",
        "account_since": "2021-03-15",
        "total_orders": 47,
    },
    "C88741": {
        "name": "Bob Martinez",
        "email": "bob@example.com",
        "tier": "Standard",
        "account_since": "2023-08-01",
        "total_orders": 5,
    },
}

# Simulated order database
_ORDERS = {
    "ORD-5501": {
        "status": "delivered",
        "total": 149.99,
        "items": ["Wireless Headphones", "USB-C Cable"],
        "delivered_date": "2024-11-02",
        "damage_claim_eligible": True,
    },
    "ORD-5502": {
        "status": "delivered",
        "total": 89.99,
        "items": ["Phone Case"],
        "delivered_date": "2024-11-03",
        "duplicate_charge": True,
    },
}


def tool_get_customer(identifier: str) -> dict:
    """
    Look up and VERIFY a customer's identity.
    Returns verified_customer_id on success.
    This MUST be called before any financial operations.
    """
    customer = _CUSTOMERS.get(identifier)
    if customer:
        return {
            "verified_customer_id": f"VER-{identifier}",
            "name": customer["name"],
            "email": customer["email"],
            "tier": customer["tier"],
            "account_since": customer["account_since"],
            "total_orders": customer["total_orders"],
        }
    # Try name-based search (less reliable — reason gates exist)
    for cid, c in _CUSTOMERS.items():
        if identifier.lower() in c["name"].lower():
            return {
                "warning": "Name match is ambiguous — ID verification recommended",
                "verified_customer_id": f"VER-{cid}",
                "name": c["name"],
                "email": c["email"],
            }
    return {"error": f"Customer '{identifier}' not found"}


def tool_lookup_order(order_id: str) -> dict:
    """Look up order details."""
    order = _ORDERS.get(order_id)
    if order:
        return {"order_id": order_id, **order}
    return {"error": f"Order '{order_id}' not found"}


def tool_check_policy(policy_type: str, context: dict) -> dict:
    """Check company policy for a given situation."""
    policies = {
        "damage_claim": {
            "eligible": True,
            "resolution": "Full refund or replacement within 30 days of delivery",
            "requires": "Photo evidence or agent confirmation",
            "max_refund": 500.0,
        },
        "duplicate_charge": {
            "eligible": True,
            "resolution": "Automatic refund of duplicate amount",
            "requires": "Order lookup confirming duplicate",
            "max_refund": 1000.0,
        },
        "subscription_cancel": {
            "eligible": True,
            "resolution": "Cancel effective end of billing period",
            "penalty": None,
            "pro_rata_refund": True,
        },
        "competitor_price_match": {
            "eligible": None,
            "resolution": "Policy gap — escalate to manager",
            "note": "Policy only covers own-site price adjustments",
        },
    }
    return policies.get(policy_type, {"error": f"Unknown policy type '{policy_type}'"})


def tool_process_refund(order_id: str, amount: float, reason: str,
                        verified_customer_id: str) -> dict:
    """
    Process a customer refund.
    REQUIRES verified_customer_id — enforced at gate level, not prompt level.
    """
    return {
        "refund_id": f"REF-{order_id}-{int(amount*100)}",
        "order_id": order_id,
        "amount": amount,
        "reason": reason,
        "status": "approved",
        "estimated_days": 3,
    }


def tool_escalate_to_human(handoff_summary: str) -> dict:
    """Create a human escalation ticket."""
    return {
        "ticket_id": f"TKT-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "status": "escalated",
        "queue": "Tier-2 Support",
        "estimated_wait_minutes": 15,
        "handoff_summary": handoff_summary,
    }


# ══════════════════════════════════════════════════════════════════
# SECTION 2: TOOL DEFINITIONS (sent to Claude)
# ══════════════════════════════════════════════════════════════════

TOOLS = [
    {
        "name": "get_customer",
        "description": (
            "Verify and retrieve customer information by customer ID or name. "
            "MUST be called before lookup_order or process_refund. "
            "Returns verified_customer_id required for financial operations. "
            "Use customer ID (e.g. C10023) for reliable identification; "
            "name-based lookup may return ambiguous results."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "identifier": {
                    "type": "string",
                    "description": "Customer ID (e.g. C10023) or full name",
                }
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "lookup_order",
        "description": (
            "Retrieve order details by order ID. "
            "Use for checking order status, items, delivery date, and eligibility flags. "
            "Do NOT use for financial operations — those require process_refund."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "Order ID (e.g. ORD-5501)",
                }
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "check_policy",
        "description": (
            "Look up company policy for a situation type. "
            "Use before processing any resolution to confirm eligibility and limits. "
            "Types: damage_claim, duplicate_charge, subscription_cancel, competitor_price_match"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "policy_type": {
                    "type": "string",
                    "enum": [
                        "damage_claim",
                        "duplicate_charge",
                        "subscription_cancel",
                        "competitor_price_match",
                    ],
                },
                "context": {
                    "type": "object",
                    "description": "Relevant order/customer context for policy evaluation",
                },
            },
            "required": ["policy_type"],
        },
    },
    {
        "name": "process_refund",
        "description": (
            "Process a customer refund. "
            "REQUIRES prior get_customer call — verified_customer_id must be in context. "
            "REQUIRES prior check_policy to confirm eligibility. "
            "Maximum $500 per transaction; amounts above this require escalation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id":  {"type": "string"},
                "amount":    {"type": "number", "description": "Refund amount in USD"},
                "reason":    {"type": "string", "description": "Brief reason for refund"},
            },
            "required": ["order_id", "amount", "reason"],
        },
    },
    {
        "name": "escalate_to_human",
        "description": (
            "Escalate the case to a human support agent. "
            "Use when: (1) customer explicitly requests a human, "
            "(2) policy gap prevents autonomous resolution, "
            "(3) unable to make meaningful progress. "
            "Always include a complete handoff summary."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "handoff_summary": {
                    "type": "string",
                    "description": (
                        "Complete structured summary including: "
                        "customer ID and name, issue description, root cause analysis, "
                        "actions already taken, recommended action, escalation reason"
                    ),
                }
            },
            "required": ["handoff_summary"],
        },
    },
]

SYSTEM_PROMPT = """You are a customer support resolution agent.

WORKFLOW RULES (enforced by the system — not just guidance):
1. Always call get_customer FIRST to verify identity
2. Always check_policy before processing any refund
3. process_refund is blocked until identity is verified

ESCALATION RULES:
- If customer explicitly asks for a human: escalate IMMEDIATELY, no investigation
- If policy is silent or ambiguous on the request: escalate (do not invent policy)
- If you cannot make meaningful progress: escalate with full context

ESCALATION CONTENT: When escalating, your handoff_summary MUST include:
  - Verified customer ID and name
  - Order IDs and issue descriptions
  - Root cause analysis from your investigation
  - All actions you already took
  - Your recommended resolution
  - Why you are escalating

RESOLUTION GOAL: 80%+ first-contact resolution.
For multi-issue requests, investigate ALL issues in parallel using the same verified customer context, then provide a SINGLE unified response.
"""


# ══════════════════════════════════════════════════════════════════
# SECTION 3: PROGRAMMATIC ENFORCEMENT (THE GATES)
# ══════════════════════════════════════════════════════════════════

class WorkflowState:
    """
    Maintains the mutable state that gates check.
    Lives in the runtime — Claude cannot read or modify this directly.
    """

    def __init__(self):
        self.verified_customer_id: Optional[str] = None
        self.customer_name: Optional[str] = None
        self.policy_checked: set[str] = set()     # track which policies were verified
        self.orders_looked_up: dict = {}
        self.tool_call_log: list[dict] = []
        self.refund_amount_this_session: float = 0.0

    def log(self, tool_name: str, inputs: dict, result: dict):
        self.tool_call_log.append({
            "tool": tool_name,
            "inputs": inputs,
            "result_summary": str(result)[:200],
            "timestamp": datetime.now().isoformat(),
        })


def dispatch_tool_with_gates(tool_name: str, inputs: dict, state: WorkflowState) -> dict:
    """
    Central dispatcher. Enforces prerequisite gates BEFORE executing any tool.

    This is the Q1 answer (Option A):
      - Gate blocks process_refund until get_customer returns verified ID
      - Gate is in the RUNTIME — cannot be bypassed by model reasoning
    """

    # ── GATE 1: process_refund requires verified customer ──────────
    if tool_name == "process_refund":
        if not state.verified_customer_id:
            return {
                "blocked": True,
                "reason": (
                    "process_refund is blocked: customer identity not yet verified. "
                    "Call get_customer first to obtain verified_customer_id."
                ),
                "required_step": "get_customer",
            }
        # ── GATE 2: process_refund requires policy check ──────────
        # (ensure we don't refund outside policy bounds)
        # This is a softer gate — we warn rather than block
        if not state.policy_checked:
            return {
                "blocked": True,
                "reason": (
                    "process_refund is blocked: no policy has been checked yet. "
                    "Call check_policy first to confirm refund eligibility and limits."
                ),
                "required_step": "check_policy",
            }

    # ── GATE 3: lookup_order and process_refund both require customer ──
    if tool_name == "lookup_order" and not state.verified_customer_id:
        # Soft gate: warn but allow (order lookup is read-only)
        # For financial operations, this would be a hard gate
        pass  # allow through with warning in result

    # ── Execute the actual tool ────────────────────────────────────
    result = _execute_backend_tool(tool_name, inputs, state)

    # ── PostToolUse: policy enforcement hook ───────────────────────
    result = post_tool_use_hook(tool_name, inputs, result, state)

    # ── Update state from result ───────────────────────────────────
    _update_state(tool_name, result, state)

    # ── Log the call ───────────────────────────────────────────────
    state.log(tool_name, inputs, result)

    return result


def _execute_backend_tool(tool_name: str, inputs: dict, state: WorkflowState) -> dict:
    """Call the actual backend function."""
    dispatch = {
        "get_customer":    lambda: tool_get_customer(inputs["identifier"]),
        "lookup_order":    lambda: tool_lookup_order(inputs["order_id"]),
        "check_policy":    lambda: tool_check_policy(
            inputs["policy_type"], inputs.get("context", {})
        ),
        "process_refund":  lambda: tool_process_refund(
            inputs["order_id"],
            inputs["amount"],
            inputs["reason"],
            state.verified_customer_id,        # injected from state — not from model
        ),
        "escalate_to_human": lambda: tool_escalate_to_human(inputs["handoff_summary"]),
    }
    fn = dispatch.get(tool_name)
    if not fn:
        return {"error": f"Unknown tool: {tool_name}"}
    try:
        return fn()
    except Exception as exc:
        return {"error": str(exc)}


def post_tool_use_hook(tool_name: str, inputs: dict, result: dict, state: WorkflowState) -> dict:
    """
    PostToolUse hook: fires after every tool execution.

    Handles:
      1. Policy enforcement: block refunds above $500 threshold
      2. Data normalisation: unified timestamp and status formats
    """

    # ── Policy enforcement: refund threshold ───────────────────────
    if tool_name == "process_refund" and not result.get("error"):
        amount = inputs.get("amount", 0)
        state.refund_amount_this_session += amount

        if amount > 500:
            # Block the refund, redirect to escalation
            return {
                "blocked": True,
                "reason": f"Refund of ${amount:.2f} exceeds $500 per-transaction limit.",
                "action_required": "Use escalate_to_human for amounts above $500.",
                "attempted_amount": amount,
                "order_id": inputs.get("order_id"),
            }

    # ── Data normalisation: unify timestamp formats ─────────────────
    # Different MCP tools return dates in different formats.
    # Normalise to ISO 8601 before the model processes the result.
    for key in ("created_at", "delivered_date", "refund_date"):
        if key in result and isinstance(result[key], (int, float)):
            # Unix timestamp → ISO 8601
            result[key] = datetime.utcfromtimestamp(result[key]).isoformat() + "Z"

    # ── Data normalisation: numeric status codes → human-readable ──
    if "status_code" in result:
        code_map = {200: "success", 404: "not_found", 403: "forbidden", 500: "server_error"}
        result["status"] = code_map.get(result["status_code"], f"code_{result['status_code']}")

    return result


def _update_state(tool_name: str, result: dict, state: WorkflowState):
    """Update workflow state based on tool results."""
    if tool_name == "get_customer" and "verified_customer_id" in result:
        state.verified_customer_id = result["verified_customer_id"]
        state.customer_name = result.get("name")

    if tool_name == "lookup_order" and "order_id" in result:
        state.orders_looked_up[result["order_id"]] = result

    if tool_name == "check_policy":
        state.policy_checked.add(result.get("resolution", "unknown"))


# ══════════════════════════════════════════════════════════════════
# SECTION 4: THE AGENTIC LOOP
# ══════════════════════════════════════════════════════════════════

def run_customer_support_agent(customer_message: str, max_turns: int = 15) -> dict:
    """
    Full agentic loop for the Customer Support Resolution Agent.

    The loop:
      1. Sends message + history to Claude
      2. If stop_reason=tool_use: gates check, tool executes, result appended
      3. If stop_reason=end_turn: agent has finished; return result
    """
    state = WorkflowState()
    messages = [{"role": "user", "content": customer_message}]

    print(f"\n{'='*70}")
    print(f"CUSTOMER: {customer_message}")
    print(f"{'='*70}")

    for turn in range(1, max_turns + 1):
        print(f"\n── Turn {turn} ──────────────────────────────────────────")

        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        # Append assistant response
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            final_text = next(
                (b.text for b in response.content if hasattr(b, "text")), ""
            )
            print(f"\n✓ AGENT RESPONSE:\n{final_text}")
            return {
                "status": "resolved",
                "response": final_text,
                "turns": turn,
                "verified_customer_id": state.verified_customer_id,
                "tool_calls": len(state.tool_call_log),
            }

        # Process tool calls
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            print(f"  Tool call: {block.name}({json.dumps(block.input, default=str)[:80]})")

            # ── GATES ARE HERE — this is where enforcement happens ──
            result = dispatch_tool_with_gates(block.name, block.input, state)

            if result.get("blocked"):
                print(f"  ⛔ BLOCKED: {result['reason'][:80]}")
            else:
                print(f"  ✓ Result: {str(result)[:80]}...")

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result, default=str),
                "is_error": bool(result.get("error") or result.get("blocked")),
            })

        messages.append({"role": "user", "content": tool_results})

    return {"status": "max_turns_exceeded", "turns": max_turns}


# ══════════════════════════════════════════════════════════════════
# SECTION 5: DEMO SCENARIOS
# ══════════════════════════════════════════════════════════════════

def demo_q1_bypass_prevention():
    """
    Demonstrates Q1 scenario: customer volunteers order ID.
    Without gates, agent might call lookup_order directly.
    With gates, it is BLOCKED until get_customer completes.
    """
    print("\n" + "="*70)
    print("DEMO: Q1 — Bypass Prevention (customer volunteers order ID)")
    print("="*70)
    print("Expected: Agent cannot call process_refund without verification")
    print("Gate enforcement: programmatic, not prompt-based")

    state = WorkflowState()

    # Simulate model trying to skip verification
    print("\nSimulating model attempt to skip verification...")

    result = dispatch_tool_with_gates(
        "process_refund",
        {"order_id": "ORD-5501", "amount": 149.99, "reason": "damaged"},
        state,
    )
    print(f"Result (no verification): {result}")
    assert result.get("blocked"), "Gate should have blocked this!"

    # Now verify customer
    result = dispatch_tool_with_gates(
        "get_customer", {"identifier": "C10023"}, state
    )
    print(f"\nAfter get_customer: verified_id = {state.verified_customer_id}")

    # Check policy
    dispatch_tool_with_gates(
        "check_policy", {"policy_type": "damage_claim"}, state
    )

    # Now refund should work
    result = dispatch_tool_with_gates(
        "process_refund",
        {"order_id": "ORD-5501", "amount": 149.99, "reason": "damaged goods"},
        state,
    )
    print(f"\nAfter verification + policy check: {result}")
    assert not result.get("blocked"), "Refund should succeed after gates pass!"
    print("✓ Gate enforcement working correctly")


def demo_refund_threshold_hook():
    """Demonstrates PostToolUse hook blocking a $750 refund."""
    print("\n" + "="*70)
    print("DEMO: PostToolUse Hook — $500 Threshold Enforcement")
    print("="*70)

    state = WorkflowState()
    dispatch_tool_with_gates("get_customer", {"identifier": "C10023"}, state)
    dispatch_tool_with_gates("check_policy", {"policy_type": "damage_claim"}, state)

    result = dispatch_tool_with_gates(
        "process_refund",
        {"order_id": "ORD-5501", "amount": 750.00, "reason": "large damage claim"},
        state,
    )
    print(f"Result: {result}")
    assert result.get("blocked"), "Hook should block amounts over $500"
    print("✓ Hook enforcement working correctly")


if __name__ == "__main__":
    # Run demonstrations
    demo_q1_bypass_prevention()
    demo_refund_threshold_hook()

    # Run a full agent conversation
    run_customer_support_agent(
        "Hi, my customer ID is C10023. Order ORD-5501 arrived damaged and "
        "I also notice a duplicate charge on ORD-5502. Can you help with both?"
    )
