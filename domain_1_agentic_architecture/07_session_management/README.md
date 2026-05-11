# Task 1.7 – Manage Session State, Resumption, and Forking

> **Exam Domain**: Domain 1 — Agentic Architecture & Orchestration (27%)  
> **Scenarios**: Claude Code multi-step investigation (Scenario 6)  
> **Code**: [`session_resumption.py`](./session_resumption.py) | [`fork_session_patterns.py`](./fork_session_patterns.py) | [`session_lifecycle.py`](./session_lifecycle.py)

---

## Core Concepts: Session Types and Operations

### What Is a Session?

A **session** is a conversation context with message history and state:

```
┌─────────────────────────────────────┐
│  SESSION  (conversation context)    │
├─────────────────────────────────────┤
│ messages: [                          │
│   {role: "user", content: "..."},    │
│   {role: "assistant", content: "..."} │
│ ]                                   │
│                                     │
│ state: {                            │
│   tool_results: {...},              │
│   file_digests: {...},              │
│   current_hypothesis: "..."         │
│ }                                   │
└─────────────────────────────────────┘
```

A session can be:
- **Named** — persisted and resumable by name (CLI: `--resume <name>`)
- **Forked** — independent branch from a named session (CLI: `--fork-session <base>`)
- **Ephemeral** — single-use, not persisted (typical API usage)

---

## 1. Named Session Resumption (`--resume`)

### The Resume Guarantee

`--resume <session-name>` reloads the exact prior conversation. The session history is deterministic: everything the agent said, did, and concluded remains available.

```
Work Session 1 (Day 1):
  claude "Analyze the payment module architecture"
  → output: detailed architecture analysis
  → saved as session "payment_analysis"

Work Session 2 (Day 3, after code changes):
  claude --resume payment_analysis
  "The payment module was refactored. In auth.py, lines 45-67 changed.
   Analyze the impact of these changes on your prior analysis."
  
  → Resumed session has:
      - Full prior message history
      - All prior tool results
      - All prior conclusions
      - Now: targeted re-analysis request
```

### When to Resume vs Start Fresh

```
RESUME (--resume)                    START FRESH (no --resume)
─────────────────────────────────    ──────────────────────────────
Prior context still valid              Prior tool results are stale
Incremental addition needed            Complete re-analysis required
File changes are targeted              Major codebase restructure
Prior conclusions hold                 Assumptions are invalidated
Cost: cheaper (context reuse)          Cost: more expensive (rebuild)

Example: Resume                        Example: Start Fresh
──────────────────────────────        ──────────────────────────
Resumed payment analysis,              Prior session found 14 bugs.
inform: "auth.py lines 45-67           New code review finds only 3
were refactored. Lines 50-54           of the 14 still exist.
changed from X to Y."                  Start fresh → will find different
Agent can diff this change             bugs in the rewritten code.
against prior analysis.

Agent's thinking:                     Agent's thinking:
  "I know the prior structure.         "I have no idea what the
   This specific change affects        prior analysis found. I'll
   the payment flow here..."           analyse from scratch."
```

### The Core Problem With Stale Tool Results

```
RESUMED SESSION WITH STALE RESULTS
───────────────────────────────────
Prior session:
  tool: web_search("payment gateway 2024 trends")
  result: {...dated results from March 2024...}

Resumed session 6 months later:
  Agent has access to old March 2024 results
  But market has changed: 3 new competitors, pricing shifted
  Agent builds conclusions on stale data
  
  ❌ WRONG: Trusting the cached March 2024 results
  ✅ RIGHT: "Re-search for current payment gateway trends"

FRESH SESSION WITH INJECTED SUMMARIES
──────────────────────────────────────
Fresh session:
  Coordinator: "Based on prior analysis, here's a summary of
               the payment module's current state:
               - 3 main functions
               - Uses Stripe integration
               - Error handling via try/except
               - 12 critical bugs were found previously"
  
  Agent: (has this context but not stale tool results)
  Re-searches for fresh data, builds fresh conclusions,
  cites which old bugs still exist in refactored code
```

---

## 2. Fork Sessions for Divergent Exploration

### Fork vs Parallel Task Spawning

```
TASK SPAWNING (previous task 1.3)     FORK_SESSION
─────────────────────────────────     ───────────────────────
Coordinator spawns subagents          Coordinator (or human) creates
via Task tool                         independent session branches

Both start empty context              Both inherit shared baseline

No shared context between            Independent after fork point,
subagents                            but from same starting point

Fully parallel (no blocking)         Can work sequentially or parallel
```

