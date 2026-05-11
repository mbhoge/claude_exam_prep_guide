"""
adaptive_decomposition.py — Dynamic Plans for Open-Ended Investigation Tasks
=============================================================================
Task 1.6: Design Task Decomposition Strategies for Complex Workflows

Adaptive decomposition is the correct strategy when:
  - Task scope is genuinely unknown before execution
  - Each step's findings determine what comes next
  - Dependencies between components aren't known upfront
  - Different inputs require structurally different plans

Canonical exam example:
  "Add comprehensive tests to a legacy codebase"
  → Cannot plan without first mapping what exists
  → Dependencies found mid-execution change the plan
  → Priorities shift as actual coverage gaps are discovered

Run: python adaptive_decomposition.py
"""

import anthropic
import json
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

client = anthropic.Anthropic()


# ══════════════════════════════════════════════════════════════════
# SECTION 1: DATA STRUCTURES FOR ADAPTIVE PLANNING
# ══════════════════════════════════════════════════════════════════

class Priority(str, Enum):
    P1 = "P1"   # Critical: do immediately
    P2 = "P2"   # High: do next
    P3 = "P3"   # Medium: do when P1/P2 complete
    P4 = "P4"   # Low: do if time allows
    BLOCKED = "BLOCKED"  # waiting for dependency


@dataclass
class SubtaskSpec:
    """
    A single item in the adaptive backlog.
    Priority and dependencies can change as new information arrives.
    """
    task_id: str
    description: str
    priority: Priority
    estimated_complexity: str           # small | medium | large
    depends_on: list[str] = field(default_factory=list)  # task_ids
    rationale: str = ""                 # why this priority was assigned
    discovered_at_step: int = 0         # which execution step created this
    status: str = "pending"             # pending | in_progress | complete | blocked


@dataclass
class ModuleInfo:
    """Codebase module discovered during Phase 1 (mapping)."""
    path: str
    line_count: int
    public_functions: list[str]
    dependencies: list[str]             # other modules this imports
    existing_test_file: Optional[str]   # path to existing tests, if any
    estimated_test_coverage: str        # none | low | partial | good
    business_criticality: str           # critical | high | medium | low
    change_frequency: str               # high | medium | low


@dataclass
class AdaptivePlan:
    """
    The living plan — updated throughout execution as new information arrives.
    """
    task_description: str
    phase: str                          # mapping | prioritising | executing | complete
    modules_discovered: list[ModuleInfo] = field(default_factory=list)
    backlog: list[SubtaskSpec] = field(default_factory=list)
    completed_tasks: list[SubtaskSpec] = field(default_factory=list)
    discoveries: list[str] = field(default_factory=list)   # log of findings that changed plan
    current_step: int = 0

    def pending_by_priority(self) -> list[SubtaskSpec]:
        priority_order = [Priority.P1, Priority.P2, Priority.P3, Priority.P4]
        pending = [t for t in self.backlog if t.status == "pending"]
        return sorted(pending, key=lambda t: priority_order.index(t.priority)
                      if t.priority in priority_order else 99)

    def mark_complete(self, task_id: str):
        for task in self.backlog:
            if task.task_id == task_id:
                task.status = "complete"
                self.completed_tasks.append(task)
                # Unblock tasks that were waiting for this one
                for other in self.backlog:
                    if task_id in other.depends_on and other.status == "blocked":
                        remaining_deps = [d for d in other.depends_on
                                          if d not in [t.task_id for t in self.completed_tasks]]
                        if not remaining_deps:
                            other.status = "pending"
                break

    def add_task(self, task: SubtaskSpec):
        """Add a newly discovered task to the backlog."""
        task.discovered_at_step = self.current_step
        self.backlog.append(task)
        self.discoveries.append(
            f"Step {self.current_step}: Added '{task.task_id}' "
            f"(priority {task.priority.value}) — {task.rationale}"
        )

    def summary(self) -> str:
        total = len(self.backlog)
        complete = len(self.completed_tasks)
        pending = len([t for t in self.backlog if t.status == "pending"])
        return f"Phase: {self.phase} | Total: {total} | Complete: {complete} | Pending: {pending}"


# ══════════════════════════════════════════════════════════════════
# SECTION 2: PHASE 1 — MAP
# Explore the codebase before generating any subtasks.
# You cannot plan what you haven't seen.
# ══════════════════════════════════════════════════════════════════

