"""
Task 1.3 – Subagent Invocation, Context Passing, and Spawning
==============================================================
Covers:
  - Task tool as the spawning mechanism (allowedTools must include "Task")
  - Explicit context passing (no automatic inheritance)
  - AgentDefinition configuration
  - Parallel subagent spawning via multiple Task calls in ONE response
  - Structured data formats to preserve attribution (source URLs, page numbers)
"""

import anthropic
import json

client = anthropic.Anthropic()


# ─────────────────────────────────────────────────────────
# SECTION 1: The Task tool definition
# ─────────────────────────────────────────────────────────
# The Task tool is how coordinators spawn subagents.
# The coordinator's allowedTools MUST include "Task".

TASK_TOOL = {
    "name": "Task",
    "description": (
        "Spawn a subagent to handle a specific research or analysis task. "
        "The subagent receives only the context you explicitly provide. "
        "Use for tasks that benefit from isolated context and specialised focus."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "agent_role": {
                "type": "string",
                "description": "Role of the subagent (web_searcher, document_analyst, synthesiser)",
            },
            "instruction": {
                "type": "string",
                "description": "Detailed task instruction for the subagent",
            },
            "context": {
                "type": "string",
                "description": "Prior findings to pass explicitly. Subagent has no other context.",
            },
        },
        "required": ["agent_role", "instruction"],
    },
}


# ─────────────────────────────────────────────────────────
# SECTION 2: AgentDefinition configuration
# ─────────────────────────────────────────────────────────

AGENT_DEFINITIONS = {
    "web_searcher": {
        "description": "Searches the web for current information on a topic",
        "system_prompt": """You are a web research specialist.
Your ONLY job: find relevant information on the assigned topic.
Return structured findings: facts, source URLs, dates.
Do NOT analyse documents or synthesise — other agents handle that.""",
        "allowed_tools": ["web_search"],  # Tool restriction per role
    },
    "document_analyst": {
        "description": "Analyses provided documents for key insights",
        "system_prompt": """You are a document analysis specialist.
Analyse the provided documents carefully.
Return: key claims, statistics, page references, conclusions.
Do NOT search the web — only work with provided documents.""",
        "allowed_tools": ["read_file"],
    },
    "synthesiser": {
        "description": "Synthesises findings from multiple specialists into reports",
        "system_prompt": """You are a research synthesis specialist.
Combine provided findings into coherent, well-cited reports.
Preserve source attribution for every claim.
Flag conflicting information and coverage gaps explicitly.""",
        "allowed_tools": [],  # Synthesiser needs no tools — works from provided context
    },
}


# ─────────────────────────────────────────────────────────
# SECTION 3: Explicit context passing (no automatic inheritance)
# ─────────────────────────────────────────────────────────

def build_subagent_prompt(
    instruction: str,
    prior_findings: dict | None = None,
    research_goals: str = "",
    quality_criteria: str = "",
) -> str:
    """
    Build a subagent prompt that EXPLICITLY includes all needed context.

    Key exam point: subagents do NOT automatically inherit parent context.
    Every piece of context must be explicitly injected here.
    """
    parts = []

    if research_goals:
        parts.append(f"RESEARCH GOALS:\n{research_goals}")

    if quality_criteria:
        parts.append(f"QUALITY CRITERIA:\n{quality_criteria}")

    parts.append(f"YOUR TASK:\n{instruction}")

    if prior_findings:
        parts.append("CONTEXT FROM PRIOR SPECIALISTS:")
        for source, content in prior_findings.items():
            # Structured format separates content from metadata
            parts.append(
                f"\n[Source: {source}]\n"
                f"Content: {content.get('content', '')[:600]}\n"
                f"Source URL: {content.get('url', 'N/A')}\n"
                f"Date: {content.get('date', 'N/A')}"
            )

    return "\n\n".join(parts)


# ─────────────────────────────────────────────────────────
# SECTION 4: Parallel subagent spawning
# ─────────────────────────────────────────────────────────

