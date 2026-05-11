# Task 1.3 – Configure Subagent Invocation, Context Passing, and Spawning

> **Exam Domain**: Domain 1 — Agentic Architecture & Orchestration (27%)  
> **Scenario**: Multi-Agent Research System (Scenario 3)  
> **Sample Questions**: Q7, Q8, Q9  
> **Code**: [`subagent_invocation.py`](./subagent_invocation.py) | [`context_passing.py`](./context_passing.py) | [`parallel_spawning.py`](./parallel_spawning.py)

---

## The Core Problem This Task Solves

A coordinator agent on its own has one context window. For complex research or analysis tasks, that window fills up quickly, reasoning quality degrades, and you lose the benefit of specialisation. The answer is to **delegate subtasks to subagents**, each with its own fresh context, focused system prompt, and restricted tool access. But delegation requires knowing exactly how spawning works, what context subagents inherit (none, automatically), and how to pass what they need explicitly.

---

## 1. The Task Tool — Spawning Mechanism

### How Spawning Works

The `Task` tool is the **only** mechanism a coordinator uses to spawn subagents in the Claude Agent SDK. There is no other API call, no side channel, no implicit spawn. If `Task` is not in `allowedTools`, the coordinator cannot invoke subagents — full stop.

```
Coordinator receives user query
         │
         ▼
  Calls Task tool (in allowedTools)
         │
         ▼
  Runtime creates subagent with:
    - AgentDefinition (system prompt, tools)
    - Explicit prompt from coordinator
    - ISOLATED context window (fresh, empty)
         │
         ▼
  Subagent executes, returns result
         │
         ▼
  Coordinator receives tool_result
```

### The `allowedTools` Requirement

```python
# ❌ WRONG: coordinator cannot spawn subagents
coordinator = AgentDefinition(
    system_prompt="You coordinate research...",
    allowed_tools=["web_search", "read_file"],  # Task missing!
)

# ✅ CORRECT: Task included enables subagent spawning
coordinator = AgentDefinition(
    system_prompt="You coordinate research...",
    allowed_tools=["web_search", "read_file", "Task"],  # Task present
)
```

**Exam trap**: If a question describes a coordinator that "cannot spawn subagents" despite being correctly configured otherwise, the first thing to check is whether `"Task"` is in `allowedTools`.

### Task Tool Input Schema

```python
TASK_TOOL = {
    "name": "Task",
    "description": "Spawn a subagent to handle a specialised subtask.",
    "input_schema": {
        "type": "object",
        "properties": {
            "agent_role": {
                "type": "string",
                "description": "Which subagent type to spawn"
            },
            "instruction": {
                "type": "string",
                "description": "Complete task + all context needed. Subagent has nothing else."
            },
        },
        "required": ["agent_role", "instruction"],
    },
}
```

The `instruction` field is doing the heavy lifting — it must contain everything the subagent needs, because the subagent starts from zero.

---

## 2. Context Isolation — What Subagents Do and Don't Inherit

### The Isolation Principle

This is the single most important concept in Task 1.3 and is directly tested:

> **Subagents do NOT automatically inherit the coordinator's conversation history, memory, or any other context. Subagents do NOT share memory between invocations.**

Each subagent is a blank slate. It receives:
- ✅ Its `AgentDefinition` (system prompt, tools, description)
- ✅ Whatever the coordinator explicitly puts in the `Task` instruction

It does NOT receive:
- ❌ The coordinator's conversation history
- ❌ Results from other subagents (unless the coordinator passes them explicitly)
- ❌ The original user query (unless included in the instruction)
- ❌ Prior subagent conversation history
- ❌ Any shared state or global memory

### Why This Design?

```
SHARED CONTEXT (bad)                    ISOLATED CONTEXT (good)
────────────────────                    ──────────────────────────
All subagents see:                      Each subagent sees:
  - Full coordinator history              - Only what coordinator passes
  - All prior tool results                - Clean context window
  - Other subagents' outputs              - Focused on its specific task
         │                                        │
  Context window fills                    Full window for its work
  quickly with irrelevant data            No distraction from other tasks
  Subagent can't focus                    Specialisation is real
```

### Visualising Context Boundaries

```
┌─────────────────────────────────────────────────────┐
│  COORDINATOR  (knows everything)                    │
│                                                     │
│  history = [user_query, turn_1, turn_2, ...]        │
│  web_results = {...}                                │
│  doc_analysis = {...}                               │
│                                                     │
│   spawns ──────────────────────────────────────┐   │
│                                                │   │
└────────────────────────────────────────────────│───┘
                                                 │
                          explicit instruction   │
                          only (what coordinator │
                          chooses to include)    │
                                                 ▼
                          ┌─────────────────────────────┐
                          │  SUBAGENT  (blank slate)    │
                          │                             │
                          │  Sees: instruction only     │
                          │  Does NOT see:              │
                          │    ✗ coordinator history    │
                          │    ✗ other subagents        │
                          │    ✗ original user query    │
                          │       (unless included)     │
                          └─────────────────────────────┘
```

