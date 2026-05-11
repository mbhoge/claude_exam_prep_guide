# Task 1.4 – Multi-Step Workflows with Enforcement and Handoff Patterns

> **Exam Domain**: Domain 1 — Agentic Architecture & Orchestration (27%)  
> **Scenario**: Customer Support Resolution Agent (Scenario 1)  
> **Sample Questions tested**: Q1, Q3  
> **Code**: [`multi_step_workflows.py`](./multi_step_workflows.py) | [`enforcement_patterns.py`](./enforcement_patterns.py) | [`handoff_protocols.py`](./handoff_protocols.py)

---

## The Core Problem This Task Solves

Complex agentic workflows involve steps that **must happen in a specific order** — not because we prefer it, but because safety, security, or business rules **require** it. The exam tests your ability to choose between two fundamentally different enforcement mechanisms and know when each is appropriate.

---

## 1. Programmatic Enforcement vs Prompt-Based Guidance

### The Fundamental Distinction

```
PROMPT-BASED GUIDANCE                    PROGRAMMATIC ENFORCEMENT
─────────────────────────                ────────────────────────────
"Always verify the customer              Code blocks tool B from
 before processing a refund"             executing until tool A returns
                                         a verified result
       ↓                                        ↓
  Claude reads the instruction            The runtime physically
  and usually follows it                  prevents the call
       ↓                                        ↓
  In ~12% of cases, it                   Zero bypasses —
  skips it (Q1 scenario)                 impossible to skip
```

### Why Prompts Fail for Critical Ordering

The model is a probabilistic text predictor. When a customer volunteers their order ID (`"My order is #12345, I need a refund"`), the model may reason:

> *"I have the order ID — I can call `lookup_order` directly. This is efficient."*

This is valid reasoning from the model's perspective — but it bypasses the identity verification step required for financial security. This is **exactly the failure mode in Sample Question 1** (12% bypass rate).

### Decision Rule: When to Use Each

```
Is this ordering rule a BUSINESS REQUIREMENT or a PREFERENCE?
      │
      ├─► PREFERENCE (e.g., "search before summarising")
      │        → Prompt-based guidance is fine
      │        → Model may reorder based on context
      │        → Acceptable: probabilistic compliance
      │
      └─► REQUIREMENT (e.g., "verify identity before financial ops")
               → Programmatic enforcement ONLY
               → Prompt instructions alone = non-zero failure rate
               → NOT acceptable: any bypass has consequences
```

**Requirements that demand programmatic enforcement:**
- Identity verification before financial transactions
- Consent/terms acceptance before data processing
- Age verification before restricted content
- Authorization checks before privileged actions
- Audit logging before irreversible operations

---

## 2. Enforcement Mechanisms

### Mechanism 1: Prerequisite Gate (State-Based)

A gate checks whether a prerequisite state has been achieved before allowing a tool to execute. State is maintained in the workflow object, not in the prompt.

```
 State: verified_customer_id = None
              │
              ▼
 Tool call: process_refund(order_id, amount)
              │
              ▼
 Gate checks: verified_customer_id is None?
              │              │
              ▼              ▼
         BLOCKED          ALLOWED
    "Call get_customer     (if verified_customer_id
       first"              was set by prior call)
```

**Key**: The gate lives in the **runtime**, not in the prompt. It cannot be bypassed by clever phrasing.

### Mechanism 2: PostToolUse Hook (Interception-Based)

A hook fires after a tool returns and can:
1. Transform the result before the model sees it (data normalisation)
2. Block the result and redirect the flow (policy enforcement)

```
 Tool: process_refund → returns {"amount": 750}
              │
              ▼
 PostToolUse Hook fires
              │
              ▼
 Check: amount > $500 threshold?
              │              │
              YES             NO
              │               │
              ▼               ▼
    Block result          Pass through
    Return escalation     model sees
    instruction           original result
```

### Mechanism 3: Tool Restriction (Access-Based)

Limit the tools available to an agent role. A subagent that doesn't have `process_refund` in its `allowedTools` simply cannot call it — no gate needed.

