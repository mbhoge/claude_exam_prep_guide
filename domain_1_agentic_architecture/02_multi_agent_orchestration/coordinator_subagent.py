"""
Task 1.2 – Multi-Agent Orchestration with Coordinator-Subagent Patterns
========================================================================
Implements the hub-and-spoke architecture directly tested in Exam Scenario 3
(Multi-Agent Research System) and sample Question 7.

Key concepts:
  - Hub-and-spoke: coordinator routes ALL communication
  - Context isolation: subagents receive ONLY explicit context
  - Dynamic subagent selection based on query complexity
  - Overly narrow decomposition → incomplete topic coverage (Q7 root cause)
  - Iterative refinement loops for gap coverage
"""

import anthropic
import json
import asyncio
from dataclasses import dataclass, field
from typing import Optional

client = anthropic.Anthropic()


# ─────────────────────────────────────────────────────────
# SECTION 1: Data structures
# ─────────────────────────────────────────────────────────

@dataclass
class SubagentResult:
    agent_name: str
    task: str
    success: bool
    content: Optional[str] = None
    error: Optional[str] = None
    coverage_gaps: list = field(default_factory=list)


@dataclass
class TaskSpec:
    task_id: str
    agent_role: str
    instruction: str
    context: Optional[dict] = None
    depends_on: list = field(default_factory=list)


# ─────────────────────────────────────────────────────────
# SECTION 2: Subagent (isolated context)
# ─────────────────────────────────────────────────────────

class Subagent:
    """
    A subagent operates with ISOLATED context.
    It receives only what the coordinator explicitly passes.
    It does NOT inherit the coordinator's conversation history.
    """

    SYSTEM_PROMPTS = {
        "web_searcher": """You are a web research specialist.
Search for information on the assigned topic.
Return: structured findings with source URLs, key facts, and dates.
Do NOT attempt document analysis or synthesis — other specialists handle those.""",

        "document_analyst": """You are a document analysis specialist.
Analyse provided documents for key insights, data, and claims.
Return: structured analysis with page references, statistics, and conclusions.
Do NOT search the web — other specialists handle that.""",

        "synthesiser": """You are a research synthesis specialist.
Combine findings from multiple specialists into coherent, well-cited reports.
Identify coverage gaps and note conflicting information explicitly.
Return: structured synthesis with claim-source mappings.""",
    }

    def __init__(self, role: str):
        self.role = role
        self.name = role
        self.system_prompt = self.SYSTEM_PROMPTS.get(role, f"You are a {role} specialist.")

    def execute(self, task: str, context: Optional[dict] = None) -> SubagentResult:
        """
        Execute with ONLY the provided task + context.
        No coordinator history is passed.
        """
        # Build the message — explicit context injection
        if context:
            user_message = (
                f"{task}\n\n"
                f"Context from prior specialists:\n"
                f"{json.dumps(context, indent=2)}"
            )
        else:
            user_message = task

        try:
            response = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=2000,
                system=self.system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )

            return SubagentResult(
                agent_name=self.name,
                task=task,
                success=True,
                content=response.content[0].text,
            )

        except Exception as exc:
            return SubagentResult(
                agent_name=self.name,
                task=task,
                success=False,
                error=str(exc),
            )


# ─────────────────────────────────────────────────────────
# SECTION 3: Coordinator – hub-and-spoke implementation
# ─────────────────────────────────────────────────────────

