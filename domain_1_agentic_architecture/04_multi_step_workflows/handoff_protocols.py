"""
handoff_protocols.py — Structured Handoff Protocols and Multi-Concern Decomposition
====================================================================================
Covers two skills from Task 1.4:

SKILL 1: Compiling structured handoff summaries for human agents who
         lack access to the conversation transcript.

SKILL 2: Decomposing multi-concern customer requests into distinct items,
         investigating each in parallel using shared context, then
         synthesising a unified resolution.

Run:
    python handoff_protocols.py
"""

import anthropic
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum

client = anthropic.Anthropic()


# ══════════════════════════════════════════════════════════════════
# SECTION 1: HANDOFF PROTOCOL DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════

class EscalationReason(str, Enum):
    CUSTOMER_REQUESTED  = "customer_explicitly_requested_human"
    POLICY_GAP          = "policy_gap_or_exception_required"
    OVER_THRESHOLD      = "amount_exceeds_automated_limit"
    UNABLE_TO_PROGRESS  = "unable_to_make_meaningful_progress"
    AMBIGUOUS_IDENTITY  = "multiple_customer_matches"


class UrgencyLevel(str, Enum):
    LOW    = "low"
    NORMAL = "normal"
    HIGH   = "high"
    URGENT = "urgent"   # e.g. customer very upset, time-sensitive refund


@dataclass
class ActionTaken:
    tool_name: str
    inputs: dict
    result_summary: str
    succeeded: bool


@dataclass
class IssueDetail:
    issue_type: str        # e.g. "damaged_goods", "duplicate_charge"
    order_id: Optional[str]
    description: str
    root_cause: str
    evidence: str


@dataclass
class HandoffSummary:
    """
    Complete structured handoff.
    Human agents have NO access to conversation transcript —
    this summary must contain EVERYTHING they need to continue.
    """
    # Customer identity
    verified_customer_id: str
    customer_name: str
    customer_email: str
    customer_tier: str

    # Issues
    issues: list[IssueDetail]

    # What was done
    actions_taken: list[ActionTaken]

    # Resolution guidance
    recommended_action: str
    refund_amount: Optional[float] = None
    policy_references: list[str] = field(default_factory=list)

    # Escalation context
    escalation_reason: EscalationReason = EscalationReason.UNABLE_TO_PROGRESS
    urgency: UrgencyLevel = UrgencyLevel.NORMAL
    customer_sentiment: str = "neutral"
    additional_context: str = ""

    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    session_duration_turns: int = 0

    def to_text(self) -> str:
        """
        Format for the escalate_to_human tool call.
        Human agent reads this directly — must be clear and self-contained.
        """
        lines = [
            "=" * 65,
            "ESCALATION HANDOFF SUMMARY",
            f"Generated: {self.created_at}",
            "=" * 65,
            "",
            "── CUSTOMER IDENTITY ──────────────────────────────────",
            f"Verified Customer ID : {self.verified_customer_id}",
            f"Name                 : {self.customer_name}",
            f"Email                : {self.customer_email}",
            f"Account Tier         : {self.customer_tier}",
            "",
            "── ISSUES ─────────────────────────────────────────────",
        ]

        for i, issue in enumerate(self.issues, 1):
            lines += [
                f"Issue {i}: {issue.issue_type.replace('_', ' ').title()}",
                f"  Order ID    : {issue.order_id or 'N/A'}",
                f"  Description : {issue.description}",
                f"  Root Cause  : {issue.root_cause}",
                f"  Evidence    : {issue.evidence}",
                "",
            ]

        lines += [
            "── ACTIONS ALREADY TAKEN ──────────────────────────────",
        ]
        for action in self.actions_taken:
            status = "✓" if action.succeeded else "✗"
            lines.append(
                f"  {status} {action.tool_name}({json.dumps(action.inputs)[:50]})"
                f" → {action.result_summary[:60]}"
            )

        lines += [
            "",
            "── RECOMMENDED ACTION ─────────────────────────────────",
            f"  {self.recommended_action}",
        ]

        if self.refund_amount is not None:
            lines.append(f"  Refund Amount: ${self.refund_amount:.2f}")

        if self.policy_references:
            lines.append("  Policy Refs: " + ", ".join(self.policy_references))

        lines += [
            "",
            "── ESCALATION CONTEXT ─────────────────────────────────",
            f"  Reason   : {self.escalation_reason.value.replace('_', ' ')}",
            f"  Urgency  : {self.urgency.value.upper()}",
            f"  Sentiment: {self.customer_sentiment}",
        ]

        if self.additional_context:
            lines.append(f"  Notes    : {self.additional_context}")

        lines.append("=" * 65)

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Serialise for storage or downstream processing."""
        return {
            "verified_customer_id": self.verified_customer_id,
            "customer_name": self.customer_name,
            "customer_email": self.customer_email,
            "customer_tier": self.customer_tier,
            "issues": [
                {
                    "issue_type": i.issue_type,
                    "order_id": i.order_id,
                    "description": i.description,
                    "root_cause": i.root_cause,
                    "evidence": i.evidence,
                }
                for i in self.issues
            ],
            "actions_taken": [
                {
                    "tool": a.tool_name,
                    "inputs": a.inputs,
                    "result": a.result_summary,
                    "succeeded": a.succeeded,
                }
                for a in self.actions_taken
            ],
            "recommended_action": self.recommended_action,
            "refund_amount": self.refund_amount,
            "escalation_reason": self.escalation_reason.value,
            "urgency": self.urgency.value,
            "created_at": self.created_at,
        }


# ══════════════════════════════════════════════════════════════════
# SECTION 2: HANDOFF BUILDER (LLM-ASSISTED)
# ══════════════════════════════════════════════════════════════════

def build_handoff_with_ai(
    conversation_context: str,
    tool_call_log: list[dict],
    escalation_reason: EscalationReason,
    urgency: UrgencyLevel = UrgencyLevel.NORMAL,
) -> str:
    """
    Uses Claude to extract a structured handoff summary from
    the conversation context and tool call log.

    This is the LLM-assisted handoff pattern — the agent compiles
    its own work into a structured format for the human.
    """

    tool_log_formatted = "\n".join(
        f"- {entry['tool']}({entry.get('inputs', {})}) → {entry.get('result', 'N/A')}"
        for entry in tool_call_log
    )

    prompt = f"""You are compiling a structured handoff summary for a human support agent.
