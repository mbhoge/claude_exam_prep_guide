"""
parallel_spawning.py — Parallel Subagent Spawning and fork_session
==================================================================
Task 1.3 Skills:
  - Spawning parallel subagents by emitting multiple Task calls in
    a single coordinator response (NOT across separate turns)
  - Designing coordinator prompts with goals + quality criteria
    rather than step-by-step procedural instructions
  - fork_session for divergent exploration from a shared baseline

This file is exam-focused: Q9 tests the scoped cross-role tool pattern,
and Task 1.3 directly tests the "single response, multiple Task calls"
pattern for parallelism.

Run: python parallel_spawning.py
"""

import anthropic
import json
import time
from dataclasses import dataclass
from typing import Optional

client = anthropic.Anthropic()


# ══════════════════════════════════════════════════════════════════
# SECTION 1: SEQUENTIAL vs PARALLEL SPAWNING
# The fundamental difference — one call per turn vs all calls at once.
# ══════════════════════════════════════════════════════════════════

def demonstrate_sequential_vs_parallel():
    """
    Visualises the timing and round-trip difference between
    sequential Task calls (wrong) and parallel Task calls (correct).
    """
    print("\n" + "=" * 65)
    print("SEQUENTIAL vs PARALLEL SUBAGENT SPAWNING")
    print("=" * 65)

    print("""
SEQUENTIAL (wrong pattern — one Task per coordinator turn):
─────────────────────────────────────────────────────────────
  Turn 1: coordinator → Task(web_searcher, "AI in music")
  Turn 2: coordinator → Task(web_searcher, "AI in film")
  Turn 3: coordinator → Task(web_searcher, "AI in writing")

  Timeline: A|────|  B|────|  C|────|
             ↑ B waits for A. C waits for B.

  Problems:
    - 3 round trips to the coordinator model
    - Each subagent executes one at a time (no parallelism)
    - Total time = time(A) + time(B) + time(C)
    - Coordinator's token budget used up by intermediate turns

PARALLEL (correct pattern — multiple Tasks in ONE response):
─────────────────────────────────────────────────────────────
  Turn 1: coordinator → Task(web_searcher, "AI in music")
                      + Task(web_searcher, "AI in film")
                      + Task(web_searcher, "AI in writing")
          (all three in the same response)

  Timeline: A|────|
             B|────|   ← all running at the same time
             C|────|

  Benefits:
    - 1 round trip to the coordinator model
    - All subagents execute concurrently
    - Total time ≈ max(time(A), time(B), time(C))
    - Coordinator receives all three results in a single user turn

HOW THE RUNTIME KNOWS TO RUN IN PARALLEL:
  The coordinator response contains multiple content blocks of type "tool_use".
  When the runtime sees multiple Task tool_use blocks in one response,
  it executes them concurrently — the model doesn't control scheduling,
  the runtime does.
""")


# ══════════════════════════════════════════════════════════════════
# SECTION 2: HOW PARALLEL TASKS LOOK IN THE MESSAGE ARRAY
# Shows the exact JSON structure of a coordinator response
# that spawns multiple subagents simultaneously.
# ══════════════════════════════════════════════════════════════════