MAPPING_SYSTEM_PROMPT = """You are a codebase archaeologist performing an initial mapping.

YOUR ONLY JOB IN THIS PHASE: understand what exists. Do NOT generate test code yet.

DISCOVER:
  - Every module/file and its purpose
  - Public API of each module (functions, classes, their signatures)
  - Dependencies between modules (import graph)
  - Current test coverage estimates (look for test files)
  - Business criticality indicators (payment? auth? core data models?)
  - Change frequency signals (size, complexity, documentation quality)

OUTPUT: JSON with modules array. Each module:
{
  "path": "relative/path/to/module.py",
  "line_count": 245,
  "public_functions": ["function_name(params) -> return_type"],
  "dependencies": ["other.module", "third.party.lib"],
  "existing_test_file": "tests/test_module.py or null",
  "estimated_test_coverage": "none|low|partial|good",
  "business_criticality": "critical|high|medium|low",
  "change_frequency": "high|medium|low"
}

Be thorough. The mapping determines the entire subsequent plan."""


def phase1_map_codebase(
    codebase_description: str,
    file_listing: str,
) -> list[ModuleInfo]:
    """
    Phase 1: Map what exists before creating any plan.

    This is the 'explore first' step that adaptive decomposition
    requires for open-ended tasks. You cannot prioritise what you
    haven't inventoried.

    Args:
        codebase_description: High-level description of the system
        file_listing:         ls -la or tree output of the codebase
    """
    print("\n" + "=" * 65)
    print("PHASE 1: MAPPING — Exploring codebase structure")
    print("(No subtasks created yet — must see before planning)")
    print("=" * 65)

    prompt = f"""Map this codebase for test coverage planning.

SYSTEM DESCRIPTION:
{codebase_description}

FILE STRUCTURE:
{file_listing}

Analyse this structure and return the module inventory JSON."""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=3000,
        system=MAPPING_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text
    modules = []

    try:
        start = raw.find("[")
        end   = raw.rfind("]") + 1
        if start != -1:
            data = json.loads(raw[start:end])
            for m in data:
                modules.append(ModuleInfo(
                    path=m.get("path", "unknown"),
                    line_count=m.get("line_count", 0),
                    public_functions=m.get("public_functions", []),
                    dependencies=m.get("dependencies", []),
                    existing_test_file=m.get("existing_test_file"),
                    estimated_test_coverage=m.get("estimated_test_coverage", "none"),
                    business_criticality=m.get("business_criticality", "medium"),
                    change_frequency=m.get("change_frequency", "medium"),
                ))
    except (json.JSONDecodeError, KeyError):
        # Parse failed — create a basic module from text
        print("  (Using fallback parsing for mapping output)")

    print(f"\nMapping complete: discovered {len(modules)} module(s)")
    for m in modules:
        cov_icon = "✗" if m.estimated_test_coverage == "none" else "~"
        print(f"  {cov_icon} {m.path} ({m.line_count}L) — "
              f"criticality: {m.business_criticality}, coverage: {m.estimated_test_coverage}")

    return modules


# ══════════════════════════════════════════════════════════════════
# SECTION 3: PHASE 2 — PRIORITISE
# Use mapping output to build a prioritised backlog.
# Priority is based on ACTUAL data, not assumptions.
# ══════════════════════════════════════════════════════════════════

PRIORITISATION_SYSTEM_PROMPT = """You are a test planning strategist.

Given a codebase module inventory, create a prioritised test backlog.

PRIORITISATION CRITERIA (apply in this order):
  P1 (Critical): business-critical modules with zero test coverage
  P2 (High):     security-sensitive or payment-related with low coverage
                 OR high-criticality modules with partial coverage
  P3 (Medium):   medium-criticality with low/no coverage
                 OR utility modules with complex logic
  P4 (Low):      well-covered modules, simple utilities, constants

DEPENDENCY RULES:
  - If module A imports module B and A is P1, B must be at least P2
  - Shared fixtures/helpers that multiple tests need → P1 regardless
  - Test infrastructure (conftest.py, factories) → P1 always

OUTPUT: JSON backlog array:
[
  {
    "task_id": "test_payment_checkout",
    "description": "Write tests for payment/checkout.py",
    "priority": "P1",
    "estimated_complexity": "large",
    "depends_on": [],
    "rationale": "business-critical, 0% coverage, handles payment processing"
  }
]

Order by priority within each tier."""