class ResearchCoordinator:
    """
    Implements hub-and-spoke: ALL inter-subagent communication,
    error handling, and information routing flows through here.

    Subagents NEVER communicate with each other directly.
    """

    def __init__(self):
        self.subagents = {
            "web_searcher":     Subagent("web_searcher"),
            "document_analyst": Subagent("document_analyst"),
            "synthesiser":      Subagent("synthesiser"),
        }
        self.execution_log: list[SubagentResult] = []

    # ── 3a. Task decomposition ────────────────────────────

    def decompose_topic(self, topic: str) -> list[TaskSpec]:
        """
        GOOD decomposition: broad, covering all relevant sub-domains.

        The exam question about "AI in creative industries" shows what happens
        when the coordinator decomposes too narrowly (only visual arts).
        This method deliberately creates broad coverage.
        """
        prompt = f"""You are a research coordinator.
Decompose the following topic into 3-5 broad research areas that together
provide COMPLETE coverage. Avoid focusing on only one sub-domain.

Topic: {topic}

Return JSON array only:
[
  {{
    "task_id": "t1",
    "agent_role": "web_searcher",
    "instruction": "...",
    "depends_on": []
  }}
]"""

        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1000,
            system="You decompose research topics into comprehensive, non-overlapping subtasks.",
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text
        start, end = raw.find("["), raw.rfind("]") + 1
        if start == -1:
            # Fallback: return sensible default decomposition
            return self._default_decomposition(topic)

        try:
            data = json.loads(raw[start:end])
            return [
                TaskSpec(
                    task_id=t["task_id"],
                    agent_role=t["agent_role"],
                    instruction=t["instruction"],
                    depends_on=t.get("depends_on", []),
                )
                for t in data
            ]
        except json.JSONDecodeError:
            return self._default_decomposition(topic)

    def _default_decomposition(self, topic: str) -> list[TaskSpec]:
        """Fallback broad decomposition ensuring complete coverage."""
        return [
            TaskSpec(
                task_id="t1",
                agent_role="web_searcher",
                instruction=f"Research current landscape and major trends: {topic}. "
                            "Cover ALL relevant domains and sub-fields.",
                depends_on=[],
            ),
            TaskSpec(
                task_id="t2",
                agent_role="web_searcher",
                instruction=f"Research challenges, risks, and criticisms regarding: {topic}. "
                            "Include diverse perspectives.",
                depends_on=[],
            ),
            TaskSpec(
                task_id="t3",
                agent_role="synthesiser",
                instruction=f"Synthesise all research on: {topic}. "
                            "Identify coverage gaps and note conflicts.",
                depends_on=["t1", "t2"],
            ),
        ]

    # ── 3b. Execution with dependency ordering ────────────

    def execute_tasks(self, tasks: list[TaskSpec]) -> dict[str, SubagentResult]:
        """
        Execute tasks respecting dependencies.
        Passes prior results as EXPLICIT context (not automatic inheritance).
        """
        results: dict[str, SubagentResult] = {}
        completed: set[str] = set()
        pending = {t.task_id: t for t in tasks}

        while pending:
            # Find tasks whose dependencies are all complete
            ready = [
                t for t in pending.values()
                if all(dep in completed for dep in t.depends_on)
            ]

            if not ready:
                # Circular dependency – break
                break

            for task in ready:
                subagent = self.subagents.get(task.agent_role)
                if not subagent:
                    results[task.task_id] = SubagentResult(
                        agent_name=task.agent_role,
                        task=task.instruction,
                        success=False,
                        error=f"No subagent registered for role '{task.agent_role}'",
                    )
                    completed.add(task.task_id)
                    del pending[task.task_id]
                    continue

                # Build context from completed dependencies ONLY
                context = {}
                for dep_id in task.depends_on:
                    if dep_id in results and results[dep_id].success:
                        # Pass summary, not full content (keep context focused)
                        context[dep_id] = (results[dep_id].content or "")[:800]

                print(f"  → Executing {task.task_id} ({task.agent_role})...")
                result = subagent.execute(task.instruction, context or None)

                self.execution_log.append(result)
                results[task.task_id] = result
                completed.add(task.task_id)
                del pending[task.task_id]

        return results

    # ── 3c. Result aggregation ────────────────────────────

    def aggregate_and_synthesise(
        self, topic: str, results: dict[str, SubagentResult]
    ) -> str:
        """
        Coordinator aggregates ALL subagent results and synthesises final answer.
        Handles conflicts and identifies gaps.
        """
        synthesis_input = f"Research topic: {topic}\n\nSpecialist findings:\n"

        for task_id, result in results.items():
            synthesis_input += f"\n[{task_id} – {result.agent_name}]\n"
            if result.success:
                synthesis_input += result.content or ""
            else:
                synthesis_input += f"FAILED: {result.error}"

        synthesis_input += (
            "\n\nSynthesize these findings into a comprehensive, well-cited report. "
            "Explicitly note any coverage gaps or conflicting information."
        )

        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=3000,
            system="You synthesise multi-source research into clear, complete reports.",
            messages=[{"role": "user", "content": synthesis_input}],
        )
        return response.content[0].text

    # ── 3d. Iterative refinement loop ────────────────────

    def research_with_refinement(
        self, topic: str, max_iterations: int = 2
    ) -> str:
        """
        Coordinator evaluates synthesis for gaps and re-delegates if needed.
        This is the iterative refinement pattern tested in Task 1.2.
        """
        tasks = self.decompose_topic(topic)
        results = self.execute_tasks(tasks)
        synthesis = self.aggregate_and_synthesise(topic, results)

        for iteration in range(max_iterations):
            # Check if synthesis has identified coverage gaps
            gap_prompt = (
                f"Does this research report have significant coverage gaps "
                f"for the topic '{topic}'?\n\n"
                f"Report:\n{synthesis[:1500]}\n\n"
                f"If yes, list 1-3 specific missing areas as JSON array of strings. "
                f"If no gaps, return empty array []."
            )

            gap_response = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=300,
                messages=[{"role": "user", "content": gap_prompt}],
            )

            raw = gap_response.content[0].text
            start, end = raw.find("["), raw.rfind("]") + 1
            gaps = json.loads(raw[start:end]) if start != -1 else []

            if not gaps:
                break  # Coverage sufficient

            print(f"  Iteration {iteration + 1}: filling gaps – {gaps}")

            # Re-delegate targeted gap queries
            gap_tasks = [
                TaskSpec(
                    task_id=f"gap_{i}",
                    agent_role="web_searcher",
                    instruction=f"Research this specific gap in '{topic}': {gap}",
                    depends_on=[],
                )
                for i, gap in enumerate(gaps)
            ]

            gap_results = self.execute_tasks(gap_tasks)
            results.update(gap_results)
            synthesis = self.aggregate_and_synthesise(topic, results)

        return synthesis

    # ── 3e. Main orchestration entry point ────────────────

    def orchestrate(self, topic: str) -> str:
        print(f"\nCoordinator: Researching '{topic}'")
        print("Step 1: Decomposing topic...")
        tasks = self.decompose_topic(topic)
        print(f"  Created {len(tasks)} tasks")

        print("Step 2: Executing tasks (with dependency ordering)...")
        results = self.execute_tasks(tasks)

        print("Step 3: Aggregating and synthesising...")
        return self.aggregate_and_synthesise(topic, results)