def show_parallel_task_message_structure():
    """
    Shows the raw message structure of a coordinator response
    containing multiple Task calls — this is what 'parallel' means
    at the API level.
    """
    print("\n" + "=" * 65)
    print("MESSAGE STRUCTURE: Multiple Task Calls in One Response")
    print("=" * 65)

    # This is what the coordinator's response.content looks like
    # when it spawns three subagents in parallel:
    coordinator_response_content = [
        {
            "type": "text",
            "text": "I'll research all three creative domains in parallel to ensure comprehensive coverage.",
        },
        # ── PARALLEL TASK 1 ────────────────────────────────────────
        {
            "type": "tool_use",
            "id": "task_call_001",
            "name": "Task",
            "input": {
                "agent_role": "web_searcher",
                "instruction": """Research AI impact on music production (2023-2024).

RESEARCH GOALS:
1. AI tools used by professional music producers
2. Workflow efficiency changes (time-to-release, cost)
3. Artist adoption and resistance rates

QUALITY CRITERIA:
- Sources from 2023 or later
- Prefer measured statistics over industry estimates
- Include source URL and publication date for every finding

OUTPUT: JSON findings array with full metadata per finding.""",
            },
        },
        # ── PARALLEL TASK 2 ────────────────────────────────────────
        {
            "type": "tool_use",
            "id": "task_call_002",
            "name": "Task",
            "input": {
                "agent_role": "web_searcher",
                "instruction": """Research AI impact on film production and visual effects (2023-2024).

RESEARCH GOALS:
1. AI tools in VFX, editing, and scriptwriting
2. Studio adoption rates and cost implications
3. Union and labour responses to AI in film

QUALITY CRITERIA:
- Sources from 2023 or later
- Include box office or budget data where available
- Flag whether sources are studio-issued vs independent

OUTPUT: JSON findings array with full metadata per finding.""",
            },
        },
        # ── PARALLEL TASK 3 ────────────────────────────────────────
        {
            "type": "tool_use",
            "id": "task_call_003",
            "name": "Task",
            "input": {
                "agent_role": "web_searcher",
                "instruction": """Research AI impact on creative writing and journalism (2023-2024).

RESEARCH GOALS:
1. AI writing assistants used by professional authors and journalists
2. Publisher and media company policies on AI-generated content
3. Reader perception of AI-written content

QUALITY CRITERIA:
- Sources from 2023 or later
- Include survey data or reader studies where available
- Distinguish between AI-assisted and fully AI-generated

OUTPUT: JSON findings array with full metadata per finding.""",
            },
        },
    ]

    print("\nCoordinator response.content has", len(coordinator_response_content), "blocks:")
    for i, block in enumerate(coordinator_response_content):
        if block["type"] == "text":
            print(f"  [{i}] text: '{block['text'][:60]}...'")
        else:
            print(f"  [{i}] tool_use: Task(agent_role={block['input']['agent_role']!r}, id={block['id']!r})")

    print("\nRuntime receives this response and:")
    print("  1. Identifies all tool_use blocks with name='Task'")
    print("  2. Executes all three in PARALLEL (concurrent invocations)")
    print("  3. Collects all three tool_results")
    print("  4. Returns them to coordinator in a SINGLE user turn")

    # Show what the coordinator receives back (all three results together)
    all_results_user_turn = {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": "task_call_001",
                "content": '{"agent_role": "web_searcher", "findings": [...], "search_date": "2024-11-01"}',
            },
            {
                "type": "tool_result",
                "tool_use_id": "task_call_002",
                "content": '{"agent_role": "web_searcher", "findings": [...], "search_date": "2024-11-01"}',
            },
            {
                "type": "tool_result",
                "tool_use_id": "task_call_003",
                "content": '{"agent_role": "web_searcher", "findings": [...], "search_date": "2024-11-01"}',
            },
        ],
    }
    print(f"\nCoordinator then receives ONE user turn with {len(all_results_user_turn['content'])} tool_results")
    print("All three parallel tasks complete before coordinator processes any of them")


# ══════════════════════════════════════════════════════════════════
# SECTION 3: COORDINATOR PROMPT DESIGN
# Goals + quality criteria vs step-by-step procedural instructions.
# ══════════════════════════════════════════════════════════════════

# ── BAD: Step-by-step instructions (rigid, breaks when conditions vary)
COORDINATOR_PROMPT_BAD = """You are a research coordinator.

To research a topic:
Step 1: Search for recent news articles about the topic
Step 2: For each article found, extract the key statistics
Step 3: Look for academic papers on the same topic
Step 4: Compare the statistics from news and academic sources
Step 5: Create a summary table of all statistics found
Step 6: Write a 500-word synthesis"""

# Why this fails:
# - What if step 1 finds nothing? Steps 2-5 have nothing to work with.
# - What if the topic has no academic papers? Step 3 is wasted.
# - 500-word synthesis may be wrong length for the query complexity.
# - Model cannot adapt strategy based on what it discovers.
# - Steps constrain the HOW, but the WHAT (quality) is unspecified.


# ── GOOD: Goals + quality criteria (adaptive, enables judgment)
COORDINATOR_PROMPT_GOOD = """You are a research coordinator.

When researching a topic:

COORDINATION PRINCIPLES:
  - Analyse what information is needed before deciding which subagents to spawn
  - Spawn independent research tasks in PARALLEL (multiple Task calls in one response)
  - Pass prior agents' findings explicitly to synthesis agents
  - Adapt your research strategy based on what you discover

RESEARCH QUALITY CRITERIA (apply to all spawned subagents):
  - Prefer sources from the last 2 years
  - Distinguish measured statistics from estimates or projections
  - Flag when data is conflicting across sources
  - Note coverage gaps where evidence was thin

SUBAGENT SELECTION GUIDE:
  - web_searcher:     for current data, news, market reports, recent developments
  - document_analyst: for provided documents, academic papers, technical specs
  - synthesiser:      when you have sufficient web + document findings to combine

TASK INSTRUCTION QUALITY:
  - Include research goals (what the subagent should find)
  - Include quality criteria (what makes a good finding)
  - Include output format (how findings should be structured)
  - Do NOT include step-by-step procedures — the subagent decides its method"""

