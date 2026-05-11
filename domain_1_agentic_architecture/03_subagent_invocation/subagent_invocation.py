"""
subagent_invocation.py — Core Mechanics: Task Tool, AgentDefinition, Context Isolation
=======================================================================================
Task 1.3: Configure Subagent Invocation, Context Passing, and Spawning

This file covers the foundational mechanics:
  1. Task tool structure and the allowedTools requirement
  2. AgentDefinition configuration for each subagent type
  3. Context isolation — what subagents inherit (nothing) and what they receive
  4. Dispatching subagents and processing their results in the agentic loop

Run: python subagent_invocation.py
"""

import anthropic
import json
from dataclasses import dataclass, field
from typing import Optional

client = anthropic.Anthropic()


# ══════════════════════════════════════════════════════════════════
# SECTION 1: AGENT DEFINITIONS
# Each definition establishes a subagent's identity, expertise,
# boundaries, and tool access. The coordinator uses these templates
# to decide which subagent to spawn and how to configure it.
# ══════════════════════════════════════════════════════════════════

@dataclass
class AgentDefinition:
    """
    Template that defines a subagent type.

    'description'    — used by the coordinator to decide which agent to spawn
    'system_prompt'  — the subagent's expertise, constraints, and output rules
    'allowed_tools'  — ONLY tools relevant to this agent's specialisation
    """
    name: str
    description: str
    system_prompt: str
    allowed_tools: list[str] = field(default_factory=list)


# ── Research pipeline agent definitions ───────────────────────────

WEB_SEARCHER = AgentDefinition(
    name="web_searcher",
    description=(
        "Searches the web for current, factual information on a topic. "
        "Returns structured findings with source attribution. "
        "Use for: recent data, news, statistics, current competitive landscape."
    ),
    system_prompt="""You are a web research specialist.

EXPERTISE: Finding current, well-sourced factual information.
BOUNDARY: Do NOT analyse, synthesise, or draw strategic conclusions.
          Other specialists handle that — your job is raw information gathering.

OUTPUT FORMAT — return only valid JSON:
{
  "findings": [
    {
      "claim": "specific factual statement",
      "evidence_excerpt": "brief quote or data point from source",
      "metadata": {
        "source_url": "https://...",
        "document_name": "Article/Report Title",
        "publication_date": "YYYY-MM-DD",
        "source_type": "news|industry_report|academic|government",
        "confidence": "measured|estimated|anecdotal"
      }
    }
  ],
  "coverage_gaps": ["topics where no good sources were found"],
  "search_date": "YYYY-MM-DD"
}

If you cannot find reliable information, say so in coverage_gaps rather
than fabricating sources.""",
    allowed_tools=["web_search", "fetch_url"],
    # NOT: write_file, process_refund, Task (no subagent spawning from subagents)
)


DOCUMENT_ANALYST = AgentDefinition(
    name="document_analyst",
    description=(
        "Analyses provided documents for key insights, data, and claims. "
        "Returns structured findings with page-level attribution. "
        "Use for: academic papers, reports, technical documents, whitepapers."
    ),
    system_prompt="""You are a document analysis specialist.

EXPERTISE: Extracting claims, statistics, and conclusions from document text.
BOUNDARY: Do NOT search the web. Work ONLY with documents provided in your prompt.
          Do NOT infer beyond what the documents state.

OUTPUT FORMAT — return only valid JSON:
{
  "findings": [
    {
      "claim": "specific factual statement from the document",
      "evidence_excerpt": "relevant quote from the document",
      "metadata": {
        "source_url": null,
        "document_name": "exact document name as provided",
        "page_number": 12,
        "section": "section title if available",
        "publication_date": "YYYY-MM-DD if stated",
        "confidence": "measured|estimated|author_opinion"
      }
    }
  ],
  "coverage_gaps": ["topics mentioned but not covered in depth"],
  "documents_analysed": ["list of document names"]
}""",
    allowed_tools=["read_file"],
    # NOT: web_search (boundary enforcement via tool restriction)
)