# ─────────────────────────────────────────────────────────
# SECTION 4: Demonstrating the Q7 anti-pattern
# ─────────────────────────────────────────────────────────

def demonstrate_narrow_decomposition_problem():
    """
    Reproduces the exact failure in Sample Question 7:
    Topic = "impact of AI on creative industries"
    Bad coordinator decomposes into ONLY visual arts subtasks.
    Result: music, writing, film production are missing entirely.
    """

    # ❌ BAD decomposition – coordinator only sees visual arts
    bad_tasks = [
        TaskSpec("t1", "web_searcher", "Research AI in digital art creation", []),
        TaskSpec("t2", "web_searcher", "Research AI in graphic design", []),
        TaskSpec("t3", "web_searcher", "Research AI in photography", []),
        # Missing: music, writing, film, gaming, theatre...
    ]
    print("❌ Bad decomposition covers only:", [t.instruction for t in bad_tasks])

    # ✅ GOOD decomposition – broad, exhaustive coverage
    good_tasks = [
        TaskSpec("t1", "web_searcher",
                 "Research AI impact on visual arts (digital art, graphic design, photography, illustration)", []),
        TaskSpec("t2", "web_searcher",
                 "Research AI impact on music, audio production, and performing arts", []),
        TaskSpec("t3", "web_searcher",
                 "Research AI impact on writing, journalism, screenwriting, and literary arts", []),
        TaskSpec("t4", "web_searcher",
                 "Research AI impact on film, video production, gaming, and interactive media", []),
        TaskSpec("t5", "synthesiser",
                 "Synthesise ALL creative industry impacts into a comprehensive report",
                 ["t1", "t2", "t3", "t4"]),
    ]
    print("✅ Good decomposition covers:", [t.instruction[:60] for t in good_tasks])


# ─────────────────────────────────────────────────────────
# SECTION 5: Context isolation demonstration
# ─────────────────────────────────────────────────────────

def demonstrate_context_isolation():
    """
    Shows exactly what a subagent receives vs what it doesn't.
    This directly tests the 'isolated context' knowledge point.
    """

    # What the COORDINATOR knows (full state)
    coordinator_knows = {
        "original_query": "Research impact of AI on creative industries",
        "conversation_history": ["turn 1...", "turn 2..."],
        "other_subagents_running": ["web_searcher", "document_analyst"],
        "budget_remaining_usd": 4.50,
        "api_keys": {"internal_db": "secret-key"},  # NEVER share this
    }

    # What the SUBAGENT receives (minimal, task-specific only)
    subagent_receives = {
        # Task instruction — explicit
        "task": "Research AI in music production",
        # Relevant context from prior subagent — explicit
        "prior_visual_arts_findings": "AI is used in digital art via tools like Midjourney...",
        # NOTE: coordinator_knows above is NOT passed
    }

    print("Coordinator state keys:", list(coordinator_knows.keys()))
    print("Subagent receives keys:", list(subagent_receives.keys()))
    print("\nSubagent does NOT automatically get:")
    for key in coordinator_knows:
        if key not in subagent_receives:
            print(f"  ✗ {key}")


# ─────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Context Isolation Demo ===")
    demonstrate_context_isolation()

    print("\n=== Narrow Decomposition Anti-Pattern Demo ===")
    demonstrate_narrow_decomposition_problem()

    # Uncomment to run actual API calls:
    # coordinator = ResearchCoordinator()
    # report = coordinator.orchestrate("impact of AI on creative industries")
    # print("\nFinal Report:\n", report)