# Why this works:
# - Model decides which subagents based on actual query needs
# - Criteria ensure quality without constraining method
# - Subagents can adapt their research strategy
# - Parallel spawning is explicitly encouraged
# - Coverage gaps are handled naturally (note them, don't fail)


def compare_coordinator_prompts():
    """Shows the difference between procedural and goals-based prompts."""
    print("\n" + "=" * 65)
    print("COORDINATOR PROMPT DESIGN: Procedural vs Goals-Based")
    print("=" * 65)

    print("\n❌ PROCEDURAL (step-by-step) prompt problems:")
    print("  - Rigid: breaks when step N finds nothing")
    print("  - Prescriptive: prevents subagent from using better strategies")
    print("  - Quality-silent: doesn't specify what 'good' findings look like")
    print("  - No parallelism guidance: tends to produce sequential Task calls")

    print("\n✅ GOALS + CRITERIA prompt benefits:")
    print("  - Adaptive: subagent adjusts strategy to actual findings")
    print("  - Outcome-focused: specifies WHAT to find, not HOW to find it")
    print("  - Quality-explicit: coordinator criteria propagate to all tasks")
    print("  - Parallelism-natural: model decides which tasks are independent")

    print(f"\nProcedural prompt length: {len(COORDINATOR_PROMPT_BAD)} chars")
    print(f"Goals-based prompt length: {len(COORDINATOR_PROMPT_GOOD)} chars")
    print("(Note: goals-based is longer but produces better results)")


# ══════════════════════════════════════════════════════════════════
# SECTION 4: FORK-BASED SESSION MANAGEMENT
# Independent exploration branches from a shared analysis baseline.
# ══════════════════════════════════════════════════════════════════

FORK_SESSION_CONCEPT = """
fork_session: Divergent Exploration from a Shared Baseline
════════════════════════════════════════════════════════════

When to use fork_session vs standard Task spawning:

STANDARD TASK SPAWNING                  FORK_SESSION
──────────────────────                  ─────────────
Different domains, fresh context        Same domain, shared baseline
  coordinator → Task(music)               claude (shared analysis)
  coordinator → Task(film)                  ├── fork_session: approach A
  coordinator → Task(writing)              └── fork_session: approach B

  Each subagent starts empty              Each fork inherits the baseline
  Works from its own research             Works from shared prior analysis

USE WHEN:                               USE WHEN:
  Topics are independent                  Topics share a common foundation
  No shared baseline needed              Expensive analysis done once
  Specialisation by domain                Divergent strategies to compare
  Most multi-agent research               Refactoring approach comparison,
                                          architectural decision comparison

EXAMPLE USE CASES:
  fork_session is best for:
    - "Should we use REST or GraphQL?" (analyse codebase once, fork for each)
    - "Test Jest vs Vitest for this project" (understand project once, fork for each)
    - "Compare microservice vs monolith" (analyse current system once, fork for each)

  Standard Task is best for:
    - "Research AI in music, film, and writing" (independent topics)
    - "Analyse document A and document B" (different inputs)
    - "Check policy and look up order" (completely different domains)
"""


def demonstrate_fork_session_pattern():
    """Shows the fork_session pattern and when to apply it."""
    print("\n" + "=" * 65)
    print("FORK_SESSION: Divergent Exploration from Shared Baseline")
    print("=" * 65)
    print(FORK_SESSION_CONCEPT)

    # CLI usage pattern
    fork_cli_example = """
CLAUDE CODE CLI PATTERN:
────────────────────────
# Step 1: Shared analysis (expensive, done ONCE)
claude "Analyse the authentication module: describe its architecture,
        dependencies, and current test coverage."

# ↑ This analysis is now in the session history.

# Step 2: Fork for approach A (inherits the analysis above)
claude --fork-session auth_baseline \\
  "Based on the analysis, design a JWT token refresh implementation.
   Include tradeoffs vs the current session-based approach."

# Step 3: Fork for approach B (also inherits the same analysis)
claude --fork-session auth_baseline \\
  "Based on the analysis, design an OAuth2 integration.
   Include tradeoffs vs the current session-based approach."

# Each fork:
#   ✓ Inherits the shared auth module analysis
#   ✓ Works independently from the fork point
#   ✗ Does NOT share results with the other fork
#   ✗ Does NOT re-run the expensive analysis step

# Developer reviews both fork outputs and makes decision.
"""
    print(fork_cli_example)

    # SDK equivalent (conceptual)
    print("AGENT SDK EQUIVALENT (conceptual):")
    print("""
# After shared baseline analysis in a coordinator session:
shared_baseline_messages = [
    {"role": "user", "content": "Analyse the auth module..."},
    {"role": "assistant", "content": "[detailed analysis...]"},
]

# Fork A: inherits shared_baseline_messages, adds approach A
fork_a_messages = shared_baseline_messages + [
    {"role": "user", "content": "Design JWT approach based on above..."}
]
response_a = client.messages.create(messages=fork_a_messages, ...)

# Fork B: inherits shared_baseline_messages, adds approach B
fork_b_messages = shared_baseline_messages + [
    {"role": "user", "content": "Design OAuth2 approach based on above..."}
]
response_b = client.messages.create(messages=fork_b_messages, ...)

# Both forks start from the same shared analysis.
# Neither affects the other's context.
""")