### The Fork Pattern

```
BASELINE SESSION (shared analysis):
  claude> Analyse codebase X
  → creates comprehensive analysis
  → session name: "codebase_x_baseline"

FORK A — Approach 1:
  claude --fork-session codebase_x_baseline
  "Compare REST API redesign: option A (GraphQL)"
  
  → inherits: full baseline analysis
  → independent: diverges from this point
  → output: GraphQL approach analysis

FORK B — Approach 2:
  claude --fork-session codebase_x_baseline
  "Compare REST API redesign: option B (gRPC)"
  
  → inherits: same full baseline analysis (parallel branch)
  → independent: diverges from this point
  → output: gRPC approach analysis

DECISION:
  Human reviews both fork outputs,
  decides which approach to pursue based on merits.
```

### Why Fork Is Superior to Re-Analysis

```
WRONG: Starting fresh analysis twice
────────────────────────────────────
fresh_session_a: claude "Analyse API redesign: GraphQL approach"
  → must discover codebase X structure again
  → 4 min, 8000 tokens

fresh_session_b: claude "Analyse API redesign: gRPC approach"
  → must discover codebase X structure again
  → 4 min, 8000 tokens

Total: 8 minutes, 16000 tokens

RIGHT: Fork from shared baseline
───────────────────────────────────
baseline: claude "Analyse codebase X"
  → understand structure once
  → 4 min, 8000 tokens

fork_a: claude --fork-session baseline "Compare GraphQL approach"
  → starts with baseline context
  → 1 min, 2000 tokens (only comparing approaches)

fork_b: claude --fork-session baseline "Compare gRPC approach"
  → starts with baseline context
  → 1 min, 2000 tokens

Total: 6 minutes, 12000 tokens
Speed: 33% faster
Cost: 25% cheaper
Quality: Same (both know baseline)
```

---

## 3. Session Lifecycle and State Management

### Diagram of Session Operations

```
SESSION CREATION
  ↓
NAMED SESSION LOOP:
  claude [--resume name] "query"
    ↓
  conversation executes (tools, reasoning, conclusions)
    ↓
  (implicit save at end if named)

FORK OPERATIONS:
  baseline session created/resumed
    ↓
  claude --fork-session baseline "approach A"
    ├─ creates fork_a (copy of baseline's message history)
    ├─ appends new user message
    ├─ runs to completion
    └─ saved as fork_a (independent from baseline)
  
  baseline session still active
    ↓
  claude --fork-session baseline "approach B"
    ├─ creates fork_b (fresh copy of baseline's message history)
    ├─ appends new user message
    ├─ runs to completion
    └─ saved as fork_b (independent from baseline)

DECISION & CONTINUATION:
  baseline, fork_a, fork_b all exist independently
  Developer reviews fork_a vs fork_b outputs
  Decides to pursue fork_a's approach
    ↓
  claude --resume fork_a "Implement the approach from above"
    ↓
  fork_a continues (preserves prior reasoning)
```

### State Staleness Scenarios

```
SCENARIO 1: Code hasn't changed
────────────────────────────────
Prior session: Payment module analysis (3 days old)
Code state:   No changes
Resumption:   Safe ✓

Approach: --resume and ask incremental questions
  "Given your prior analysis, what's the impact of adding
   TLS 1.3 to the payment gateway connection?"
  (builds on prior analysis, doesn't duplicate work)

SCENARIO 2: Code changed in analyzed files
──────────────────────────────────────────
Prior session: Payment module analysis (cov. 85%)
Code state:   checkout.py refactored (lines 50-120 rewritten)
Resumption:   Risky if assuming old code state

Approach: Resume + inform of specific changes
  --resume payment_analysis
  "The checkout flow was refactored. Lines 50-120 of
   payment/checkout.py changed from [old] to [new].
   How does this affect your prior findings?"
  
  (agent knows context from prior session, can diff this change)

SCENARIO 3: Core assumptions invalidated
────────────────────────────────────────
Prior session: Architecture analysis assuming single database
Code state:   Refactored to microservices, 4 databases now
Resumption:   Not safe

Approach: Start fresh with injected summary
  (new session, no --resume)
  "You previously found the monolithic system had these issues:
   [list]. The system was refactored to microservices with:
   [new architecture summary]. 
   Which prior issues still apply? Which are resolved?
   What new issues exist?"
  
  (agent starts fresh, but knows baseline for comparison)
```

---

## 4. Informed Resumption: Communicating File Changes