SYNTHESISER = AgentDefinition(
    name="synthesiser",
    description=(
        "Synthesises findings from multiple research agents into a coherent, "
        "cited report. Preserves source attribution throughout. "
        "Use for: final report generation after web and document research."
    ),
    system_prompt="""You are a research synthesis specialist.

EXPERTISE: Combining multi-source findings into coherent, well-structured reports.
BOUNDARY: Do NOT search the web or read documents.
          Work ONLY from the findings provided in your prompt.
          Do NOT add claims not present in the provided findings.

ATTRIBUTION RULES:
  - Every claim in your output MUST cite its source from the provided findings
  - If two sources conflict, present BOTH values with their sources — do not choose
  - Note coverage gaps where topic areas lacked good sources

OUTPUT FORMAT:
  Structured report with:
  1. Executive summary (3-5 sentences, no citations needed)
  2. Key findings (each with inline citation: [Source: document_name, p.X])
  3. Conflicting findings (both values, both sources)
  4. Coverage gaps (topics where evidence was absent or thin)
  5. Confidence assessment (overall data quality)""",
    allowed_tools=[],
    # No tools — synthesiser works entirely from provided context
)


AGENT_REGISTRY: dict[str, AgentDefinition] = {
    "web_searcher":     WEB_SEARCHER,
    "document_analyst": DOCUMENT_ANALYST,
    "synthesiser":      SYNTHESISER,
}


# ══════════════════════════════════════════════════════════════════
# SECTION 2: THE TASK TOOL DEFINITION
# This is what the coordinator sees. It calls Task to spawn subagents.
# The coordinator's allowedTools MUST include "Task".
# ══════════════════════════════════════════════════════════════════

TASK_TOOL_DEFINITION = {
    "name": "Task",
    "description": (
        "Spawn a specialised subagent to handle a focused subtask. "
        "The subagent receives ONLY what you include in 'instruction' — "
        "it has no access to this conversation or any other context. "
        "Available roles: web_searcher, document_analyst, synthesiser."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "agent_role": {
                "type": "string",
                "enum": ["web_searcher", "document_analyst", "synthesiser"],
                "description": "Which specialised subagent to spawn",
            },
            "instruction": {
                "type": "string",
                "description": (
                    "Complete instructions for the subagent, including: "
                    "the specific task, all necessary context, research goals, "
                    "quality criteria, and output format requirements. "
                    "The subagent sees ONLY this field — include everything it needs."
                ),
            },
        },
        "required": ["agent_role", "instruction"],
    },
}


# ══════════════════════════════════════════════════════════════════
# SECTION 3: COORDINATOR TOOL SET
# The coordinator gets the Task tool PLUS any other tools it needs.
# "Task" in allowedTools is what enables subagent spawning.
# ══════════════════════════════════════════════════════════════════

# ✅ CORRECT: "Task" included — coordinator CAN spawn subagents
COORDINATOR_TOOLS = [
    TASK_TOOL_DEFINITION,
    # Coordinator may also have its own direct tools:
    {
        "name": "check_coverage",
        "description": "Evaluate whether research findings cover the topic adequately",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "findings_summary": {"type": "string"},
            },
            "required": ["topic", "findings_summary"],
        },
    },
]

# ❌ WRONG: missing "Task" — coordinator CANNOT spawn subagents
COORDINATOR_TOOLS_BROKEN = [
    # Task tool not included — subagent spawning silently impossible
    {"name": "web_search", "description": "...", "input_schema": {}},
]


# ══════════════════════════════════════════════════════════════════
# SECTION 4: CONTEXT ISOLATION DEMONSTRATION
# Shows exactly what a subagent receives vs what it doesn't.
# ══════════════════════════════════════════════════════════════════

def demonstrate_context_isolation():
    """
    Visualises the isolation boundary between coordinator and subagent.
    This is the most important concept in Task 1.3.
    """
    print("\n" + "=" * 65)
    print("CONTEXT ISOLATION: What Does a Subagent Actually See?")
    print("=" * 65)

    # Everything the coordinator knows at the point of spawning
    coordinator_full_state = {
        "original_user_query":    "Research AI impact on creative industries",
        "conversation_history":   ["Turn 1...", "Turn 2...", "Turn 3..."],
        "prior_web_findings":     {"music": {...}, "visual_arts": {...}},
        "prior_doc_findings":     {"paper_1": {...}, "paper_2": {...}},
        "budget_remaining_usd":   4.20,
        "other_subagents_running": ["web_searcher_music", "web_searcher_film"],
        "api_keys":               {"internal_db": "secret-key-123"},
        "session_turn_count":     7,
    }

    print("\n✗ What the subagent does NOT inherit automatically:")
    for key in coordinator_full_state:
        print(f"  ✗  coordinator.{key}")

    # What the coordinator explicitly includes in the Task instruction
    explicit_instruction = """Research the impact of AI on music production and composition.

CONTEXT PROVIDED:
- Related finding from web search: "AI music tools grew 340% in 2024"
- Scope: focus on professional music production, not consumer tools

RESEARCH GOALS:
1. Current AI tools used by professional music producers
2. Impact on production workflows and time-to-market
3. Artist perspectives (adoption vs resistance)

QUALITY CRITERIA:
- Sources from 2023 or later preferred
- Include quantitative data where available
- Flag estimated vs measured statistics

OUTPUT FORMAT: structured JSON with findings array (see role instructions)"""

    print("\n✓ What the subagent DOES receive (from Task instruction only):")
    print(f"  ✓  Explicit instruction ({len(explicit_instruction)} chars)")
    print(f"  ✓  AgentDefinition system_prompt (via role)")
    print(f"  ✓  allowed_tools for its role")
    print("\n  Everything else: ✗ not inherited, ✗ not visible, ✗ not accessible")

    print("\nKey exam point:")
    print("  If a subagent needs data from a prior subagent, the COORDINATOR")
    print("  must explicitly include that data in the Task instruction.")
    print("  There is no shared memory, no message bus, no implicit passing.")


