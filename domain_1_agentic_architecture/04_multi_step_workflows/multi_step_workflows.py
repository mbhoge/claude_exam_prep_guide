"""
Task 1.4 – Multi-Step Workflows with Enforcement and Handoff Patterns
======================================================================
Directly tested in Sample Question 1 (customer support agent skips get_customer).

Core distinction:
  - Prompt instructions = probabilistic compliance (non-zero failure rate)
  - Programmatic prerequisites = deterministic compliance (zero bypass rate)

When identity verification is required before financial operations,
use programmatic enforcement — prompts alone are insufficient.
"""

import anthropic
from dataclasses import dataclass
from typing import Optional

client = anthropic.Anthropic()


# ─────────────────────────────────────────────────────────
# SECTION 1: Tools for the customer support scenario
# ─────────────────────────────────────────────────────────

def get_customer(identifier: str) -> dict:
    """Verify customer identity and return verified customer ID."""
    # Simulated: real impl queries customer DB
    if identifier.startswith("C"):
        return {
            "verified_customer_id": f"VERIFIED_{identifier}",
            "name": "Jane Smith",
            "email": "jane@example.com",
        }
    return {"error": "Customer not found"}


def lookup_order(order_id: str, verified_customer_id: Optional[str] = None) -> dict:
    """Look up an order. Requires verified_customer_id for security."""
    if not verified_customer_id:
        return {"error": "verified_customer_id required before order lookup"}
    return {
        "order_id": order_id,
        "status": "shipped",
        "total": 149.99,
        "items": ["Widget A", "Widget B"],
    }


def process_refund(order_id: str, amount: float, verified_customer_id: Optional[str] = None) -> dict:
    """Process a refund. Requires prior customer verification."""
    if not verified_customer_id:
        return {"error": "verified_customer_id required before refund"}
    return {"refund_id": f"REF-{order_id}", "amount": amount, "status": "approved"}


# ─────────────────────────────────────────────────────────
# SECTION 2: WRONG approach – prompt-only enforcement
# ─────────────────────────────────────────────────────────
# ❌ This is what Option B in Q1 looks like.
# Prompt says "always call get_customer first" but model may skip it.

WRONG_SYSTEM_PROMPT = """
You are a customer support agent.
IMPORTANT: Always call get_customer before any order operations.
You must verify the customer's identity before looking up orders or processing refunds.
"""
# Reality: In ~12% of cases (per Q1 scenario), the agent ignores this.
# When a customer volunteers their order ID, model may call lookup_order directly.


# ─────────────────────────────────────────────────────────
# SECTION 3: CORRECT approach – programmatic prerequisite gate
# ─────────────────────────────────────────────────────────

class CustomerSupportWorkflow:
    """
    Implements programmatic prerequisite gates that BLOCK downstream
    tool calls until prerequisite steps complete.

    This is the correct answer to Q1: Option A.
    """

    def __init__(self):
        self.verified_customer_id: Optional[str] = None
        self.verified_order_id: Optional[str] = None
        self._tool_call_log: list = []

    # ── Programmatic gates ────────────────────────────────

    def _require_customer_verification(self, operation: str) -> None:
        """Gate: block operation if customer not yet verified."""
        if not self.verified_customer_id:
            raise PermissionError(
                f"Cannot {operation}: customer identity not verified. "
                f"Call get_customer first to obtain verified_customer_id."
            )

    def _require_order_lookup(self, operation: str) -> None:
        """Gate: block operation if order not yet retrieved."""
        if not self.verified_order_id:
            raise PermissionError(
                f"Cannot {operation}: order not yet retrieved. "
                f"Call lookup_order first."
            )

    # ── Tool wrappers with gates ──────────────────────────

    def tool_get_customer(self, identifier: str) -> dict:
        """Step 1: Must be called first. Unlocks order operations."""
        result = get_customer(identifier)
        if "verified_customer_id" in result:
            self.verified_customer_id = result["verified_customer_id"]
        return result

    def tool_lookup_order(self, order_id: str) -> dict:
        """Step 2: Gate blocks this until get_customer completes."""
        self._require_customer_verification("lookup order")   # programmatic gate
        result = lookup_order(order_id, self.verified_customer_id)
        if "order_id" in result:
            self.verified_order_id = result["order_id"]
        return result

    def tool_process_refund(self, order_id: str, amount: float) -> dict:
        """Step 3: Gate blocks this until both prior steps complete."""
        self._require_customer_verification("process refund")  # gate 1
        self._require_order_lookup("process refund")           # gate 2
        return process_refund(order_id, amount, self.verified_customer_id)

    # ── Execute tool call from agent ──────────────────────

    def execute_tool(self, tool_name: str, inputs: dict) -> dict:
        """Dispatch tool call through workflow with gates enforced."""
        self._tool_call_log.append(tool_name)
        handlers = {
            "get_customer":   lambda: self.tool_get_customer(inputs["identifier"]),
            "lookup_order":   lambda: self.tool_lookup_order(inputs["order_id"]),
            "process_refund": lambda: self.tool_process_refund(
                inputs["order_id"], inputs["amount"]
            ),
        }
        handler = handlers.get(tool_name)
        if not handler:
            return {"error": f"Unknown tool: {tool_name}"}
        try:
            return handler()
        except PermissionError as exc:
            return {"error": str(exc), "requires": "complete_prerequisite_steps"}