```python
# Coordinator allowedTools includes all tools
coordinator_tools = ["get_customer", "lookup_order", "process_refund", "escalate_to_human"]

# Triage subagent can only read, never write
triage_tools = ["get_customer", "lookup_order"]

# Finance subagent requires pre-verified context
finance_tools = ["process_refund"]   # blocked without verified_customer_id
```

---

## 3. Structured Handoff Protocols

### Why Handoffs Fail Without Structure

When an agent escalates to a human, the human agent typically:
- Has **no access to the conversation transcript**
- Must **start from scratch** if the handoff is unstructured
- Has no idea what was already tried
- Cannot make informed decisions without the prior context

An unstructured escalation like *"customer needs help"* destroys all the work the agent did.

### The Structured Handoff Components

Every escalation must include:

```
┌─────────────────────────────────────────────┐
│            STRUCTURED HANDOFF               │
├─────────────────────────────────────────────┤
│ 1. Customer Identity                        │
│    - Verified customer ID                   │
│    - Name, account tier, contact info       │
│    - Account history summary                │
├─────────────────────────────────────────────┤
│ 2. Issue Details                            │
│    - Order ID(s) affected                   │
│    - Issue type (return, billing, account)  │
│    - Date reported                          │
├─────────────────────────────────────────────┤
│ 3. Root Cause Analysis                      │
│    - What the agent determined              │
│    - Evidence gathered                      │
│    - Data that supports or contradicts      │
├─────────────────────────────────────────────┤
│ 4. Actions Already Taken                    │
│    - Tools called and results               │
│    - Policies checked                       │
│    - What was attempted                     │
├─────────────────────────────────────────────┤
│ 5. Recommended Action                       │
│    - What the human agent should do next    │
│    - Dollar amount if refund needed         │
│    - Specific policy reference if relevant  │
├─────────────────────────────────────────────┤
│ 6. Escalation Reason & Urgency              │
│    - Why it couldn't be resolved            │
│    - Customer sentiment                     │
│    - Time sensitivity                       │
└─────────────────────────────────────────────┘
```

### When to Escalate

The exam tests three specific escalation triggers:

| Trigger | Action | Wrong Alternative |
|---------|--------|-------------------|
| Customer explicitly requests a human | Escalate **immediately** — do not attempt investigation first | ❌ Trying to resolve first anyway |
| Policy gap or exception | Escalate — autonomous action outside policy is risky | ❌ Making up a policy decision |
| Unable to make meaningful progress | Escalate with what was attempted | ❌ Looping indefinitely |

**Key exam insight**: Sentiment-based escalation (escalate when customer seems angry) is **NOT a reliable proxy** for case complexity. An angry customer with a simple issue should be resolved, not escalated.

---

## 4. Multi-Concern Request Decomposition

### The Problem

A single customer message often contains **multiple distinct issues**:

> *"My order #12345 arrived damaged AND I was double-charged for order #12346 AND I want to cancel my subscription"*

A naive agent handles these sequentially, wasting time and losing context between each one.

### The Pattern: Parallel Investigation with Shared Context

```
Customer Message: "Damaged order + double charge + cancel subscription"
        │
        ▼
Coordinator decomposes into 3 distinct items
        │
        ├──────────────────────────────────┐──────────────────────────┐
        ▼                                  ▼                          ▼
Issue 1: Damaged order           Issue 2: Double charge      Issue 3: Subscription
  - lookup_order(#12345)           - lookup_order(#12346)      - get_subscription()
  - check_damage_policy()          - check_billing()           - check_cancel_policy()
  - assess refund/replace          - check duplicate charge    - check penalties
        │                                  │                          │
        └──────────────────────────────────┴──────────────────────────┘
                                           │
                                           ▼
                                  Coordinator aggregates
                                  all findings into
                                  UNIFIED resolution
                                           │
                                           ▼
                              Single coherent response
                              addressing all 3 issues
```

**Why parallel?** Each sub-investigation is **independent** — the damage claim doesn't depend on the billing inquiry result. Parallel execution reduces total latency.