# ══════════════════════════════════════════════════════════════════
# SECTION 5: SUBAGENT EXECUTOR
# Runs a subagent by invoking Claude with the AgentDefinition's
# system prompt and the explicit instruction.
# ══════════════════════════════════════════════════════════════════

def execute_subagent(agent_role: str, instruction: str) -> dict:
    """
    Execute a subagent invocation.

    Args:
        agent_role:   which AgentDefinition to use
        instruction:  complete task + context (must be self-contained)

    Returns:
        Parsed result from the subagent (JSON if structured output requested)
    """
    defn = AGENT_REGISTRY.get(agent_role)
    if not defn:
        return {"error": f"Unknown agent role: {agent_role}"}

    # Build tool list from allowed_tools (only role-relevant tools)
    tools = _build_tool_list_for_role(defn.allowed_tools)

    # The subagent starts with an EMPTY conversation — only its system prompt
    # and the instruction. No coordinator history. No prior subagent results.
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2000,
        system=defn.system_prompt,           # AgentDefinition expertise
        tools=tools if tools else [],         # Role-restricted tools only
        messages=[
            {
                "role": "user",
                "content": instruction,       # Everything the subagent needs
                # ↑ This is the ONLY context the subagent has
            }
        ],
    )

    raw_text = next(
        (b.text for b in response.content if hasattr(b, "text")), ""
    )

    # Attempt to parse JSON output (structured finding format)
    try:
        start = raw_text.find("{")
        end   = raw_text.rfind("}") + 1
        if start != -1 and end > start:
            return {"success": True, "data": json.loads(raw_text[start:end]), "raw": raw_text}
    except json.JSONDecodeError:
        pass

    return {"success": True, "data": None, "raw": raw_text}


def _build_tool_list_for_role(allowed_tool_names: list[str]) -> list[dict]:
    """Build tool definition list for a given set of tool names."""
    tool_definitions = {
        "web_search": {
            "name": "web_search",
            "description": "Search the web for current information",
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
        "read_file": {
            "name": "read_file",
            "description": "Read a document file",
            "input_schema": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    }
    return [tool_definitions[name] for name in allowed_tool_names if name in tool_definitions]


# ══════════════════════════════════════════════════════════════════
# SECTION 6: COORDINATOR AGENTIC LOOP WITH TASK TOOL
# Shows how the coordinator uses Task calls in its own agentic loop.
# ══════════════════════════════════════════════════════════════════

def run_coordinator_with_subagents(user_query: str) -> str:
    """
    Coordinator agentic loop that dispatches to subagents via Task tool.

    The coordinator:
    1. Receives the query
    2. Analyses what research is needed
    3. Spawns appropriate subagents (via Task tool calls)
    4. Collects results
    5. Synthesises (possibly via a synthesis subagent)
    """
    # Coordinator system prompt: goals + quality criteria, not step-by-step
    coordinator_system = """You are a research coordinator.

Your job is to:
  1. Analyse the research question and determine what information is needed
  2. Spawn appropriate specialist subagents using the Task tool
  3. Collect their findings and synthesise a comprehensive answer

When spawning subagents:
  - Provide complete, self-contained instructions (they inherit nothing from here)
  - Include research goals and quality criteria, not step-by-step procedures
  - Spawn parallel agents (multiple Task calls at once) for independent topics
  - Pass prior agents' findings explicitly to later agents

Available subagent roles:
  - web_searcher:     finds current web-based information
  - document_analyst: analyses provided documents
  - synthesiser:      combines findings into a coherent report"""

    messages = [{"role": "user", "content": user_query}]
    all_subagent_results: dict[str, dict] = {}

    print(f"\n{'='*65}")
    print(f"COORDINATOR: Processing '{user_query[:60]}...'")
    print("="*65)

    for turn in range(10):
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=3000,
            system=coordinator_system,
            tools=COORDINATOR_TOOLS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            final = next(
                (b.text for b in response.content if hasattr(b, "text")), ""
            )
            print(f"\n✓ FINAL ANSWER:\n{final[:500]}...")
            return final

        # Process Task tool calls
        tool_results = []
        task_calls = [b for b in response.content if b.type == "tool_use"]
        print(f"\nTurn {turn+1}: {len(task_calls)} tool call(s)")

        for call in task_calls:
            if call.name == "Task":
                role        = call.input["agent_role"]
                instruction = call.input["instruction"]
                print(f"  → Spawning {role} ({len(instruction)} char instruction)")

                result = execute_subagent(role, instruction)
                all_subagent_results[f"{role}_{turn}"] = result

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": json.dumps(result, default=str),
                })
            else:
                # Handle other coordinator tools
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": call.id,
                    "content": '{"status": "ok"}',
                })

        messages.append({"role": "user", "content": tool_results})

    return "Max turns reached"


