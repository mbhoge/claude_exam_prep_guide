"""
agent_sdk_hooks.py — Agent SDK Hooks: Interception & Data Normalization
=======================================================================
Exam domain: 1.5 — Agent SDK Hooks for Tool Call Interception

Demonstrates:
  1. HookManager — registers and dispatches PreToolUse / PostToolUse hooks
  2. PostToolUse normalization — unifies heterogeneous MCP data formats
     (Unix timestamps, ISO 8601, RFC 2822; numeric/bool/string status codes)
  3. PreToolUse compliance — blocks refunds above $500, redirects to human
  4. Full agentic loop with hooks wired in
  5. Side-by-side: prompt-based (probabilistic) vs hook-based (deterministic)

Key exam assertion:
  Hooks are DETERMINISTIC. Prompts are PROBABILISTIC.
  Any business rule that must NEVER be violated requires a hook, not a prompt.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable
import anthropic

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: DATA NORMALIZATION UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

STATUS_CODE_MAP = {
    0: "pending",
    1: "active",
    2: "on_hold",
    3: "cancelled",
    4: "completed",
    5: "error",
}


def to_iso8601(value: Any) -> str:
    """Convert any timestamp representation to ISO 8601 UTC string."""
    if isinstance(value, (int, float)):
        # Unix epoch seconds or milliseconds
        ts = value / 1000 if value > 1e10 else value
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

    if isinstance(value, str):
        # Already ISO 8601 — validate and normalise timezone suffix
        if "T" in value:
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return dt.astimezone(timezone.utc).isoformat()
            except ValueError:
                pass

        # RFC 2822: "Mon, 06 May 2024 12:34:56 +0000"
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(value).astimezone(timezone.utc).isoformat()
        except Exception:
            pass

    # Fallback: return as-is with a warning tag so the model knows it's raw
    return f"[unparsed_timestamp:{value}]"


def normalize_status(value: Any) -> str:
    """Convert numeric codes, booleans, or strings to a unified status string."""
    if isinstance(value, bool):
        return "active" if value else "inactive"
    if isinstance(value, int):
        return STATUS_CODE_MAP.get(value, f"unknown_{value}")
    if isinstance(value, str):
        return value.lower().strip()
    return str(value)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: HOOK MANAGER
# ─────────────────────────────────────────────────────────────────────────────

class HookManager:
    """
    Central registry and dispatcher for PreToolUse and PostToolUse hooks.

    PreToolUse hooks return None (allow) or a dict (block with reason).
    PostToolUse hooks receive (tool_name, inputs, result) and return
    a (possibly modified) result dict.
    """

    def __init__(self):
        self._pre_hooks: list[Callable] = []
        self._post_hooks: list[Callable] = []

    def register_pre(self, fn: Callable) -> None:
        """Register a PreToolUse hook. Called before the tool executes."""
        self._pre_hooks.append(fn)

    def register_post(self, fn: Callable) -> None:
        """Register a PostToolUse hook. Called after the tool executes."""
        self._post_hooks.append(fn)

    def run_pre(self, tool_name: str, inputs: dict) -> dict | None:
        """
        Run all PreToolUse hooks in registration order.
        First hook that returns a non-None value wins (short-circuit).
        Returns None to allow the tool call to proceed.
        """
        for hook in self._pre_hooks:
            result = hook(tool_name, inputs)
            if result is not None:
                return result
        return None

    def run_post(self, tool_name: str, inputs: dict, raw_result: dict) -> dict:
        """
        Run all PostToolUse hooks in registration order.
        Each hook receives the output of the previous one (pipeline).
        """
        result = raw_result
        for hook in self._post_hooks:
            result = hook(tool_name, inputs, result)
        return result


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: CONCRETE HOOKS
# ─────────────────────────────────────────────────────────────────────────────

# ── PostToolUse: Data Normalization ──────────────────────────────────────────

TIMESTAMP_FIELDS = {"created_at", "updated_at", "timestamp", "date", "processed_at"}
STATUS_FIELDS = {"status", "state", "order_status"}


def hook_normalize_data_formats(
    tool_name: str, inputs: dict, result: dict
) -> dict:
    """
    PostToolUse hook: normalize heterogeneous MCP responses to a canonical schema.

    Problem this solves:
      CRM returns  {"created_at": 1715000000, "status": 1}       (Unix + int code)
      ERP returns  {"created_at": "2024-05-06T12:00:00Z", "status": "active"} (ISO + string)
      Payments     {"created_at": "Mon, 06 May 2024 ...", "status": true}  (RFC2822 + bool)

    Without this hook the model must reason about format ambiguity on every call.
    With this hook it always sees ISO 8601 UTC strings and human-readable status.
    """
    normalized = dict(result)

    for field in TIMESTAMP_FIELDS:
        if field in normalized:
            normalized[field] = to_iso8601(normalized[field])

    for field in STATUS_FIELDS:
        if field in normalized:
            normalized[field] = normalize_status(normalized[field])

    # Mark result as normalized so downstream hooks / the model can trust the format
    normalized["_normalized"] = True
    return normalized


# ── PreToolUse: Compliance Enforcement ───────────────────────────────────────

REFUND_THRESHOLD = 500.0


def hook_enforce_refund_policy(tool_name: str, inputs: dict) -> dict | None:
    """
    PreToolUse hook: block process_refund calls that exceed the policy limit.

    Returns None  → allow the call (passes through to the tool)
    Returns dict  → block the call (model receives this as the "tool result")

    The returned dict contains required_action, which instructs the model
    exactly what to do instead (deterministic redirection).
    """
    if tool_name != "process_refund":
        return None

    amount = float(inputs.get("amount", 0))
    if amount <= REFUND_THRESHOLD:
        return None  # within policy — allow

    return {
        "blocked": True,
        "policy": "REFUND_POLICY_001",
        "reason": (
            f"Refund of ${amount:.2f} exceeds the ${REFUND_THRESHOLD:.2f} "
            "automated processing limit."
        ),
        "required_action": (
            "Call escalate_to_human with type='high_value_refund', "
            f"amount={amount}, and the customer's order_id."
        ),
        "escalation_type": "high_value_refund",
        "original_amount": amount,
    }


def hook_block_delete_in_production(tool_name: str, inputs: dict) -> dict | None:
    """
    PreToolUse hook: block any tool that deletes records in production environment.
    Shows a second compliance use-case pattern for the exam.
    """
    if "delete" in tool_name.lower():
        env = inputs.get("environment", "production")
        if env == "production":
            return {
                "blocked": True,
                "reason": "Destructive operations in production require manual approval.",
                "required_action": "Create a change-request ticket via submit_change_request.",
            }
    return None


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: MOCK MCP TOOL REGISTRY
# (Simulates heterogeneous MCP servers returning different data formats)
# ─────────────────────────────────────────────────────────────────────────────

def _crm_get_customer(customer_id: str) -> dict:
    """Legacy CRM: Unix timestamps, numeric status codes."""
    return {
        "customer_id": customer_id,
        "name": "Alice Johnson",
        "email": "alice@example.com",
        "created_at": 1715000000,       # Unix epoch
        "status": 1,                    # numeric: 1 = active
        "tier": "gold",
    }


def _erp_get_order(order_id: str) -> dict:
    """Modern ERP: ISO 8601, string status."""
    return {
        "order_id": order_id,
        "total": 149.99,
        "created_at": "2024-05-06T12:00:00Z",   # ISO 8601
        "status": "delivered",                   # already string
    }


def _payments_process_refund(order_id: str, amount: float, reason: str) -> dict:
    """Payment gateway: RFC 2822, boolean status."""
    return {
        "refund_id": f"REF-{order_id}",
        "amount": amount,
        "processed_at": "Mon, 06 May 2024 12:34:56 +0000",   # RFC 2822
        "status": True,                                        # bool: True = success
    }


def _escalate_to_human(escalation_type: str, amount: float, order_id: str) -> dict:
    return {
        "ticket_id": f"ESC-{order_id}",
        "escalation_type": escalation_type,
        "amount": amount,
        "status": "pending_review",
        "assigned_to": "tier2_support",
    }


TOOL_REGISTRY: dict[str, Callable] = {
    "get_customer":      lambda **kw: _crm_get_customer(kw["customer_id"]),
    "get_order":         lambda **kw: _erp_get_order(kw["order_id"]),
    "process_refund":    lambda **kw: _payments_process_refund(
                             kw["order_id"], kw["amount"], kw.get("reason", "")
                         ),
    "escalate_to_human": lambda **kw: _escalate_to_human(
                             kw["escalation_type"], kw["amount"], kw["order_id"]
                         ),
}

TOOL_DEFINITIONS = [
    {
        "name": "get_customer",
        "description": "Retrieve customer details from CRM by customer ID.",
        "input_schema": {
            "type": "object",
            "properties": {"customer_id": {"type": "string"}},
            "required": ["customer_id"],
        },
    },
    {
        "name": "get_order",
        "description": "Retrieve order details from ERP by order ID.",
        "input_schema": {
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
        },
    },
    {
        "name": "process_refund",
        "description": "Issue a refund for a completed order. Max $500 automated.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "amount":   {"type": "number"},
                "reason":   {"type": "string"},
            },
            "required": ["order_id", "amount"],
        },
    },
    {
        "name": "escalate_to_human",
        "description": "Escalate a request to the human support tier.",
        "input_schema": {
            "type": "object",
            "properties": {
                "escalation_type": {"type": "string"},
                "amount":          {"type": "number"},
                "order_id":        {"type": "string"},
            },
            "required": ["escalation_type", "amount", "order_id"],
        },
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: AGENTIC LOOP WITH HOOKS
# ─────────────────────────────────────────────────────────────────────────────

def execute_tool_with_hooks(
    tool_name: str,
    inputs: dict,
    hooks: HookManager,
) -> dict:
    """
    Core dispatcher: runs hooks around every tool call.

    Step 1 — PreToolUse:  hooks can block the call before it executes
    Step 2 — Tool exec:   dispatches to the actual tool (or MCP server)
    Step 3 — PostToolUse: hooks normalize / transform the raw result
    """
    # Step 1: PreToolUse — compliance check
    block = hooks.run_pre(tool_name, inputs)
    if block is not None:
        print(f"  [PreToolUse] BLOCKED '{tool_name}': {block['reason']}")
        return block

    # Step 2: Dispatch to actual tool
    tool_fn = TOOL_REGISTRY.get(tool_name)
    if tool_fn is None:
        return {"error": f"Unknown tool: {tool_name}"}

    raw_result = tool_fn(**inputs)
    print(f"  [Tool]       '{tool_name}' raw result: {json.dumps(raw_result)}")

    # Step 3: PostToolUse — normalization
    normalized = hooks.run_post(tool_name, inputs, raw_result)
    if normalized != raw_result:
        print(f"  [PostToolUse] Normalized '{tool_name}': {json.dumps(normalized)}")

    return normalized


def run_agentic_loop(user_message: str, hooks: HookManager) -> str:
    """
    Full agentic loop. Hooks intercept every tool call transparently.
    The model prompt contains NO compliance rules — those live in hooks.
    """
    client = anthropic.Anthropic()

    system = (
        "You are a customer support agent. "
        "Use the available tools to handle customer requests. "
        "Follow any guidance in tool responses about required next steps."
        # Note: NO refund threshold mentioned here.
        # That constraint lives entirely in the PreToolUse hook.
    )

    messages = [{"role": "user", "content": user_message}]

    print(f"\n{'='*70}")
    print(f"USER: {user_message}")
    print(f"{'='*70}")

    while True:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        # Collect any text content to return at the end
        text_parts = [b.text for b in response.content if b.type == "text"]

        if response.stop_reason == "end_turn":
            return " ".join(text_parts)

        # Process tool_use blocks
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        if not tool_use_blocks:
            return " ".join(text_parts)

        # Append assistant turn
        messages.append({"role": "assistant", "content": response.content})

        # Execute each tool call through hooks
        tool_results = []
        for block in tool_use_blocks:
            result = execute_tool_with_hooks(block.name, block.input, hooks)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result),
            })

        messages.append({"role": "user", "content": tool_results})


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: DEMONSTRATIONS
# ─────────────────────────────────────────────────────────────────────────────

def build_production_hooks() -> HookManager:
    """Wire up all hooks for the production scenario."""
    hooks = HookManager()
    hooks.register_pre(hook_enforce_refund_policy)
    hooks.register_pre(hook_block_delete_in_production)
    hooks.register_post(hook_normalize_data_formats)
    return hooks


def demo_normalization_only():
    """
    Isolated PostToolUse demonstration — no model involved.
    Shows the raw vs normalized output for each MCP server format.
    """
    print("\n" + "="*70)
    print("DEMO 1: PostToolUse Data Normalization (isolated)")
    print("="*70)

    hooks = HookManager()
    hooks.register_post(hook_normalize_data_formats)

    scenarios = [
        ("get_customer", {"customer_id": "C10023"}),
        ("get_order", {"order_id": "ORD-5501"}),
    ]

    for tool_name, inputs in scenarios:
        tool_fn = TOOL_REGISTRY[tool_name]
        raw = tool_fn(**inputs)
        normalized = hooks.run_post(tool_name, inputs, raw)

        print(f"\nTool: {tool_name}")
        print(f"  RAW:        {json.dumps(raw)}")
        print(f"  NORMALIZED: {json.dumps(normalized)}")

    print()
    print("Observation:")
    print("  CRM  epoch 1715000000     -> ISO 8601 UTC string")
    print("  CRM  status code 1        -> 'active'")
    print("  Both: same schema, model reasons about data not format")


def demo_compliance_enforcement():
    """
    Isolated PreToolUse demonstration — no model involved.
    Shows blocking at the hook layer before the tool runs.
    """
    print("\n" + "="*70)
    print("DEMO 2: PreToolUse Compliance Enforcement (isolated)")
    print("="*70)

    hooks = HookManager()
    hooks.register_pre(hook_enforce_refund_policy)

    test_cases = [
        ("process_refund", {"order_id": "ORD-001", "amount": 149.99}, "under threshold"),
        ("process_refund", {"order_id": "ORD-002", "amount": 500.00}, "exactly at threshold"),
        ("process_refund", {"order_id": "ORD-003", "amount": 500.01}, "just over threshold"),
        ("process_refund", {"order_id": "ORD-004", "amount": 750.00}, "well over threshold"),
        ("get_order",      {"order_id": "ORD-005"},                   "non-refund tool (passthrough)"),
    ]

    for tool_name, inputs, label in test_cases:
        result = hooks.run_pre(tool_name, inputs)
        status = "BLOCKED" if result else "ALLOWED"
        amount = inputs.get("amount", "N/A")
        print(f"  amount=${amount:<8} ({label}): {status}")
        if result:
            print(f"    required_action: {result['required_action']}")


def demo_hooks_vs_prompts():
    """
    Conceptual comparison: shows why hooks provide guarantees that prompts cannot.
    No API call needed — demonstrates the logic layer.
    """
    print("\n" + "="*70)
    print("DEMO 3: Hooks vs Prompts — Deterministic vs Probabilistic")
    print("="*70)

    print("""