---

## 3. AgentDefinition Configuration

`AgentDefinition` is the template that defines a subagent type — its identity, expertise, and boundaries.

### Components

```python
AgentDefinition(
    # 1. Description: used by the coordinator to decide which subagent to spawn
    description="Searches the web for current information on research topics",

    # 2. System prompt: the subagent's expertise, constraints, and output format
    system_prompt="""You are a web research specialist.
Focus: find current, factual information on the assigned topic.
Output format: structured JSON with claims, sources, and dates.
Constraints: do NOT analyse or synthesise — other agents do that.
             do NOT make up sources — only report what you find.""",

    # 3. Tool restrictions: only tools relevant to this agent's role
    allowed_tools=["web_search", "fetch_url"],
    # NOT: process_refund, write_file, escalate_to_human
    # Tool restriction enforces specialisation and prevents misuse
)
```

### Designing System Prompts by Role

The system prompt does three things for a subagent:
1. Establishes **what it knows** (expertise framing)
2. Establishes **what it must not do** (boundary enforcement)
3. Establishes **how to format output** (downstream usability)

```
┌──────────────────────────────────────────────────────┐
│ WELL-DESIGNED SYSTEM PROMPT STRUCTURE                │
├──────────────────────────────────────────────────────┤
│                                                      │
│ Role: "You are a [role] specialist."                 │
│       → One clear identity, not a generalist         │
│                                                      │
│ Expertise: "Your focus is [specific domain]."        │
│       → What the agent knows and looks for           │
│                                                      │
│ Boundaries: "Do NOT [other agents' work]."           │
│       → Prevents scope creep and tool misuse         │
│                                                      │
│ Output format: "Return [specific structure]."        │
│       → Ensures coordinator can parse and use output │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### Example AgentDefinitions for a Research Pipeline

```python
WEB_SEARCHER = AgentDefinition(
    description="Finds current web-based information on a topic",
    system_prompt="""You are a web research specialist.
EXPERTISE: finding current, factual, well-sourced information.
BOUNDARY: do NOT analyse, synthesise, or draw conclusions.
OUTPUT: JSON array of findings, each with claim, url, date.""",
    allowed_tools=["web_search", "fetch_url"],
)

DOCUMENT_ANALYST = AgentDefinition(
    description="Analyses provided documents for key insights",
    system_prompt="""You are a document analysis specialist.
EXPERTISE: extracting claims, statistics, and conclusions from text.
BOUNDARY: do NOT search the web; work only with provided documents.
OUTPUT: JSON array of findings with claim, document_name, page_number.""",
    allowed_tools=["read_file"],
)

SYNTHESISER = AgentDefinition(
    description="Synthesises findings from multiple sources into reports",
    system_prompt="""You are a research synthesis specialist.
EXPERTISE: combining multi-source findings into coherent, cited reports.
BOUNDARY: do NOT search or analyse — work only from provided findings.
OUTPUT: structured report with claim-source mappings preserved.""",
    allowed_tools=[],  # No tools needed — works from context only
)
```

---

## 4. Passing Complete Context Explicitly

### The Rule

Since subagents inherit nothing, the coordinator must package every piece of information the subagent needs into the `Task` instruction. This means:

```python
# ❌ WRONG: assumes subagent knows the topic
task_instruction = "Research the competitive landscape."
# Subagent has no idea what product, market, or angle to focus on.

# ✅ CORRECT: everything the subagent needs is in the instruction
task_instruction = f"""Research the competitive landscape for entry into {market}.

RESEARCH GOALS:
1. Identify the top 5 competitors and their market positioning
2. Find market share data (prefer last 12 months)
3. Identify gaps in current offerings

QUALITY CRITERIA:
- Sources must be from 2023 or later
- Include quantitative data where available
- Flag if data is estimated vs measured

OUTPUT FORMAT:
Return JSON with this structure:
{{
  "competitors": [
    {{"name": "...", "market_share": "...", "positioning": "...", "source_url": "..."}}
  ],
  "market_gaps": ["..."],
  "data_freshness": "YYYY-MM"
}}"""
```

### Goals + Criteria Over Step-by-Step Instructions

A key exam skill is knowing what kind of instruction to write for coordinator prompts. The exam tests this directly:

```
STEP-BY-STEP INSTRUCTIONS (bad)        GOALS + QUALITY CRITERIA (good)
────────────────────────────────       ────────────────────────────────
"1. Search for competitor names         "Find comprehensive competitor data
 2. For each, find their website         for the [market] market.
 3. Extract pricing information
 4. Look for customer reviews           Goals:
 5. Compile into a table"               - Market share estimates
                                        - Pricing tiers
