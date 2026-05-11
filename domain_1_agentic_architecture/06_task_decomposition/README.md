# Task 1.6 – Design Task Decomposition Strategies for Complex Workflows

> **Exam Domain**: Domain 1 — Agentic Architecture & Orchestration (27%)  
> **Scenarios**: Claude Code for CI (Scenario 5), Developer Productivity (Scenario 4)  
> **Code**: [`prompt_chaining.py`](./prompt_chaining.py) | [`adaptive_decomposition.py`](./adaptive_decomposition.py) | [`code_review_pipeline.py`](./code_review_pipeline.py)

---

## The Core Decision: Fixed Pipeline vs Adaptive Decomposition

Task decomposition is fundamentally a **decision about predictability**. The right strategy is determined before writing any code, by answering one question:

> **Do you know the full set of subtasks upfront, or does each step's output determine what comes next?**

```
KNOWN SUBTASK STRUCTURE              UNKNOWN SUBTASK STRUCTURE
─────────────────────────────────    ─────────────────────────────────
"Review this PR for security,        "Add comprehensive tests to this
 style, and correctness issues"       legacy codebase"

Subtasks are fixed:                  Subtasks emerge from exploration:
  1. Security analysis                 Step 1: map the codebase
  2. Style analysis                    Step 2: identify what needs testing
  3. Correctness analysis              Step 3: decide priority order
  4. Cross-file integration            Step 4: generate tests per area
                                       Step N: adapt if dependencies found

→ PROMPT CHAINING                    → ADAPTIVE DECOMPOSITION
  (fixed sequential pipeline)          (dynamic plan, updates as you go)
```

Getting this decision wrong is expensive:
- Prompt chaining on an open-ended task → rigid structure that breaks when assumptions fail
- Adaptive decomposition on a predictable task → unnecessary overhead, slower, harder to test

---

## 1. Prompt Chaining — Fixed Sequential Pipelines

### Definition

Prompt chaining breaks a complex task into a predetermined sequence of focused steps, where each step's output becomes the next step's input. The pipeline structure is defined **before** execution begins and does not change based on intermediate results.

### When to Use Prompt Chaining

| Signal | Example |
|--------|---------|
| Task has multiple distinct, well-understood aspects | Security + style + correctness review |
| Aspects are always present regardless of input | Every PR has files to analyse |
| Clear quality criteria exist for each step | "Flag SQL injection; flag PEP 8 violations" |
| Steps have known, consistent scope | Per-file analysis → cross-file integration |
| Reproducibility matters | CI/CD pipeline — same structure every run |

### The Code Review Pipeline Pattern

The canonical exam example is splitting a large code review into:

```
INPUT: Pull request with N files
         │
         ├── Pass 1: Per-file LOCAL analysis
         │   ├── File 1 → security, correctness, style issues in File 1
         │   ├── File 2 → security, correctness, style issues in File 2
         │   └── File N → security, correctness, style issues in File N
         │
         └── Pass 2: Cross-file INTEGRATION analysis
             → Data flow between files
             → Inconsistent error handling across modules
             → API contract violations
             → Shared state problems
```

**Why split per-file and cross-file?**

If you analyse all 14 files in one pass:
- **Attention dilution**: model splits attention across all files, gives superficial treatment to each
- **Contradictory findings**: may flag a pattern in one file while approving identical code in another
- **Context window pressure**: 14 files × average file size → context nearly full before reasoning begins
- **Lost cross-file signal**: ironically, the cross-file issues become harder to spot when everything is crammed together

Per-file passes + a dedicated integration pass solves all four problems.

### Prompt Chaining Architecture