### The File Change Protocol

When resuming with modified files, the agent needs:
1. **What file changed** (path)
2. **What changed** (the diff or specific lines)
3. **Why it matters** (context for analysis)

```python
# Example: Resuming with specific file changes

resume_with_changes = """
claude --resume payment_analysis

I need to re-analyse the checkout flow.
Three files changed since the prior analysis:

FILE 1: payment/checkout.py
  Changed: Lines 45-50 (payment gateway initialization)
  From:    stripe.init(api_key=config['stripe_key'])
  To:      stripe.init(api_key=vault.get_secret('stripe_key'),
                       timeout=30)
  Impact:  Now uses vault for secrets + adds timeout

FILE 2: payment/error_handling.py
  Changed: Added new exception type PaymentTimeoutError (line 67-71)
  Impact:  checkout.py now needs to catch this

FILE 3: tests/test_checkout.py
  Changed: +32 new test cases (lines 200-232)
  Impact:  Test coverage changed from 75% to 89%

Question: Do these changes address any of your prior findings?
          What new risks does the vault integration introduce?
"""
```

### Why This Works Better Than Resuming Without Information

```
RESUMED WITHOUT FILE CHANGE NOTIFICATION
──────────────────────────────────────────
Agent has: prior analysis (old code assumptions)
Agent sees: new conversation message
Agent thinks: "The prior analysis was about payment/checkout.py.
              Maybe I should re-read it to make sure it's current.
              But I'm not sure what changed.
              I could search for the current checkout.py but I
              don't want to waste tokens re-reading code I know."

Result: Uncertain, potentially incorrect analysis built on
        stale assumptions

RESUMED WITH FILE CHANGE NOTIFICATION
──────────────────────────────────────────
Agent has: prior analysis + explicit file change list
Agent sees: "These 3 files changed: [diffs provided]"
Agent thinks: "I know the prior state. I know exactly what changed.
              I can diff this against my prior analysis.
              Changes to vault secret handling are security-relevant.
              Timeout addition affects my prior error-handling analysis."

Result: Targeted, accurate re-analysis of ONLY the changed parts
        (doesn't re-analyse unchanged code)
```

---

## 5. Anti-Patterns and Exam Traps

| Anti-Pattern | Why It Fails | Correct Approach |
|---|---|---|
| Resume with stale tool results without re-execution | Data gets out-of-date; conclusions become invalid | Re-run tools or start fresh with injected summary |
| Resuming after major refactor without new context | Assumptions are broken; agent wastes time trying to apply old analysis to new structure | Start fresh session with injected baseline summary |
| Fork-from-fork chains (fork a fork of a fork) | Message history grows, context efficiency drops, divergence gets too far | Keep forks direct from baseline; use resumption for linear continuation |
| Not naming sessions when resuming is intended | Can't resume — loses context between work sessions | Plan naming strategy upfront |
| Starting fresh with old tool results hardcoded in prompt | Hallucination risk; agent may contradict stale data with new reasoning | Use summaries (not tool results) in injected context |
| Forking and then deleting the baseline | Forks become orphaned if baseline is needed for context | Keep baseline as immutable reference |
| Resuming without acknowledging code changes in modified files | Agent builds conclusions on invalid assumptions | Explicitly list changed files and diffs when resuming after mods |

---

## 6. Session Naming Conventions (Exam Tip)

### Naming Strategy for Auditability

```
GOOD NAMING (traceable, meaning)
────────────────────────────────
payment_analysis_2024_11_01
  ↑ Domain, date

api_redesign_baseline
  ↑ Clear: this is the shared baseline for redesign exploration

api_redesign_fork_graphql
api_redesign_fork_grpc
  ↑ Parallel explorations traceable to baseline


BAD NAMING (opaque, unmaintainable)
──────────────────────────────────
session_1, session_2, tmp, work
  ↑ No information about what's inside


NAMING FOR FORKING
──────────────────
baseline:     codebase_x_analysis
fork A:       codebase_x_analysis__approach_rest
fork B:       codebase_x_analysis__approach_graphql
continuation: codebase_x_analysis__approach_rest__implementation

Pattern: <baseline>__<variant>__<continuation>
```

---

## 7. Files in This Folder

| File | Contents |
|------|----------|
| `README.md` | This conceptual guide |
| `session_resumption.py` | Named session API, resumption vs fresh start decisions |
| `fork_session_patterns.py` | Fork creation, baseline management, parallel branches |
| `session_lifecycle.py` | Full state management, file change notification, session isolation |
