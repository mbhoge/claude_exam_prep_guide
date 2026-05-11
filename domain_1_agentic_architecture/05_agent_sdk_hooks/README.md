# Task 1.5 – Agent SDK Hooks for Tool Call Interception

## What This Topic Covers

Agent SDK hooks are **middleware callbacks** injected at specific points in the
agentic tool-call lifecycle. They provide a deterministic interception layer that
runs *regardless of what the model reasons*, giving you:

- **PreToolUse** – intercepts the outgoing tool call *before* the tool executes
- **PostToolUse** – intercepts the tool result *after* execution, *before* the
  model processes it

---

## Hook Lifecycle Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     AGENTIC LOOP                            │
│                                                             │
│  Claude Model                                               │
│      │                                                      │
│      │  tool_use block                                      │
│      ▼                                                      │
│  ┌──────────────────────────────────┐                       │
│  │   PreToolUse Hook(s)             │  ◄── intercept HERE   │
│  │   • Inspect tool_name + inputs  │     to BLOCK or ALLOW │
│  │   • Block policy violations     │                       │
│  │   • Redirect to alt workflow    │                       │
│  └──────────────┬───────────────────┘                       │
│                 │  (if not blocked)                         │
│                 ▼                                           │
│  ┌──────────────────────────────────┐                       │
│  │   Actual Tool / MCP Server       │                       │
│  └──────────────┬───────────────────┘                       │
│                 │  raw result                               │
│                 ▼                                           │
│  ┌──────────────────────────────────┐                       │
│  │   PostToolUse Hook(s)            │  ◄── intercept HERE   │
│  │   • Transform / normalize data  │     to TRANSFORM      │
│  │   • Unify timestamp formats     │     before model sees │
│  │   • Convert status codes        │     the result        │
│  └──────────────┬───────────────────┘                       │
│                 │  normalized result                        │
│                 ▼                                           │
│  Claude Model (sees clean, unified data)                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. PostToolUse Hooks — Data Normalization

### The Problem

Real deployments connect multiple MCP servers. Each server returns data in its
own format:

| Source System     | Timestamp Format         | Status Representation    |
|-------------------|--------------------------|--------------------------|
| Legacy CRM        | Unix epoch (`1715000000`)| Numeric code (`1`, `3`)  |
| Modern ERP        | ISO 8601 (`2024-05-06T…`)| String (`"active"`)      |
| Payment Gateway   | RFC 2822 (`Mon, 06 May…`)| Boolean (`true`/`false`) |

If the model sees three different formats for the same concept, it must reason
about format differences before it can reason about the actual data. This burns
context tokens, introduces parsing errors, and creates non-deterministic
behaviour across sessions.

### The Solution: PostToolUse Normalization Hook

A PostToolUse hook intercepts **every tool result** from every MCP server and
converts it to a single canonical schema before the model ever sees it.

```python
def normalize_tool_result(tool_name: str, raw_result: dict) -> dict:
    """PostToolUse hook: canonicalize heterogeneous MCP responses."""

    # Normalize timestamps → ISO 8601 UTC
    if "created_at" in raw_result:
        raw_result["created_at"] = to_iso8601(raw_result["created_at"])
    if "updated_at" in raw_result:
        raw_result["updated_at"] = to_iso8601(raw_result["updated_at"])

    # Normalize status codes → human-readable strings
    if "status" in raw_result and isinstance(raw_result["status"], int):
        raw_result["status"] = STATUS_CODE_MAP.get(
            raw_result["status"], f"unknown_{raw_result['status']}"
        )

    return raw_result
```

### Why this is better than prompting the model to "handle various formats"

| Approach | Reliability | Token Cost | Debuggability |
|---|---|---|---|
| Prompt: "data may be epoch or ISO, convert as needed" | Probabilistic (model may mis-parse) | High (reasoning each time) | Poor |
| PostToolUse normalization hook | Deterministic (always runs) | Zero model tokens | Excellent (one place to fix) |

---

## 2. PreToolUse Hooks — Compliance Enforcement

### The Problem

Business rules like "never process a refund above $500" are **policy constraints**,
not model reasoning hints. If expressed only in the prompt:

```
# FRAGILE — prompt-only enforcement
SYSTEM: Do not process refunds above $500. For higher amounts, escalate.
```

The model may:
- Override the instruction when it "understands" the customer needs it
- Forget the constraint in a long conversation (lost-in-middle effect)
- Process two $300 refunds for the same order (split-refund bypass)

### The Solution: PreToolUse Compliance Hook

A PreToolUse hook runs **before** the tool executes. If the hook rejects the
call, the tool never runs and the model receives an error result explaining
what it must do instead.

```python
def enforce_refund_policy(tool_name: str, inputs: dict) -> dict | None:
    """
    PreToolUse hook: block policy-violating refunds.
    Returns None to allow, or a rejection dict to block.
    """
    if tool_name == "process_refund":
        amount = inputs.get("amount", 0)
        if amount > 500:
            return {
                "blocked": True,
                "reason": f"Refund of ${amount:.2f} exceeds $500 policy limit.",
                "required_action": "Call escalate_to_human with a human_review request.",
                "escalation_type": "high_value_refund",
            }
    return None  # allow
```