# ══════════════════════════════════════════════════════════════════
# SECTION 5: BUILDING A PARALLEL RESEARCH COORDINATOR
# Complete example of a coordinator that spawns multiple subagents
# in parallel to research a multi-faceted topic.
# ══════════════════════════════════════════════════════════════════

@dataclass
class ParallelTaskSpec:
    """Specification for a parallel subagent task."""
    agent_role: str
    instruction: str
    subtopic:    str   # for logging


def build_parallel_research_tasks(topic: str, subtopics: list[str]) -> list[ParallelTaskSpec]:
    """
    Build parallel Task specifications for a multi-subtopic research query.
    All tasks are designed to be run in ONE coordinator response turn.

    Args:
        topic:     The overarching research topic
        subtopics: Independent sub-domains to research in parallel
    """
    tasks = []
    for i, subtopic in enumerate(subtopics):
        instruction = f"""Research the impact of AI on {subtopic} (context: {topic}).

RESEARCH GOALS:
1. Current AI tools and their adoption rate in {subtopic}
2. Measurable impact on workflow, cost, or output quality
3. Professional/practitioner perspectives (adoption vs resistance)
4. Any regulatory, legal, or ethical considerations specific to {subtopic}

QUALITY CRITERIA:
- Sources from 2023 or later strongly preferred
- Distinguish measured statistics from projections
- Include publication date for every finding
- Flag sources that may have commercial bias (vendor reports, etc.)

SCOPE: Focus ONLY on {subtopic} — other subtopics are being researched
       by parallel agents.

OUTPUT: JSON findings array following the standard structured format:
{{
  "findings": [
    {{
      "claim": "...",
      "evidence_excerpt": "...",
      "metadata": {{
        "source_url": "...",
        "document_name": "...",
        "publication_date": "YYYY-MM-DD",
        "source_type": "...",
        "confidence": "measured|estimated|anecdotal"
      }}
    }}
  ],
  "coverage_gaps": ["..."],
  "search_date": "YYYY-MM-DD"
}}"""

        tasks.append(ParallelTaskSpec(
            agent_role="web_searcher",
            instruction=instruction,
            subtopic=subtopic,
        ))

    return tasks


def simulate_parallel_execution(tasks: list[ParallelTaskSpec]) -> dict[str, dict]:
    """
    Simulates parallel task execution timing.
    In production: runtime executes all Task tool calls concurrently.
    Here: shows timing comparison between sequential and parallel.
    """
    print("\n" + "=" * 65)
    print("PARALLEL EXECUTION TIMING SIMULATION")
    print("=" * 65)

    # Simulate task durations (in a real system these vary by query complexity)
    simulated_durations = {task.subtopic: 2.0 + i * 0.5 for i, task in enumerate(tasks)}

    print("\nSimulated task durations:")
    for subtopic, duration in simulated_durations.items():
        print(f"  {subtopic}: {duration:.1f}s")

    # Sequential total
    sequential_total = sum(simulated_durations.values())
    # Parallel total (bottleneck is the slowest)
    parallel_total = max(simulated_durations.values())

    print(f"\nSequential total: {sequential_total:.1f}s (sum of all tasks)")
    print(f"Parallel total:   {parallel_total:.1f}s (slowest task only)")
    print(f"Speedup:          {sequential_total / parallel_total:.1f}x faster")

    # Return simulated results
    return {
        task.subtopic: {
            "findings": [
                {
                    "claim": f"AI adoption in {task.subtopic} grew in 2024",
                    "evidence_excerpt": "Simulated finding for demonstration",
                    "metadata": {
                        "source_url": f"https://example.com/{task.subtopic.replace(' ', '-')}",
                        "document_name": f"{task.subtopic.title()} AI Report 2024",
                        "publication_date": "2024-10-01",
                        "source_type": "industry_report",
                        "confidence": "estimated",
                    },
                }
            ],
            "coverage_gaps": [],
            "search_date": "2024-11-01",
        }
        for task in tasks
    }