def spawn_parallel_subagents(topic: str) -> list:
    """
    Coordinator emits MULTIPLE Task tool calls in a SINGLE response
    to spawn subagents in parallel.

    Key exam point: parallel spawning = multiple Task calls in ONE turn,
    NOT one Task call per turn.
    """
    # Coordinator prompt designed around GOALS not step-by-step instructions
    coordinator_prompt = f"""You are a research coordinator.
Research topic: {topic}

Spawn the appropriate subagents in PARALLEL by calling the Task tool
multiple times in this single response. Assign distinct subtopics to
each agent to minimise duplication.

Research goals:
1. Complete coverage of all relevant sub-domains
2. Current information (within last 2 years)
3. Diverse source types

Quality criteria:
- Each agent covers a distinct angle
- No agent duplicates another's scope
- Together they cover the full topic"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2000,
        tools=[TASK_TOOL],
        messages=[{"role": "user", "content": coordinator_prompt}],
    )

    # Extract all Task tool calls from the single response
    task_calls = [
        block for block in response.content
        if block.type == "tool_use" and block.name == "Task"
    ]

    print(f"Coordinator spawned {len(task_calls)} subagents in parallel")
    return task_calls


# ─────────────────────────────────────────────────────────
# SECTION 5: Structured data with attribution
# ─────────────────────────────────────────────────────────

def structured_finding_with_attribution(
    claim: str,
    evidence: str,
    source_url: str,
    document_name: str,
    page_number: int | None,
    publication_date: str,
) -> dict:
    """
    Structured format that separates content from metadata.
    Preserves attribution through synthesis stages.

    This is the format subagents should output so the synthesis
    agent can cite sources accurately.
    """
    return {
        "claim": claim,
        "evidence_excerpt": evidence,
        "metadata": {
            "source_url": source_url,
            "document_name": document_name,
            "page_number": page_number,
            "publication_date": publication_date,
        },
    }


def pass_findings_to_synthesiser(web_results: list, doc_results: list) -> str:
    """
    Coordinator aggregates prior agent results and passes them
    EXPLICITLY to the synthesiser subagent.
    """
    # Combine findings with full attribution
    all_findings = {
        "web_search_findings": web_results,
        "document_analysis_findings": doc_results,
    }

    synthesiser_prompt = build_subagent_prompt(
        instruction=(
            "Synthesise all provided findings into a comprehensive, cited report. "
            "Preserve source attribution for every claim. "
            "Note conflicting statistics with both values and their sources."
        ),
        prior_findings={
            "web_search": {
                "content": json.dumps(web_results[:3], indent=2),
                "url": "multiple",
                "date": "2024-2025",
            },
            "document_analysis": {
                "content": json.dumps(doc_results[:3], indent=2),
                "url": "provided documents",
                "date": "see individual findings",
            },
        },
        quality_criteria=(
            "- Every claim must cite its source\n"
            "- Conflicting data must be presented with both values\n"
            "- Coverage gaps must be noted explicitly"
        ),
    )

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=3000,
        system=AGENT_DEFINITIONS["synthesiser"]["system_prompt"],
        messages=[{"role": "user", "content": synthesiser_prompt}],
    )

    return response.content[0].text


# ─────────────────────────────────────────────────────────
# SECTION 6: fork_session pattern
# ─────────────────────────────────────────────────────────
# fork_session is used to explore divergent approaches from a
# shared baseline without contaminating each branch.
#
# Claude Code CLI equivalent:
#   claude --fork-session "explore approach A"
#   claude --fork-session "explore approach B"
#
# Both forks share the analysis done BEFORE the fork,
# but their outputs don't affect each other.

FORK_SESSION_EXAMPLE = """
# Pseudocode – fork_session usage pattern

# Step 1: Shared baseline analysis (e.g., codebase exploration)
claude "Analyse the authentication module and summarise its structure"

# Step 2: Fork into two independent exploration branches
fork_A = fork_session("Evaluate approach: JWT token refresh strategy")
fork_B = fork_session("Evaluate approach: session-based authentication")

# Both forks inherit the shared analysis but work independently
# Results are compared by the coordinator/developer
"""


# ─────────────────────────────────────────────────────────
# Demo
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Show a structured finding
    finding = structured_finding_with_attribution(
        claim="AI-generated music now accounts for 12% of streaming plays",
        evidence="Platform data from 2024 shows a significant rise in AI-composed tracks...",
        source_url="https://example.com/music-ai-report-2024",
        document_name="Global Music AI Report 2024",
        page_number=47,
        publication_date="2024-11-15",
    )
    print("Structured finding with attribution:")
    print(json.dumps(finding, indent=2))