# ─────────────────────────────────────────────────────────
# SECTION 4: Structured handoff summaries
# ─────────────────────────────────────────────────────────

@dataclass
class HandoffSummary:
    """
    Structured summary for escalation to human agents.
    Human agents don't have access to the conversation transcript.
    """
    customer_id: str
    customer_name: str
    order_id: str
    issue_type: str
    root_cause: str
    actions_taken: list[str]
    recommended_action: str
    refund_amount: Optional[float] = None
    urgency: str = "normal"

    def format_for_human_agent(self) -> str:
        lines = [
            f"=== ESCALATION HANDOFF ===",
            f"Customer: {self.customer_name} (ID: {self.customer_id})",
            f"Order: {self.order_id}",
            f"Issue: {self.issue_type}",
            f"Root Cause: {self.root_cause}",
            f"",
            f"Actions Taken:",
        ]
        for action in self.actions_taken:
            lines.append(f"  - {action}")
        if self.refund_amount:
            lines.append(f"Refund Amount: ${self.refund_amount:.2f}")
        lines += [
            f"",
            f"RECOMMENDED ACTION: {self.recommended_action}",
            f"Urgency: {self.urgency.upper()}",
        ]
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────
# SECTION 5: PostToolUse hook for enforcement
# ─────────────────────────────────────────────────────────

def post_tool_use_hook(tool_name: str, tool_result: dict, workflow: CustomerSupportWorkflow) -> dict:
    """
    Hook that intercepts tool results for:
    1. Data normalisation (different MCP tools return different formats)
    2. Policy enforcement (block actions above threshold)

    This is Task 1.5 territory but related to Task 1.4.
    """
    # Policy enforcement: block refunds above $500
    if tool_name == "process_refund":
        amount = tool_result.get("amount", 0)
        if amount > 500:
            return {
                "blocked": True,
                "reason": "Refund exceeds $500 threshold",
                "action": "Escalate to human agent for manual approval",
                "attempted_amount": amount,
            }

    # Data normalisation: unify date formats from different MCP sources
    if "created_at" in tool_result:
        import re
        date = tool_result["created_at"]
        # Unix timestamp → ISO 8601
        if isinstance(date, (int, float)):
            from datetime import datetime
            tool_result["created_at"] = datetime.utcfromtimestamp(date).isoformat()

    return tool_result


# ─────────────────────────────────────────────────────────
# Demo: Q1 scenario
# ─────────────────────────────────────────────────────────

def q1_scenario_demo():
    """
    Reproduces Q1: agent tries to call process_refund without verification.
    Programmatic gate blocks it; prompt-only approach would allow it 12% of the time.
    """
    workflow = CustomerSupportWorkflow()

    print("Q1 Demo: Programmatic prerequisite gate")
    print()

    # Attempt 1: Try to process refund without verification (should fail)
    print("1. Attempting refund without customer verification...")
    result = workflow.execute_tool("process_refund", {"order_id": "ORD-123", "amount": 49.99})
    print(f"   Result: {result}")
    print()

    # Attempt 2: Verify customer first
    print("2. Verifying customer identity...")
    result = workflow.execute_tool("get_customer", {"identifier": "C99182"})
    print(f"   Result: {result}")
    print()

    # Attempt 3: Try refund again (should still fail – no order lookup yet)
    print("3. Attempting refund without order lookup...")
    result = workflow.execute_tool("process_refund", {"order_id": "ORD-123", "amount": 49.99})
    print(f"   Result: {result}")
    print()

    # Attempt 4: Lookup order
    print("4. Looking up order...")
    result = workflow.execute_tool("lookup_order", {"order_id": "ORD-123"})
    print(f"   Result: {result}")
    print()

    # Attempt 5: Now refund should succeed
    print("5. Processing refund (all prerequisites met)...")
    result = workflow.execute_tool("process_refund", {"order_id": "ORD-123", "amount": 49.99})
    print(f"   Result: {result}")


if __name__ == "__main__":
    q1_scenario_demo()