The human agent has NO access to the conversation transcript.
They need EVERYTHING to continue the case without re-investigating.

CONVERSATION CONTEXT:
{conversation_context}

TOOLS CALLED AND RESULTS:
{tool_log_formatted}

ESCALATION REASON: {escalation_reason.value}

Generate a structured handoff summary with EXACTLY these sections:
1. CUSTOMER IDENTITY (verified customer ID, name, email, tier)
2. ISSUES (for each: issue type, order ID, description, root cause, evidence)
3. ACTIONS TAKEN (what was done, what was found)
4. RECOMMENDED ACTION (specific next step for human agent, with dollar amount if relevant)
5. WHY ESCALATING (reason this couldn't be resolved autonomously)

Be specific. Include all relevant IDs, amounts, and dates.
Do not summarise — include the full detail the human agent needs."""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text


# ══════════════════════════════════════════════════════════════════
# SECTION 3: MULTI-CONCERN DECOMPOSITION
# ══════════════════════════════════════════════════════════════════

@dataclass
class ConcernItem:
    concern_id: str
    concern_type: str          # "damaged_goods", "billing_dispute", "cancellation"
    description: str
    order_id: Optional[str]
    tools_needed: list[str]   # which tools to call for this concern


def decompose_customer_request(customer_message: str) -> list[ConcernItem]:
    """
    Identify distinct concern items in a customer message.
    Each concern is independent and can be investigated in parallel.

    Example input:
      "My order ORD-5501 arrived damaged, I was double-charged for ORD-5502,
       and I want to cancel my subscription."

    Example output:
      [
        ConcernItem("c1", "damaged_goods", ..., "ORD-5501", [...]),
        ConcernItem("c2", "billing_dispute", ..., "ORD-5502", [...]),
        ConcernItem("c3", "cancellation_request", ..., None, [...]),
      ]
    """
    prompt = f"""Analyse this customer support message and identify each distinct concern.

Customer message: "{customer_message}"

Return ONLY a JSON array. Each item must have:
  - concern_id: "c1", "c2", etc.
  - concern_type: one of [damaged_goods, billing_dispute, duplicate_charge,
                           cancellation_request, missing_order, account_issue]
  - description: brief description of this specific concern
  - order_id: the order ID if mentioned, or null
  - tools_needed: list of tools from [get_customer, lookup_order, check_policy,
                                        process_refund, escalate_to_human]

Example:
[
  {{"concern_id": "c1", "concern_type": "damaged_goods",
    "description": "Order ORD-5501 arrived damaged",
    "order_id": "ORD-5501",
    "tools_needed": ["lookup_order", "check_policy", "process_refund"]}}
]"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text
    start = raw.find("[")
    end = raw.rfind("]") + 1

    if start == -1:
        return []

    try:
        items = json.loads(raw[start:end])
        return [
            ConcernItem(
                concern_id=item["concern_id"],
                concern_type=item["concern_type"],
                description=item["description"],
                order_id=item.get("order_id"),
                tools_needed=item.get("tools_needed", []),
            )
            for item in items
        ]
    except (json.JSONDecodeError, KeyError):
        return []


def investigate_concern(
    concern: ConcernItem,
    verified_customer_id: str,
    customer_name: str,
) -> dict:
    """
    Investigate a single concern item.
    Uses a focused subagent with only the tools needed for this concern.
    Receives the shared verified_customer_id — verified once, used everywhere.
    """

    # Build a focused investigation prompt
    investigation_prompt = f"""You are investigating a customer support concern.

Customer: {customer_name} (verified ID: {verified_customer_id})
Concern Type: {concern.concern_type}
Description: {concern.description}
Order ID: {concern.order_id or "N/A"}

Available tools for this investigation: {concern.tools_needed}

Investigate this concern thoroughly and return your findings as JSON:
{{
  "concern_id": "{concern.concern_id}",
  "root_cause": "what you determined",
  "evidence": "specific data points from tool results",
  "policy_status": "eligible/ineligible/escalation_required",
  "recommended_resolution": "specific action",
  "refund_amount": number_or_null,
  "can_resolve_autonomously": true_or_false,
  "reason_if_not": "why escalation needed if applicable"
}}"""

    # Simulate investigation (in production, this would use actual tools)
    investigation_results = {
        "damaged_goods": {
            "concern_id": concern.concern_id,
            "root_cause": "Order delivered with visible damage per carrier report",
            "evidence": "Delivery scan shows damaged package. Order total: $149.99",
            "policy_status": "eligible",
            "recommended_resolution": "Full refund of $149.99",
            "refund_amount": 149.99,
            "can_resolve_autonomously": True,
            "reason_if_not": None,
        },
        "duplicate_charge": {
            "concern_id": concern.concern_id,
            "root_cause": "Payment processor error created duplicate transaction",
            "evidence": "Two identical charges of $89.99 on 2024-11-03",
            "policy_status": "eligible",
            "recommended_resolution": "Refund duplicate charge of $89.99",
            "refund_amount": 89.99,
            "can_resolve_autonomously": True,
            "reason_if_not": None,
        },
        "cancellation_request": {
            "concern_id": concern.concern_id,
            "root_cause": "Customer wishes to cancel subscription",
            "evidence": "Active subscription since 2023-08. No cancellation penalties.",
            "policy_status": "eligible",
            "recommended_resolution": "Cancel subscription effective end of billing period",
            "refund_amount": None,
            "can_resolve_autonomously": True,
            "reason_if_not": None,
        },
    }

    return investigation_results.get(
        concern.concern_type,
        {
            "concern_id": concern.concern_id,
            "root_cause": "Unable to determine",
            "evidence": "Insufficient data",
            "policy_status": "escalation_required",
            "recommended_resolution": "Refer to Tier-2 support",
            "refund_amount": None,
            "can_resolve_autonomously": False,
            "reason_if_not": "Policy gap or complex case",
        },
    )


def resolve_multi_concern_request(
    customer_message: str,
    verified_customer_id: str,
    customer_name: str,
) -> dict:
    """
    Full multi-concern resolution flow:
    1. Decompose into distinct concerns
    2. Investigate each in PARALLEL (shared verified_customer_id)
    3. Synthesise unified resolution

    Key: verification happens ONCE, shared context flows to all concerns.
    """

    print(f"\n{'─'*60}")
    print("MULTI-CONCERN DECOMPOSITION")
    print(f"{'─'*60}")

    # Step 1: Decompose
    concerns = decompose_customer_request(customer_message)
    print(f"Identified {len(concerns)} distinct concern(s):")
    for c in concerns:
        print(f"  {c.concern_id}: {c.concern_type} (order: {c.order_id or 'N/A'})")

    # Step 2: Investigate in parallel (same verified_customer_id for all)
    print(f"\nInvestigating all concerns in parallel...")
    print(f"(shared verified_customer_id: {verified_customer_id})")

    investigation_results = {}
    for concern in concerns:
        result = investigate_concern(concern, verified_customer_id, customer_name)
        investigation_results[concern.concern_id] = result
        status = "✓ auto-resolve" if result["can_resolve_autonomously"] else "⚠ escalate"
        print(f"  {concern.concern_id}: {status} — {result['recommended_resolution']}")

    # Step 3: Synthesise into unified resolution
    print("\nSynthesising unified resolution...")

    total_refund = sum(
        r.get("refund_amount", 0) or 0
        for r in investigation_results.values()
    )

    escalation_needed = any(
        not r["can_resolve_autonomously"]
        for r in investigation_results.values()
    )

    resolution_summary = {
        "concerns_resolved": len([r for r in investigation_results.values() if r["can_resolve_autonomously"]]),
        "concerns_total": len(concerns),
        "total_refund_amount": total_refund,
        "escalation_needed": escalation_needed,
        "individual_resolutions": investigation_results,
    }

    return resolution_summary


# ══════════════════════════════════════════════════════════════════
# SECTION 4: ESCALATION TRIGGER LOGIC
# ══════════════════════════════════════════════════════════════════

def evaluate_escalation_trigger(
    customer_message: str,
    agent_can_resolve: bool,
    policy_coverage: str,  # "covered", "gap", "ambiguous"
    progress_made: bool,
) -> tuple[bool, EscalationReason]:
    """
    Evaluate whether to escalate and why.

    Exam key points:
    - Customer explicit request → escalate IMMEDIATELY, no investigation
    - Policy gap → escalate (don't invent policy decisions)
    - Unable to progress → escalate with full context
    - Sentiment alone → NOT sufficient trigger
    - Low confidence → NOT sufficient trigger
    """

    # Rule 1: Explicit human request — highest priority
    human_request_phrases = [
        "speak to a human",
        "speak to a person",
        "talk to someone",
        "want a human",
        "need a person",
        "escalate",
        "manager",
        "supervisor",
    ]
    if any(phrase in customer_message.lower() for phrase in human_request_phrases):
        return True, EscalationReason.CUSTOMER_REQUESTED

    # Rule 2: Policy gap — don't make autonomous decisions outside policy
    if policy_coverage in ("gap", "ambiguous"):
        return True, EscalationReason.POLICY_GAP

    # Rule 3: Cannot resolve autonomously
    if not agent_can_resolve:
        if not progress_made:
            return True, EscalationReason.UNABLE_TO_PROGRESS

    # No escalation needed
    return False, None


# ══════════════════════════════════════════════════════════════════
# SECTION 5: COMPLETE DEMO
# ══════════════════════════════════════════════════════════════════

def demo_complete_handoff():
    """
    Demonstrates a complete handoff scenario:
    customer asks for a human → immediate escalation with structured summary.
    """
    print("\n" + "="*70)
    print("DEMO: Complete Structured Handoff")
    print("="*70)

    # Build handoff for a scenario where customer requests a human
    handoff = HandoffSummary(
        verified_customer_id="VER-C10023",
        customer_name="Alice Johnson",
        customer_email="alice@example.com",
        customer_tier="Gold",
        issues=[
            IssueDetail(
                issue_type="damaged_goods",
                order_id="ORD-5501",
                description="Wireless headphones arrived crushed in box",
                root_cause="Carrier damage — package scan shows damaged at hub",
                evidence="Delivery record shows 'damaged' flag. Order value: $149.99",
            ),
            IssueDetail(
                issue_type="duplicate_charge",
                order_id="ORD-5502",
                description="Charged twice for the same order",
                root_cause="Payment processor submitted transaction twice on 2024-11-03",
                evidence="Two identical $89.99 charges on credit card statement",
            ),
        ],
        actions_taken=[
            ActionTaken("get_customer", {"identifier": "C10023"},
                        "Verified: Alice Johnson, Gold tier", True),
            ActionTaken("lookup_order", {"order_id": "ORD-5501"},
                        "Status: delivered, $149.99, damage_claim_eligible=True", True),
            ActionTaken("lookup_order", {"order_id": "ORD-5502"},
                        "Status: delivered, $89.99, duplicate_charge=True", True),
            ActionTaken("check_policy", {"policy_type": "damage_claim"},
                        "Eligible for full refund up to $500", True),
            ActionTaken("process_refund", {"order_id": "ORD-5501", "amount": 149.99},
                        "Blocked: customer requested human agent mid-investigation", False),
        ],
        recommended_action=(
            "Process refund of $149.99 for ORD-5501 (damage claim, policy confirmed). "
            "Also process refund of $89.99 for ORD-5502 (duplicate charge confirmed). "
            "Total refund: $239.98. Both within $500 per-transaction limit."
        ),
        refund_amount=239.98,
        policy_references=["damage_claim policy: full refund within 30 days",
                            "duplicate_charge policy: automatic refund approved"],
        escalation_reason=EscalationReason.CUSTOMER_REQUESTED,
        urgency=UrgencyLevel.HIGH,
        customer_sentiment="frustrated",
        additional_context="Gold tier customer with 47 orders — high value relationship",
        session_duration_turns=6,
    )

    print("\nFormatted handoff for human agent:")
    print(handoff.to_text())


def demo_multi_concern():
    """Demonstrates multi-concern parallel investigation."""
    print("\n" + "="*70)
    print("DEMO: Multi-Concern Parallel Investigation")
    print("="*70)

    customer_message = (
        "Hi, order ORD-5501 arrived damaged, I was also double-charged "
        "for ORD-5502, and I'd like to cancel my subscription. Can you help?"
    )

    result = resolve_multi_concern_request(
        customer_message=customer_message,
        verified_customer_id="VER-C10023",
        customer_name="Alice Johnson",
    )

    print("\nUnified resolution:")
    print(f"  Concerns total    : {result['concerns_total']}")
    print(f"  Auto-resolved     : {result['concerns_resolved']}")
    print(f"  Total refund      : ${result['total_refund_amount']:.2f}")
    print(f"  Escalation needed : {result['escalation_needed']}")


def demo_escalation_triggers():
    """Demonstrates the three correct escalation triggers."""
    print("\n" + "="*70)
    print("DEMO: Escalation Trigger Evaluation")
    print("="*70)

    test_cases = [
        {
            "message": "I want to speak to a human agent please",
            "agent_can_resolve": True,
            "policy_coverage": "covered",
            "progress": True,
            "expected": (True, EscalationReason.CUSTOMER_REQUESTED),
        },
        {
            "message": "I want a competitor price match",
            "agent_can_resolve": False,
            "policy_coverage": "gap",
            "progress": False,
            "expected": (True, EscalationReason.POLICY_GAP),
        },
        {
            "message": "My order is damaged, I need a refund",
            "agent_can_resolve": True,
            "policy_coverage": "covered",
            "progress": True,
            "expected": (False, None),
        },
        {
            "message": "I'm very angry about this!",   # Sentiment alone
            "agent_can_resolve": True,
            "policy_coverage": "covered",
            "progress": True,
            "expected": (False, None),   # Sentiment alone is NOT a trigger
        },
    ]

    for case in test_cases:
        should_escalate, reason = evaluate_escalation_trigger(
            case["message"],
            case["agent_can_resolve"],
            case["policy_coverage"],
            case["progress"],
        )
        expected_escalate, expected_reason = case["expected"]
        match = should_escalate == expected_escalate
        status = "✓" if match else "✗"

        print(f"\n{status} '{case['message'][:50]}'")
        print(f"  Escalate: {should_escalate}, Reason: {reason}")
        if not match:
            print(f"  Expected: {expected_escalate}, {expected_reason}")


if __name__ == "__main__":
    demo_complete_handoff()
    demo_multi_concern()
    demo_escalation_triggers()