```
┌─────────────────────────────────────────────────────────┐
│  PROMPT CHAINING EXECUTION MODEL                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Step 1 prompt                                          │
│    system: "You review security issues"                 │
│    user:   [file contents]                              │
│    → output: structured security findings               │
│         │                                               │
│         ▼ (output fed as input)                         │
│  Step 2 prompt                                          │
│    system: "You review style issues"                    │
│    user:   [file contents]                              │
│    → output: structured style findings                  │
│         │                                               │
│         ▼ (outputs from steps 1+2 fed in)              │
│  Step 3 prompt  (cross-file integration)                │
│    system: "You review cross-file data flow"            │
│    user:   [all file summaries + findings from 1+2]     │
│    → output: integration-level issues                   │
│         │                                               │
│         ▼                                               │
│  Step 4: Aggregation                                    │
│    Combine all findings → deduplicate → prioritise      │
│    → final structured review output                     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Key Prompt Chaining Properties

**Each step has isolated, focused context**: A security-focused pass isn't distracted by style considerations. This is why prompt chaining produces more thorough results than a single all-aspects pass.

**Steps can run in parallel when independent**: Per-file analyses of File 1, File 2, and File 3 are independent — they can all run concurrently. The cross-file integration pass must wait for all per-file results.

**The pipeline structure is deterministic**: Given the same PR, the same pipeline runs. This is what makes it suitable for CI/CD where reproducibility is required.

---

## 2. Adaptive Decomposition — Dynamic Plans

### Definition

Adaptive decomposition generates and refines subtasks based on intermediate findings. The plan at step N depends on what was discovered at steps 1 through N-1. The full task structure **cannot be known upfront**.

### When to Use Adaptive Decomposition

| Signal | Example |
|--------|---------|
| Task scope is genuinely unknown | "Add comprehensive tests to a legacy codebase" |
| Findings at step N determine what to investigate at step N+1 | Discovering circular dependencies changes test strategy |
| Different inputs require structurally different plans | Some codebases have test infrastructure; others don't |
| Open-ended investigation with variable depth | "Debug this system" — severity and location unknown |
| Dependencies between components aren't known upfront | What does module X depend on? Unknown until analysed |

### The Three-Phase Adaptive Pattern

For open-ended tasks, adaptive decomposition always follows this structure:

```
Phase 1: MAP — Understand what you're dealing with
───────────────────────────────────────────────────
  Goal:    Establish ground truth about structure
  Method:  Explore without touching production code
  Output:  Inventory of components, dependencies, current state

  Example:
    - List all modules and their sizes
    - Identify entry points and public APIs
    - Find existing test files and their coverage
    - Map dependency graph
    - Identify build system and test runner

Phase 2: PRIORITISE — Decide what matters most
───────────────────────────────────────────────────
  Goal:    Use Phase 1 findings to rank areas by impact
  Method:  Analyse findings; apply heuristics (coverage gaps,
           criticality, change frequency, risk level)
  Output:  Ordered backlog of areas to address

  Example:
    - payment module: 0% coverage, highest business risk → Priority 1
    - auth module: 15% coverage, security-critical → Priority 2
    - utils module: 65% coverage, low risk → Priority 5

Phase 3: EXECUTE — Generate subtasks adaptively
───────────────────────────────────────────────────
  Goal:    Work through prioritised plan, adapting as you go
  Method:  Address each area; update plan when dependencies found
  Output:  Completed work with updates to backlog

  Example:
    - Write tests for payment/checkout.py
    - Discover checkout.py imports payment/tax_calculator.py
    - Add tax_calculator.py tests before continuing checkout
    - Adjust remaining backlog based on discovery
```

### Why Adaptive Decomposition Beats Up-Front Planning for Open-Ended Tasks

```
UP-FRONT FULL PLAN (wrong for open-ended tasks)
─────────────────────────────────────────────────
"We'll test:
  1. auth module (estimated 2 days)
  2. payment module (estimated 3 days)
  3. order module (estimated 1 day)"