def phase2_prioritise(
    modules: list[ModuleInfo],
    task_description: str,
) -> list[SubtaskSpec]:
    """
    Phase 2: Convert mapping to prioritised backlog.

    Priorities are based on ACTUAL codebase state from Phase 1,
    not pre-assumed priorities. This is what makes adaptive
    decomposition superior to up-front planning for open-ended tasks.
    """
    print("\n" + "─" * 65)
    print("PHASE 2: PRIORITISING — Building backlog from actual findings")
    print("(Priorities based on Phase 1 data, not assumptions)")
    print("─" * 65)

    module_data = [
        {
            "path": m.path,
            "line_count": m.line_count,
            "public_functions": m.public_functions,
            "dependencies": m.dependencies,
            "existing_test_file": m.existing_test_file,
            "estimated_test_coverage": m.estimated_test_coverage,
            "business_criticality": m.business_criticality,
            "change_frequency": m.change_frequency,
        }
        for m in modules
    ]

    prompt = f"""Task: {task_description}

Module inventory from Phase 1:
{json.dumps(module_data, indent=2)}

Create a prioritised test backlog following the prioritisation criteria."""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2000,
        system=PRIORITISATION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text
    tasks = []

    try:
        start = raw.find("[")
        end   = raw.rfind("]") + 1
        if start != -1:
            data = json.loads(raw[start:end])
            for item in data:
                priority_str = item.get("priority", "P3")
                try:
                    priority = Priority(priority_str)
                except ValueError:
                    priority = Priority.P3

                tasks.append(SubtaskSpec(
                    task_id=item.get("task_id", f"task_{len(tasks)}"),
                    description=item.get("description", ""),
                    priority=priority,
                    estimated_complexity=item.get("estimated_complexity", "medium"),
                    depends_on=item.get("depends_on", []),
                    rationale=item.get("rationale", ""),
                ))
    except (json.JSONDecodeError, KeyError):
        print("  (Fallback: creating default prioritised tasks)")
        # Create basic tasks from module data
        for m in sorted(modules,
                        key=lambda x: (x.business_criticality != "critical",
                                       x.estimated_test_coverage != "none")):
            tasks.append(SubtaskSpec(
                task_id=f"test_{m.path.replace('/', '_').replace('.py', '')}",
                description=f"Write tests for {m.path}",
                priority=Priority.P1 if m.business_criticality == "critical" else Priority.P3,
                estimated_complexity="medium",
                rationale=f"Criticality: {m.business_criticality}, Coverage: {m.estimated_test_coverage}",
            ))

    print(f"\nBacklog created: {len(tasks)} task(s)")
    for task in tasks:
        dep_str = f" [deps: {', '.join(task.depends_on)}]" if task.depends_on else ""
        print(f"  {task.priority.value}: {task.task_id} ({task.estimated_complexity}){dep_str}")
        print(f"       {task.rationale[:70]}")

    return tasks


# ══════════════════════════════════════════════════════════════════
# SECTION 4: PHASE 3 — EXECUTE ADAPTIVELY
# Work through the backlog in priority order.
# Update backlog when new dependencies are discovered.
# ══════════════════════════════════════════════════════════════════

EXECUTION_SYSTEM_PROMPT = """You are an expert test writer for Python code.

Write comprehensive pytest tests for the given module.

REQUIREMENTS:
  - Use pytest fixtures for setup
  - Test happy paths and error cases
  - Test edge cases and boundary conditions
  - Mock external dependencies (databases, APIs, other modules)
  - Follow AAA pattern (Arrange, Act, Assert)
  - Name tests descriptively: test_<function>_<scenario>_<expected_result>

DISCOVERY REPORTING (CRITICAL):
After writing tests, report any NEW dependencies you discovered:
  - Modules you had to mock that may also need testing
  - Shared utilities needed across test files
  - Test fixtures needed by multiple test files
  - Circular dependencies that complicate testing

Format: After the test code, add a JSON block:
```discoveries
{
  "new_dependencies_found": [
    {
      "module": "path/to/module.py",
      "reason": "why this needs attention",
      "suggested_priority": "P1|P2|P3|P4"
    }
  ],
  "shared_fixtures_needed": ["description of fixture"],
  "blocking_issues": ["anything that prevents proper testing"]
}
```"""