# ══════════════════════════════════════════════════════════════════
# SECTION 7: ANTI-PATTERN DEMONSTRATIONS
# ══════════════════════════════════════════════════════════════════

def antipattern_missing_task_in_allowed_tools():
    """❌ WRONG: coordinator cannot spawn subagents."""
    print("\n❌ ANTIPATTERN: Task tool missing from allowedTools")
    coordinator_no_task = AgentDefinition(
        name="broken_coordinator",
        description="Tries to be a coordinator",
        system_prompt="You coordinate research by spawning subagents.",
        allowed_tools=["web_search", "read_file"],  # Task NOT included!
    )
    print(f"   allowed_tools: {coordinator_no_task.allowed_tools}")
    print("   Result: any Task call → 'unknown tool' error at runtime")
    print("   Fix: add 'Task' to allowed_tools")


def antipattern_vague_instruction():
    """❌ WRONG: instruction too vague — subagent has no context."""
    print("\n❌ ANTIPATTERN: Vague Task instruction")

    vague = "Research the market."
    print(f"   Instruction: '{vague}'")
    print("   Subagent problems:")
    print("     - Which market? (no topic)")
    print("     - What aspect? (no research goals)")
    print("     - What format? (no output spec)")
    print("     - What time period? (no quality criteria)")
    print("   Fix: include topic, goals, criteria, and output format")


def antipattern_assuming_inherited_context():
    """❌ WRONG: assumes subagent knows prior results."""
    print("\n❌ ANTIPATTERN: Assuming inherited context")

    bad_instruction = "Based on the web search results, analyse the competitive landscape."
    print(f"   Instruction: '{bad_instruction}'")
    print("   Problem: subagent has NO access to 'the web search results'")
    print("   The phrase 'based on the web search results' refers to data")
    print("   the subagent has never seen.")
    print("   Fix: include the actual web search results in the instruction text")

    good_instruction = """Analyse the competitive landscape for entry into the European cloud storage market.

WEB SEARCH RESULTS (from web_searcher, collected 2024-11-01):
{
  "findings": [
    {"claim": "AWS holds 32% EU market share", "source_url": "...", "date": "2024-09"},
    {"claim": "GDPR compliance is primary adoption barrier", "source_url": "...", "date": "2024-10"}
  ]
}

Based on these findings, provide competitive landscape analysis."""

    print(f"\n   ✅ CORRECT: actual findings included in instruction")
    print(f"   Instruction length: {len(good_instruction)} chars (includes data)")


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Task 1.3 — Subagent Invocation Core Mechanics")
    print("=" * 65)

    # Section 4: Context isolation
    demonstrate_context_isolation()

    # Section 7: Anti-patterns
    antipattern_missing_task_in_allowed_tools()
    antipattern_vague_instruction()
    antipattern_assuming_inherited_context()

    # Section 6: Full coordinator loop (uncomment to call API)
    # run_coordinator_with_subagents("Research AI impact on the creative industries")

    print("\n✓ Core mechanics demonstrated. See context_passing.py for")
    print("  structured finding formats, and parallel_spawning.py for")
    print("  parallel Task emission and fork_session patterns.")