def run_parallel_research_demo():
    """
    Complete demo of parallel subagent research on a multi-faceted topic.
    Shows the coordinator → parallel Tasks → synthesis flow.
    """
    print("\n" + "=" * 65)
    print("PARALLEL RESEARCH COORDINATOR DEMO")
    print("=" * 65)

    topic = "Impact of AI on creative industries"
    subtopics = [
        "music production and composition",
        "film production and visual effects",
        "creative writing and journalism",
        "visual arts and graphic design",
    ]

    print(f"\nTopic: {topic}")
    print(f"Subtopics to research in parallel: {len(subtopics)}")
    for s in subtopics:
        print(f"  - {s}")

    # Build parallel tasks
    tasks = build_parallel_research_tasks(topic, subtopics)
    print(f"\n✓ Built {len(tasks)} parallel Task specifications")
    print("  All would be emitted in ONE coordinator response turn")

    # Show what the coordinator response content block looks like
    print("\nCoordinator response.content structure (parallel Tasks):")
    for i, task in enumerate(tasks):
        print(f"  [{i}] tool_use: Task(agent_role='web_searcher', subtopic='{task.subtopic[:30]}...')")

    # Simulate parallel execution
    results = simulate_parallel_execution(tasks)

    print(f"\n✓ All {len(results)} parallel tasks complete")
    print("  All results returned in ONE coordinator user turn")
    print("  Coordinator now has complete coverage across all subtopics")

    # Build synthesis instruction with all parallel results
    combined_findings_json = json.dumps(results, indent=2)
    synthesis_instruction_preview = f"""Synthesise research on '{topic}'.

FINDINGS FROM PARALLEL WEB RESEARCH AGENTS:
{combined_findings_json[:300]}
... ({len(combined_findings_json)} chars total)

SYNTHESIS REQUIREMENTS:
- Cover all {len(subtopics)} subtopics
- Note which areas had stronger/weaker evidence
- Identify cross-domain patterns
- Flag conflicting findings across subtopics"""

    print(f"\nSynthesis instruction size: {len(synthesis_instruction_preview)} chars")
    print("(Passes ALL parallel findings to synthesiser subagent)")


# ══════════════════════════════════════════════════════════════════
# SECTION 6: EXAM-FOCUSED SUMMARY TABLE
# Quick reference for the patterns tested in Q7, Q8, Q9.
# ══════════════════════════════════════════════════════════════════

EXAM_PATTERNS_TABLE = """
EXAM QUICK REFERENCE: Parallel Spawning and fork_session
══════════════════════════════════════════════════════════

PATTERN                          MECHANISM              WHEN
─────────────────────────────────────────────────────────────────
Parallel subagent spawning       Multiple Task calls    Independent topics,
                                 in ONE response        no ordering dependency

Sequential subagent spawning     One Task per           Dependent tasks (B needs
(coordinator chains tasks)       coordinator turn       A's output to proceed)

fork_session                     Branches from a        Same baseline, divergent
                                 shared history         strategies or approaches

Single subagent, no Task         execute_subagent()     Single specialised task,
                                 directly               no coordination needed

─────────────────────────────────────────────────────────────────
Q7 ROOT CAUSE: Coordinator decomposed "creative industries" into
  only visual arts subtopics → music, film, writing never researched.
  Fix: coordinator prompt with BROAD goals, not narrow topic list.

Q9 CORRECT: Give synthesis agent scoped verify_fact tool (not all tools).
  85% simple lookups handled inline.
  15% complex go through coordinator → web_searcher (coordinator routing).
  Principle: least privilege + targeted cross-role tool for high-frequency need.

ALLOWEDTOOLS CHECK: If coordinator "cannot spawn subagents" → check if
  "Task" is in allowedTools. It must be present for Task calls to work.
"""


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Task 1.3 — Parallel Spawning and fork_session")
    print("=" * 65)

    demonstrate_sequential_vs_parallel()
    show_parallel_task_message_structure()
    compare_coordinator_prompts()
    demonstrate_fork_session_pattern()
    run_parallel_research_demo()

    print("\n" + "=" * 65)
    print("EXAM QUICK REFERENCE")
    print(EXAM_PATTERNS_TABLE)