def execute_subtask(
    task: SubtaskSpec,
    plan: AdaptivePlan,
    module: Optional[ModuleInfo],
    module_content: str,
) -> tuple[str, list[dict]]:
    """
    Execute a single subtask and report discoveries.

    Returns:
        (generated_tests, new_dependencies_discovered)

    The new_dependencies_discovered are what make this ADAPTIVE —
    they trigger backlog updates for subsequent steps.
    """
    plan.current_step += 1

    print(f"\n{'─'*65}")
    print(f"EXECUTING: {task.task_id} [{task.priority.value}] (Step {plan.current_step})")
    print(f"  {task.description}")
    if task.rationale:
        print(f"  Rationale: {task.rationale}")
    print("─" * 65)

    context = f"""Task: {task.description}

Module to test: {module.path if module else 'see content below'}
"""
    if module:
        context += f"""Module info:
  Public functions: {module.public_functions}
  Dependencies: {module.dependencies}
  Business criticality: {module.business_criticality}
"""

    context += f"""
Module content:
```python
{module_content}
```

Write comprehensive tests. Report new dependencies found."""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=3000,
        system=EXECUTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": context}],
    )

    raw = response.content[0].text

    # Extract generated tests
    test_code = raw
    new_dependencies = []

    # Extract discovery block
    if "```discoveries" in raw:
        disc_start = raw.find("```discoveries") + len("```discoveries")
        disc_end   = raw.find("```", disc_start)
        if disc_end != -1:
            disc_text = raw[disc_start:disc_end].strip()
            test_code = raw[:raw.find("```discoveries")].strip()
            try:
                disc_data = json.loads(disc_text)
                new_dependencies = disc_data.get("new_dependencies_found", [])

                if disc_data.get("shared_fixtures_needed"):
                    print(f"  Shared fixtures needed: {disc_data['shared_fixtures_needed']}")
                if disc_data.get("blocking_issues"):
                    print(f"  ⚠️  Blocking issues: {disc_data['blocking_issues']}")
            except json.JSONDecodeError:
                pass

    print(f"  ✓ Tests generated ({len(test_code.splitlines())} lines)")

    # Report and handle discoveries
    if new_dependencies:
        print(f"  🔍 {len(new_dependencies)} new dependency(ies) discovered:")
        for dep in new_dependencies:
            print(f"     → {dep.get('module')} ({dep.get('suggested_priority')}): "
                  f"{dep.get('reason', '')[:60]}")

    return test_code, new_dependencies


def update_backlog_from_discoveries(
    plan: AdaptivePlan,
    new_dependencies: list[dict],
    completed_task_id: str,
):
    """
    Update the adaptive plan based on newly discovered dependencies.

    This is the core of adaptive decomposition — the plan changes
    as you learn more about the codebase. Each execution step
    can add new tasks or change priorities of existing ones.
    """
    if not new_dependencies:
        return

    print(f"\n  📋 Updating backlog based on Step {plan.current_step} discoveries:")

    for dep in new_dependencies:
        module_path = dep.get("module", "")
        priority_str = dep.get("suggested_priority", "P2")
        reason = dep.get("reason", "dependency discovered")

        # Check if this module is already in the backlog
        existing_ids = [t.task_id for t in plan.backlog]
        new_task_id = f"test_{module_path.replace('/', '_').replace('.py', '')}"

        if new_task_id in existing_ids:
            # Module already in backlog — may need priority upgrade
            for task in plan.backlog:
                if task.task_id == new_task_id and task.status == "pending":
                    old_priority = task.priority
                    try:
                        new_priority = Priority(priority_str)
                    except ValueError:
                        new_priority = Priority.P2

                    # Only upgrade priority, never downgrade
                    priority_order = [Priority.P1, Priority.P2, Priority.P3, Priority.P4]
                    if (priority_order.index(new_priority) <
                            priority_order.index(old_priority)):
                        task.priority = new_priority
                        plan.discoveries.append(
                            f"Step {plan.current_step}: Upgraded {new_task_id} "
                            f"from {old_priority.value} to {new_priority.value} "
                            f"— {reason}"
                        )
                        print(f"     ↑ Upgraded {new_task_id}: "
                              f"{old_priority.value} → {new_priority.value}")
        else:
            # New module not in backlog — add it
            try:
                new_priority = Priority(priority_str)
            except ValueError:
                new_priority = Priority.P2

            new_task = SubtaskSpec(
                task_id=new_task_id,
                description=f"Write tests for {module_path} (dependency found in {completed_task_id})",
                priority=new_priority,
                estimated_complexity="medium",
                depends_on=[],
                rationale=reason,
            )
            plan.add_task(new_task)
            print(f"     + Added {new_task_id} [{new_priority.value}]: {reason[:50]}")