Why bad:                                - Customer sentiment
- Rigid — model can't adapt             - Product differentiators
- Breaks if step 2 finds nothing
- No room for judgment calls            Quality criteria:
- Over-specifies the HOW                - 2023+ data preferred
                                        - Flag estimated vs confirmed"

                                        Why good:
                                        - Subagent adapts strategy to findings
                                        - Can skip irrelevant steps
                                        - Exercises judgment on what to include
                                        - Specifies the WHAT, not the HOW
```

---

## 5. Structured Data Formats for Attribution Preservation

### Why Attribution Gets Lost

When subagents return plain text summaries, the coordinator cannot tell which specific claim came from which source. By the time a synthesis agent combines multiple summaries, all provenance is gone.

### The Structured Finding Format

Every subagent should return findings with claim-source mappings baked in:

```python
# ❌ PLAIN TEXT — attribution lost in synthesis
"AI music generation has grown significantly. Spotify reports increased
AI-created tracks. The market is expected to double by 2026."

# ✅ STRUCTURED — attribution preserved end-to-end
{
  "findings": [
    {
      "claim": "AI-generated music tracks grew 340% on major streaming platforms",
      "evidence_excerpt": "Platform data indicates a 340% year-on-year increase...",
      "metadata": {
        "source_url": "https://techreport.com/ai-music-2024",
        "document_name": "AI Music Industry Report 2024",
        "page_number": 12,
        "publication_date": "2024-09-15",
        "source_type": "industry_report",
        "confidence": "measured"   # vs "estimated"
      }
    }
  ],
  "coverage_gaps": ["live performance AI adoption data unavailable"],
  "search_date": "2024-11-01"
}
```

### Passing Prior Findings to Later Subagents

When the coordinator passes findings from agent A to agent B, it must include both content AND metadata:

```python
def build_synthesis_instruction(web_findings: list, doc_findings: list, topic: str) -> str:
    """
    Build a synthesis subagent instruction that includes complete
    prior findings WITH attribution intact.
    """
    return f"""Synthesise research on: {topic}

WEB RESEARCH FINDINGS (from web_searcher agent):
{json.dumps(web_findings, indent=2)}
# ↑ Includes source_url, date, confidence for every claim

DOCUMENT ANALYSIS FINDINGS (from document_analyst agent):
{json.dumps(doc_findings, indent=2)}
# ↑ Includes document_name, page_number for every claim

SYNTHESIS REQUIREMENTS:
1. Every claim in your output MUST cite its source from the above data
2. If two sources conflict, present BOTH values with their sources
3. Note which topic areas had no sources (coverage gaps)
4. Do NOT add claims not supported by the provided findings

OUTPUT FORMAT: Structured report with claim-source mappings preserved."""
```

---

## 6. Parallel Subagent Spawning

### The Critical Pattern

To spawn subagents in parallel, the coordinator must emit **multiple Task tool calls in a single response** — not across separate turns. This is one of the most commonly tested patterns.

```
SEQUENTIAL (slow, wrong pattern)       PARALLEL (fast, correct pattern)
────────────────────────────────       ──────────────────────────────────
Turn 1: coordinator calls Task(A)      Turn 1: coordinator calls Task(A),
Turn 2: coordinator calls Task(B)                             Task(B),
Turn 3: coordinator calls Task(C)                             Task(C)
                                                 all in ONE response
Total: 3 round trips to the model      Total: 1 round trip to the model

A, B, C run SEQUENTIALLY               A, B, C run CONCURRENTLY
Each waits for previous to finish      All finish in parallel
```

### How the Runtime Executes Parallel Tasks

```
Coordinator response contains:
  [tool_use: Task(web_searcher, "research music...")]
  [tool_use: Task(web_searcher, "research film...")]
  [tool_use: Task(web_searcher, "research writing...")]
         │
         ▼ Runtime detects multiple Task calls
         │
  ┌──────┴──────┬──────────────┐
  ▼             ▼              ▼
Agent A       Agent B        Agent C
(music)       (film)         (writing)
  │             │              │
  └─────────────┴──────────────┘
         │ All complete
         ▼
Coordinator receives 3 tool_results in one user turn
```

### Why Sequential Spawning Is Wrong

```python
# ❌ WRONG: one Task per turn means sequential execution
for topic in ["music", "film", "writing"]:
    response = coordinator.call_claude(messages)
    messages.append(response)
    task_result = execute_task_tool(response.tool_calls[0])
    messages.append(task_result)
    # Next topic waits for this one to finish