**Shared context**: The verified customer ID from `get_customer` is shared across all three sub-investigations. It's verified once, used everywhere.

---

## 5. Anti-Patterns (Exam Traps)

| Anti-Pattern | Why It Fails | Correct Approach |
|---|---|---|
| `"Always verify customer first"` in system prompt only | Non-zero failure rate (~12% per Q1) | Programmatic prerequisite gate |
| Few-shot examples showing correct ordering | Still probabilistic — model can deviate | Programmatic gate; few-shot is a distractor in Q1 |
| Routing classifier to limit tool access | Addresses tool availability, not ordering — Q1 distractor D | State-based gates enforce ordering |
| Sentiment threshold for escalation | Sentiment ≠ complexity | Explicit categorical criteria |
| Unstructured escalation ("needs help") | Human has no context | Structured handoff with all 6 components |
| Sequential multi-concern handling | Slow; context shifts between concerns | Parallel investigation, unified synthesis |
| Escalating before attempting resolution | Wastes human capacity on solvable cases | Attempt resolution; escalate on explicit request or policy gap |

---

## 6. Sample Question Analysis

### Q1 — The Canonical Enforcement Question

> Production data shows that in 12% of cases, your agent skips `get_customer` entirely and calls `lookup_order` using only the customer's stated name, leading to misidentified accounts and incorrect refunds. What change would most effectively address this?

**Why each answer is right/wrong:**

| Option | Assessment | Reasoning |
|--------|-----------|-----------|
| A) Programmatic prerequisite blocking `lookup_order` until `get_customer` returns verified ID | ✅ **CORRECT** | Deterministic — impossible to bypass |
| B) Enhanced system prompt making verification "mandatory" | ❌ Wrong | Still probabilistic — this IS the approach that's already failing |
| C) Few-shot examples showing `get_customer` first | ❌ Wrong | Still probabilistic — improves but doesn't eliminate bypass |
| D) Routing classifier that limits tool subset per request | ❌ Wrong | Solves wrong problem — tool availability ≠ tool ordering |

### Q3 — Escalation Calibration

> Agent achieves 55% FCR vs 80% target. It escalates straightforward cases while autonomously handling complex ones. Most effective fix?

| Option | Assessment | Reasoning |
|--------|-----------|-----------|
| A) Explicit escalation criteria + few-shot examples | ✅ **CORRECT** | Directly addresses unclear decision boundaries — the root cause |
| B) Self-reported confidence score threshold | ❌ Wrong | LLM confidence scores are poorly calibrated — already wrong on hard cases |
| C) Separate classifier trained on historical tickets | ❌ Wrong | Over-engineered — prompt optimization hasn't been tried yet |
| D) Sentiment-based escalation threshold | ❌ Wrong | Solves wrong problem — sentiment ≠ case complexity |

---

## 7. Key Takeaways for the Exam

1. **Programmatic > Prompt for critical ordering**: Any step that must ALWAYS happen before another step requires code-level enforcement, not prompt instructions.

2. **Hooks = deterministic; prompts = probabilistic**: When the exam asks about "guaranteed compliance," the answer involves hooks or gates, never prompts alone.

3. **Structured handoffs preserve agent work**: Every escalation should carry the full context a human needs to continue without re-investigating.

4. **Parallel investigation, unified synthesis**: Multi-concern requests are decomposed, investigated in parallel with shared verification context, then synthesised once.

5. **Escalation triggers are categorical, not sentiment-based**: Explicit customer request, policy gap, or inability to progress — not frustration level or confidence score.

6. **The escalation timing rule**: Customer explicitly requests a human → escalate immediately, no investigation. Agent can't resolve it → escalate with full context of what was tried.

---

## 8. Files in This Folder

| File | Purpose |
|------|---------|
| `README.md` | Conceptual guide (this file) |
| `multi_step_workflows.py` | Core implementation: gates, hooks, full customer support agent loop |
| `enforcement_patterns.py` | Side-by-side: prompt-based vs programmatic enforcement with failure demo |
| `handoff_protocols.py` | Structured handoff builder + multi-concern parallel decomposition |