# ══════════════════════════════════════════════════════════════════
# SECTION 5: FULL ADAPTIVE EXECUTION LOOP
# ══════════════════════════════════════════════════════════════════

def run_adaptive_decomposition(
    task_description: str,
    codebase_description: str,
    file_structure: str,
    module_contents: dict[str, str],   # path → content
    max_steps: int = 10,
) -> AdaptivePlan:
    """
    Full three-phase adaptive decomposition.

    Phase 1: Map — explore the codebase without creating any plan
    Phase 2: Prioritise — build backlog from actual findings
    Phase 3: Execute — work through backlog, updating plan as you go

    The key difference from prompt chaining:
    - The backlog at step N is NOT the same as the backlog at step 0
    - Discoveries at execution time change what comes next
    - The plan is living, not static

    Args:
        task_description:   The open-ended task (e.g., "add comprehensive tests")
        codebase_description: High-level system description
        file_structure:     File system listing
        module_contents:    Dict of path → file content
        max_steps:          Safety limit on execution steps
    """
    plan = AdaptivePlan(task_description=task_description, phase="mapping")

    print(f"\n{'='*65}")
    print(f"ADAPTIVE DECOMPOSITION: {task_description}")
    print(f"Strategy: map → prioritise → execute (plan updates as you go)")
    print(f"{'='*65}")

    # ── Phase 1: Map ───────────────────────────────────────────────
    plan.phase = "mapping"
    modules = phase1_map_codebase(codebase_description, file_structure)
    plan.modules_discovered = modules

    # ── Phase 2: Prioritise ────────────────────────────────────────
    plan.phase = "prioritising"
    tasks = phase2_prioritise(modules, task_description)
    for task in tasks:
        plan.backlog.append(task)

    print(f"\nInitial backlog: {len(plan.backlog)} tasks")

    # ── Phase 3: Execute (adaptive) ────────────────────────────────
    plan.phase = "executing"
    steps_taken = 0

    while steps_taken < max_steps:
        # Get highest-priority pending task
        ready_tasks = plan.pending_by_priority()
        if not ready_tasks:
            print("\n✓ All tasks complete (or backlog exhausted)")
            break

        task = ready_tasks[0]
        task.status = "in_progress"

        # Find the corresponding module info and content
        module = next(
            (m for m in plan.modules_discovered if m.path in task.task_id),
            None,
        )
        content = module_contents.get(
            module.path if module else "",
            "# Module content not available for demonstration"
        )

        # Execute and collect discoveries
        test_code, new_deps = execute_subtask(task, plan, module, content)

        # Mark complete
        plan.mark_complete(task.task_id)
        steps_taken += 1

        # Update backlog based on discoveries (THIS IS THE ADAPTIVE PART)
        update_backlog_from_discoveries(plan, new_deps, task.task_id)

        print(f"\n{plan.summary()}")

        # Check if done after updates
        if not plan.pending_by_priority():
            break

    plan.phase = "complete"

    # Print discovery log
    if plan.discoveries:
        print(f"\n{'='*65}")
        print("ADAPTIVE PLAN CHANGES (discoveries that updated the plan):")
        for d in plan.discoveries:
            print(f"  → {d}")

    return plan


# ══════════════════════════════════════════════════════════════════
# SECTION 6: COMPARISON — PROMPT CHAINING vs ADAPTIVE
# Shows the key differences in concrete terms.
# ══════════════════════════════════════════════════════════════════