# ✅ CORRECT: all Tasks in ONE coordinator response
# The coordinator prompt should tell the coordinator to spawn all
# tasks simultaneously, and the model returns all Task calls at once.
# The runtime then executes them in parallel.
```

---

## 7. Fork-Based Session Management

### What fork_session Is For

`fork_session` creates **independent branches from a shared analysis baseline**. Use it when you have done expensive analysis and want to explore divergent approaches without re-doing that work.

```
Shared baseline analysis (expensive)
         │
         ├──── fork A: "Evaluate approach: REST API design"
         │              │ (builds on baseline, goes its own way)
         │              ▼
         │         branch A results
         │
         └──── fork B: "Evaluate approach: GraphQL design"
                        │ (same baseline, different direction)
                        ▼
                   branch B results
```

### fork_session vs Standard Subagent Spawning

| | Standard Task Spawn | fork_session |
|---|---|---|
| **Starting context** | Empty (explicit only) | Inherits shared baseline |
| **Use case** | Specialised domain work | Divergent approach comparison |
| **Independence** | Full isolation | Independent after fork point |
| **When to use** | Different domains, parallel research | Same domain, different strategies |

### CLI Pattern (Claude Code)

```bash
# 1. Perform shared baseline analysis
claude "Analyse the authentication module architecture and summarise its structure"

# 2. Fork into independent exploration branches
# Branch A: one approach
claude --fork-session auth_analysis "Evaluate JWT-based token refresh implementation"

# Branch B: different approach  
claude --fork-session auth_analysis "Evaluate session-based cookie authentication"

# Both branches inherit the auth analysis but diverge from there
# Compare outputs to make informed decision
```

---

## 8. Anti-Patterns and Exam Traps

| Anti-Pattern | Why It Fails | Correct Approach |
|---|---|---|
| `allowedTools` missing `"Task"` | Coordinator cannot spawn subagents at all | Always include `"Task"` in coordinator's `allowedTools` |
| Assuming subagent inherits context | Subagent starts empty — gets wrong/no data | Explicitly pass every piece of needed context |
| Vague Task instructions ("research this") | Subagent doesn't know scope, goals, or format | Include topic, goals, criteria, and output format |
| Step-by-step procedural instructions | Rigid; breaks when conditions vary | Specify research goals + quality criteria |
| One Task call per turn for parallel work | Sequential execution — no parallelism benefit | Emit all Task calls in a single coordinator response |
| Plain text subagent output | Attribution lost in synthesis | Structured JSON with claim-source mappings |
| Giving all tools to all subagents | Tool misuse, degraded selection reliability | Restrict each subagent to role-relevant tools only |
| Re-using a subagent session for new task | Stale context from prior invocation | Each Task invocation gets fresh isolated context |

---

## 9. Sample Question Analysis

### Q9 — Scoped Tool Provision (Task 2.3 crossover)

> Synthesis agent frequently needs to verify claims, currently requiring 2-3 coordinator round-trips per task (+40% latency). 85% are simple fact-checks; 15% need deep investigation. Most effective approach?

| Option | Assessment | Reasoning |
|--------|-----------|-----------|
| A) Give synthesis agent a scoped `verify_fact` tool for simple lookups; complex go to web_search via coordinator | ✅ **CORRECT** | Principle of least privilege — covers 85% case inline while preserving coordinator routing for complex 15% |
| B) Batch all verifications at end of pass, send to coordinator at once | ❌ Wrong | Creates blocking dependency — synthesis steps may depend on earlier verified facts |
| C) Give synthesis agent all web search tools | ❌ Wrong | Over-provisions — synthesis agent will use web search when it shouldn't; violates specialisation |
| D) Web searcher proactively caches extra context | ❌ Wrong | Speculative — cannot predict what synthesis agent will need |

### Q7 crossover — Narrow decomposition → coverage gaps

The Task tool is only as good as the coordinator's decomposition. If the coordinator calls `Task` three times with "AI in digital art", "AI in graphic design", "AI in photography" for the topic "AI in creative industries", the subagents execute correctly within their assigned scope — but music, writing, and film are never researched. The failure is in what the coordinator passes to `Task`, not in how Task works.

---

## 10. Files in This Folder

| File | Contents |
|------|---------|
| `README.md` | This conceptual guide |
| `subagent_invocation.py` | Core mechanics: Task tool, AgentDefinition, context isolation |
| `context_passing.py` | Structured finding formats, explicit context packaging, attribution |
| `parallel_spawning.py` | Parallel Task emission, fork_session, coordinator prompt design |