Problems:
  ✗ Estimates are wrong (you haven't seen the code yet)
  ✗ Missing dependencies block progress
  ✗ Low-value areas get same time as high-value ones
  ✗ Circular dependencies discovered late cause major rework

ADAPTIVE PLAN (correct for open-ended tasks)
─────────────────────────────────────────────────
"Step 1: Map the codebase
 Step 2: Based on map, identify high-risk uncovered modules
 Step 3: Start with payment/checkout.py
         → Find dependency on tax_calculator.py
         → Add to priority queue
 Step 4: tax_calculator.py tests
         → Find dependency on pricing/discounts.py
         → Add to queue
 Step N: Work through queue, updating priorities as discovered"

Benefits:
  ✓ Real priorities based on actual code state
  ✓ Dependencies handled as discovered, not as surprises
  ✓ Plan reflects reality, not assumptions
  ✓ High-value areas get more attention
```

---

## 3. Pattern Selection Decision Framework

```
                    Is the task structure known upfront?
                              │
              ┌───────────────┴───────────────┐
             YES                              NO
              │                               │
    Do all inputs have the              Is the scope genuinely
    same structural shape?              open-ended?
              │                               │
        ┌─────┴─────┐                   ┌─────┴─────┐
       YES           NO               YES             NO
        │             │                │               │
   PROMPT         PROMPT          ADAPTIVE         SINGLE
   CHAINING       CHAINING        DECOMP.          AGENT
   (parallel      (sequential,    (3 phases)       (small
    per item)      fixed steps)                     task)


EXAMPLES:
   PR review (14 files)         → prompt chaining, per-file parallel
   Security + style + correct   → prompt chaining, sequential aspects
   "Add tests to legacy code"   → adaptive decomposition, 3 phases
   "Debug this production issue" → adaptive decomposition, explore-first
   "Fix typo in README"         → single agent, no decomposition needed
```

---

## 4. Attention Dilution — Why Large Inputs Fail

Attention dilution is the specific failure mode that prompt chaining prevents in code reviews. Understanding it precisely matters for the exam.

### What Attention Dilution Means

A transformer model's attention is a finite resource distributed across the input context. When you provide 14 files simultaneously:

```
SINGLE PASS (14 files together)
────────────────────────────────
Files 1-14 occupy the context window.
Model attends to everything simultaneously.

Problems that appear in data:
  - Detailed feedback on files processed early (more attention)
  - Superficial comments on files processed later (less attention)
  - Bug in File 3 missed because model focusing on File 7
  - Identical code in File 5 and File 11: flagged in one, approved in other
  - Cross-file issues: model can't hold all 14 in working memory
```

```
PER-FILE PASSES (one file at a time)
─────────────────────────────────────
File 1 gets its own context window. Full attention. Deep analysis.
File 2 gets its own context window. Full attention. Deep analysis.
...
File 14 gets its own context window. Full attention. Deep analysis.

THEN: integration pass with file summaries (compact) + cross-file queries
```

### The Summaries Approach for Integration Pass

The integration pass doesn't re-read all 14 files. It receives **compact summaries** from each per-file pass:

```python
# Integration pass input (NOT raw files — summaries)
integration_context = {
    "file_summaries": [
        {
            "file": "auth/login.py",
            "public_api": ["login(username, password)", "logout(session_id)"],
            "data_sources": ["users table", "sessions table"],
            "error_handling": "returns None on failure",
        },
        {
            "file": "api/endpoints.py",
            "calls": ["auth.login()", "auth.logout()"],
            "error_handling": "raises HTTP 500 on auth failure",
        },
        # ... 12 more summaries
    ],
    "per_file_findings": [...],  # from per-file passes
}
# Integration pass looks for: inconsistent error handling,
# data flow violations, API contract mismatches
```

---

## 5. Anti-Patterns and Exam Traps

| Anti-Pattern | Why It Fails | Correct Approach |
|---|---|---|
| Single-pass on 14+ files | Attention dilution → inconsistent depth, missed bugs | Per-file passes + cross-file integration pass |
| Up-front full plan for open-ended tasks | Breaks when assumptions fail, wrong priorities | Phase 1 map → Phase 2 prioritise → Phase 3 execute adaptively |
| Adaptive decomposition for predictable reviews | Unnecessary overhead, harder to test, slower | Prompt chaining for known structure |
| Cross-file analysis in per-file passes | Each pass should be local-only; cross-file is a separate pass | Strict separation: local in per-file, cross-file in integration |
| Starting tests before mapping codebase | Missing dependencies, wrong priorities, rework | Always map structure first before generating subtasks |
| Updating plan only at end, not continuously | Discoveries at step N should update steps N+1...M | Check and update backlog after each subtask completion |
| Using prompt chaining when order matters | Step 2 may fail if it depends on Step 1 finding something | Make dependencies explicit; use adaptive if structure unknown |

---

## 6. Files in This Folder

| File | Contents |
|------|---------|
| `README.md` | This conceptual guide |
| `prompt_chaining.py` | Fixed pipelines: code review, per-file + cross-file, parallel execution |
| `adaptive_decomposition.py` | Dynamic planning: map → prioritise → execute, backlog updates |
| `code_review_pipeline.py` | Full production CI pipeline with both patterns integrated |