def compare_approaches():
    """Side-by-side comparison of when each pattern applies."""
    print("\n" + "=" * 65)
    print("PATTERN SELECTION: Prompt Chaining vs Adaptive Decomposition")
    print("=" * 65)

    comparison = """
PROMPT CHAINING                         ADAPTIVE DECOMPOSITION
─────────────────────────────────────── ─────────────────────────────────────────
Structure known BEFORE execution        Structure discovered DURING execution

All subtask types defined upfront       Subtasks generated from findings

Same pipeline for all inputs            Different plan per input

Sequential (or parallel) fixed steps    Plan updates after each step

Reproducible: run on same PR →          Variable: each codebase gets custom plan
same pipeline structure

Good for:                               Good for:
  PR code review (always has files)       "Add tests to legacy codebase"
  Security + style + correctness          "Debug this production issue"
  CI/CD automated pipelines              "Understand this unfamiliar system"
  Any task with known aspects             Open-ended investigations

Failure mode:                           Failure mode:
  Over-engineered for simple tasks        Too slow for predictable tasks
  Brittle if assumptions wrong            Harder to test and reproduce

Example:                                Example:
  PR with 14 files:                       Legacy codebase testing:
    for each file: local analysis pass      Phase 1: discover 23 modules
    after all files: integration pass       Phase 2: prioritise by coverage
    aggregate findings                      Phase 3: execute adaptively
                                              step 3: find new dep
                                              → add to backlog
                                              step 7: dep causes priority shift
                                              → update backlog
"""
    print(comparison)

    print("DECISION RULE:")
    print("  'Do I know what ALL the subtasks are BEFORE I start?'")
    print("  YES → Prompt Chaining")
    print("  NO  → Adaptive Decomposition")


# ══════════════════════════════════════════════════════════════════
# SECTION 7: DEMO WITH SAMPLE CODEBASE
# ══════════════════════════════════════════════════════════════════

SAMPLE_CODEBASE_DESCRIPTION = """
E-commerce backend system (Python/Flask).
Handles payment processing, inventory management, and order fulfillment.
No dedicated test infrastructure exists.
Legacy codebase, mixed age of code, some undocumented dependencies.
"""

SAMPLE_FILE_STRUCTURE = """
payment/
  checkout.py          (312 lines) - primary checkout flow
  tax_calculator.py    (89 lines)  - tax computation
  payment_gateway.py   (156 lines) - Stripe integration
inventory/
  stock_manager.py     (201 lines) - stock tracking
  reservation.py       (134 lines) - hold items during checkout
auth/
  login.py             (78 lines)  - user authentication
  session.py           (45 lines)  - session management
tests/
  test_auth.py         (62 lines)  - exists but incomplete
"""

SAMPLE_MODULE_CONTENTS = {
    "payment/checkout.py": """
def process_checkout(cart, user_id):
    \"\"\"Main checkout flow — coordinates all payment steps.\"\"\"
    stock = check_stock_availability(cart)
    if not stock:
        raise StockUnavailableError()

    tax = calculate_tax(cart, user_id)
    reservation = reserve_items(cart)

    try:
        result = charge_payment_gateway(cart.total + tax, user_id)
        confirm_reservation(reservation)
        return result
    except PaymentError:
        cancel_reservation(reservation)
        raise
""",
    "payment/tax_calculator.py": """
TAX_RATES = {"CA": 0.0725, "NY": 0.08, "TX": 0.0625}

def calculate_tax(cart, user_id):
    user = get_user(user_id)
    rate = TAX_RATES.get(user.state, 0.0)
    return cart.subtotal * rate
""",
}


if __name__ == "__main__":
    compare_approaches()

    print("\n" + "=" * 65)
    print("RUNNING ADAPTIVE DECOMPOSITION ON SAMPLE CODEBASE")
    print("=" * 65)

    plan = run_adaptive_decomposition(
        task_description="Add comprehensive tests to the e-commerce backend",
        codebase_description=SAMPLE_CODEBASE_DESCRIPTION,
        file_structure=SAMPLE_FILE_STRUCTURE,
        module_contents=SAMPLE_MODULE_CONTENTS,
        max_steps=5,  # limit for demo
    )

    print(f"\n{'='*65}")
    print("ADAPTIVE PLAN SUMMARY")
    print(f"{'='*65}")
    print(f"Phase: {plan.phase}")
    print(f"Modules discovered: {len(plan.modules_discovered)}")
    print(f"Total tasks in backlog: {len(plan.backlog)}")
    print(f"Tasks completed: {len(plan.completed_tasks)}")
    print(f"Plan changes (discoveries): {len(plan.discoveries)}")

    if plan.completed_tasks:
        print("\nCompleted:")
        for t in plan.completed_tasks:
            print(f"  ✓ {t.task_id} [{t.priority.value}]")

    remaining = plan.pending_by_priority()
    if remaining:
        print("\nRemaining in backlog:")
        for t in remaining[:5]:
            print(f"  □ {t.task_id} [{t.priority.value}]: {t.description[:60]}")