### Redirection to Alternative Workflows

When a PreToolUse hook blocks an action, the agent must still resolve the user's
request. The hook's return value includes `required_action` — an instruction the
model reads and acts on, directing it to the approved alternative:

```
Blocked call:   process_refund(amount=750)
Hook response:  {"blocked": true, "required_action": "Call escalate_to_human"}
Model next act: escalate_to_human(reason="high_value_refund", amount=750)
```

This redirection is part of the deterministic guarantee: not only is the
bad path blocked, but the correct path is specified.

---

## 3. Hooks vs Prompt Instructions — The Core Exam Distinction

This is the most frequently tested concept in this domain.

### Probabilistic Compliance (Prompt-Based)

```
Model receives instruction → Model interprets instruction → Model decides to follow/skip
```

- Failure rate: ~5-15% at scale depending on context complexity
- Failure mode: "The customer urgently needs $750, policy allows exceptions..."
- At 10,000 transactions/day: 500–1,500 policy violations per day

### Deterministic Compliance (Hook-Based)

```
Tool call intercepted → Hook evaluates rule → Block or allow (no model involvement)
```

- Failure rate: 0% (the model is not in the decision path)
- Failure mode: none — the code either runs or it doesn't
- The model cannot reason around a hook any more than it can reason around a firewall

### When to Use Each

| Enforcement Type | Use Hooks | Use Prompts |
|---|---|---|
| Financial thresholds | YES — never prompt | No |
| Step ordering (A before B) | YES — never prompt | No |
| Data format normalization | YES — never prompt | No |
| Tone / style preferences | No | YES |
| Content suggestions | No | YES |
| "Try to" / "prefer to" rules | No | YES |

**Rule of thumb:** If a violation would cause a real-world negative consequence
(financial loss, data breach, compliance failure), use a hook. If it would
produce a suboptimal but recoverable output, a prompt is acceptable.

---

## 4. Implementation Architecture

### HookManager

The recommended pattern is a `HookManager` that separates hook registration
from the agentic loop:

```python
class HookManager:
    def __init__(self):
        self._pre_hooks: list[Callable] = []
        self._post_hooks: list[Callable] = []

    def register_pre(self, fn): self._pre_hooks.append(fn)
    def register_post(self, fn): self._post_hooks.append(fn)

    def run_pre(self, tool_name, inputs) -> dict | None:
        for hook in self._pre_hooks:
            result = hook(tool_name, inputs)
            if result is not None:          # first hook to block wins
                return result
        return None

    def run_post(self, tool_name, inputs, raw_result) -> dict:
        result = raw_result
        for hook in self._post_hooks:
            result = hook(tool_name, inputs, result)
        return result
```

### Integration in the Agentic Loop

```python
def execute_tool_with_hooks(tool_name, inputs, hooks: HookManager):
    # 1. PreToolUse — may block
    block = hooks.run_pre(tool_name, inputs)
    if block:
        return block                        # model sees block message, not tool result

    # 2. Execute actual tool
    raw_result = dispatch_tool(tool_name, inputs)

    # 3. PostToolUse — normalize
    return hooks.run_post(tool_name, inputs, raw_result)
```

---

## 5. Claude Code Hooks (settings.json)

In Claude Code (the CLI), hooks are configured in `.claude/settings.json` as
shell commands. The same two lifecycle points exist:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "python validate_bash_command.py" }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "mcp__crm__get_customer",
        "hooks": [
          { "type": "command", "command": "python normalize_crm_output.py" }
        ]
      }
    ]
  }
}
```

- A PreToolUse hook that exits non-zero **blocks** the tool call
- A PostToolUse hook receives the result on stdin and can rewrite it on stdout

---

## 6. Exam Question Patterns

### Pattern 1: "Which approach *guarantees* compliance?"

Answer is always **hook/programmatic enforcement**, never "strengthen the prompt"
or "add few-shot examples". Prompts improve probability; hooks guarantee.

### Pattern 2: "Multiple MCP servers return different timestamp formats…"

Answer: **PostToolUse normalization hook** that converts all timestamps to a
canonical format before the model processes the result.

### Pattern 3: "Refund above $500 should go to human review…"

Answer: **PreToolUse hook** that intercepts `process_refund`, checks the
`amount` field, blocks if over threshold, and returns `required_action` pointing
to `escalate_to_human`.

### Pattern 4: "Why use a hook instead of a prompt instruction?"

Answer: Hooks provide **deterministic** enforcement. The model is not in the
decision path. Prompt instructions are **probabilistic** — the model may deviate
when reasoning suggests an exception is warranted.

---

## Files in This Folder

| File | What It Demonstrates |
|---|---|
| `README.md` | This guide — concepts, patterns, exam tips |
| `agent_sdk_hooks.py` | Full working implementation: HookManager, data normalization, compliance enforcement, agentic loop integration |