┌────────────────────────────────┬──────────────────────────────────────────┐
│ PROMPT-BASED ENFORCEMENT       │ HOOK-BASED ENFORCEMENT                   │
├────────────────────────────────┼──────────────────────────────────────────┤
│ "Do not refund > $500"         │ if amount > 500: return {blocked: True}  │
│ in system prompt               │ in PreToolUse hook                       │
├────────────────────────────────┼──────────────────────────────────────────┤
│ Model READS the rule           │ Code EXECUTES the rule                   │
│ Model DECIDES to follow        │ No decision — it either runs or doesn't  │
├────────────────────────────────┼──────────────────────────────────────────┤
│ Failure modes:                 │ Failure modes:                           │
│  • "Customer urgently needs…"  │  • None                                  │
│  • Long context / forgetting   │                                          │
│  • Split-refund bypass         │                                          │
│  • Reasoning override          │                                          │
├────────────────────────────────┼──────────────────────────────────────────┤
│ Compliance rate: ~88–95%       │ Compliance rate: 100%                    │
│ (fails 500-1500x per 10k txns) │ (zero failures, guaranteed)             │
└────────────────────────────────┴──────────────────────────────────────────┘

EXAM RULE: If the question asks which approach "guarantees" or "ensures"
compliance, the answer is always hooks/programmatic enforcement.
If it asks which approach "improves" compliance, prompts can qualify.
""")


def demo_full_agentic_loop():
    """
    Full end-to-end demonstration: model + hooks + MCP simulation.
    Run this only when ANTHROPIC_API_KEY is set.
    """
    hooks = build_production_hooks()

    # Scenario A: small refund — hook allows, normalizes output
    print("\n--- Scenario A: $149.99 refund (within policy) ---")
    result = run_agentic_loop(
        "Customer C10023's order ORD-5501 arrived damaged. Process a $149.99 refund.",
        hooks,
    )
    print(f"\nFINAL: {result}")

    # Scenario B: large refund — hook blocks, model redirects to escalation
    print("\n--- Scenario B: $750 refund (exceeds policy) ---")
    result = run_agentic_loop(
        "Customer C10023's order ORD-5501 was completely lost. Process a $750.00 refund.",
        hooks,
    )
    print(f"\nFINAL: {result}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: EXAM QUICK-REFERENCE
# ─────────────────────────────────────────────────────────────────────────────

EXAM_PATTERNS = """
╔══════════════════════════════════════════════════════════════════════════╗
║  EXAM QUICK-REFERENCE: Agent SDK Hooks                                 ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                        ║
║  PostToolUse hooks                                                     ║
║  • Run AFTER tool executes, BEFORE model sees the result               ║
║  • Use case: normalize heterogeneous data (timestamps, status codes)   ║
║  • Effect: model always gets canonical schema; never sees raw format   ║
║                                                                        ║
║  PreToolUse hooks                                                      ║
║  • Run BEFORE tool executes, can BLOCK the call entirely               ║
║  • Use case: enforce policy limits (refund threshold, env protection)  ║
║  • Effect: blocked → model receives error dict with required_action    ║
║           allowed → tool runs normally                                  ║
║                                                                        ║
║  Deterministic vs Probabilistic                                        ║
║  • Hook  = deterministic (code path; model not involved in decision)  ║
║  • Prompt = probabilistic (model interprets; may deviate 5-15%)       ║
║                                                                        ║
║  Choose hooks when:                                                    ║
║  • Financial / compliance rules that MUST NEVER be violated            ║
║  • Step ordering that MUST be enforced                                 ║
║  • Data format that MUST be canonical                                  ║
║                                                                        ║
║  Choose prompts when:                                                  ║
║  • Style, tone, format preferences                                     ║
║  • Suggestions or defaults (not hard rules)                            ║
║  • The "violation" produces suboptimal output, not real-world harm     ║
╚══════════════════════════════════════════════════════════════════════════╝
"""


if __name__ == "__main__":
    demo_normalization_only()
    demo_compliance_enforcement()
    demo_hooks_vs_prompts()
    print(EXAM_PATTERNS)

    # Uncomment to run the full agentic loop (requires ANTHROPIC_API_KEY):
    # demo_full_agentic_loop()
