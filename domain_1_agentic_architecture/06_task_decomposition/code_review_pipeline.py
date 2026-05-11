"""
code_review_pipeline.py — Production CI Pipeline with Both Decomposition Patterns
==================================================================================
Task 1.6: Design Task Decomposition Strategies for Complex Workflows

This file shows both patterns working together in a realistic CI scenario:
  - Prompt chaining for the code review itself (known structure, reproducible)
  - Adaptive decomposition for test gap analysis (unknown scope upfront)

Also demonstrates:
  - Pattern selection logic (decision function)
  - CI/CD integration with -p flag and --output-format json
  - Session context isolation for independent review instances
  - Q12 sample question scenario: single-pass vs multi-pass review

Run: python code_review_pipeline.py
"""

import anthropic
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

client = anthropic.Anthropic()


# ══════════════════════════════════════════════════════════════════
# SECTION 1: DECOMPOSITION PATTERN SELECTION
# The decision logic for choosing between patterns.
# ══════════════════════════════════════════════════════════════════

@dataclass
class TaskCharacteristics:
    """Characteristics of a task used to select decomposition pattern."""
    task_description: str
    num_inputs: int             # number of files, documents, etc.
    structure_known_upfront: bool
    all_inputs_same_shape: bool  # all files have same review criteria
    reproducibility_required: bool  # CI/CD needs same pipeline each run
    open_ended: bool             # scope genuinely unknown before starting


def select_decomposition_pattern(task: TaskCharacteristics) -> tuple[str, str]:
    """
    Decide between prompt chaining and adaptive decomposition.

    Returns:
        (pattern_name, rationale)

    This decision function embodies the core Task 1.6 knowledge.
    """
    # Single agent: task is small enough not to need decomposition
    if task.num_inputs <= 1 and not task.open_ended:
        return "single_agent", "Small, well-scoped task — no decomposition needed"

    # Adaptive: open-ended or unknown structure
    if task.open_ended or not task.structure_known_upfront:
        return (
            "adaptive_decomposition",
            "Task scope unknown upfront — must explore before planning. "
            "Phase 1: map. Phase 2: prioritise. Phase 3: execute adaptively.",
        )

    # Prompt chaining: known structure, multiple inputs
    if task.all_inputs_same_shape and task.reproducibility_required:
        return (
            "prompt_chaining_parallel_then_integration",
            f"Known structure, {task.num_inputs} inputs of same shape. "
            "Per-item parallel passes + integration pass. "
            "Reproducible for CI/CD.",
        )

    if task.structure_known_upfront:
        return (
            "prompt_chaining_sequential",
            "Known multi-aspect structure. Sequential focused passes per aspect.",
        )

    return "adaptive_decomposition", "Default to adaptive for uncertain structure"


def demonstrate_pattern_selection():
    """Shows pattern selection for the exam-relevant task types."""
    print("\n" + "=" * 65)
    print("PATTERN SELECTION DECISION FUNCTION")
    print("=" * 65)

    test_cases = [
        TaskCharacteristics(
            task_description="Review PR with 14 files for security, style, correctness",
            num_inputs=14,
            structure_known_upfront=True,
            all_inputs_same_shape=True,
            reproducibility_required=True,
            open_ended=False,
        ),
        TaskCharacteristics(
            task_description="Add comprehensive tests to legacy codebase",
            num_inputs=0,  # unknown upfront
            structure_known_upfront=False,
            all_inputs_same_shape=False,
            reproducibility_required=False,
            open_ended=True,
        ),
        TaskCharacteristics(
            task_description="Check this single file for SQL injection",
            num_inputs=1,
            structure_known_upfront=True,
            all_inputs_same_shape=True,
            reproducibility_required=True,
            open_ended=False,
        ),
        TaskCharacteristics(
            task_description="Debug why payment service is slow",
            num_inputs=0,
            structure_known_upfront=False,
            all_inputs_same_shape=False,
            reproducibility_required=False,
            open_ended=True,
        ),
    ]

    for task in test_cases:
        pattern, rationale = select_decomposition_pattern(task)
        print(f"\nTask: '{task.task_description[:55]}'")
        print(f"  → Pattern: {pattern}")
        print(f"  → Reason: {rationale[:80]}")


# ══════════════════════════════════════════════════════════════════
# SECTION 2: Q12 SCENARIO — MULTI-PASS REVIEW ARCHITECTURE
# Q12 sample question: 14-file PR with inconsistent single-pass results.
# Tests understanding of attention dilution and the per-file solution.
# ══════════════════════════════════════════════════════════════════

def q12_scenario_analysis():
    """
    Analysis of Sample Question 12 from the exam guide.

    Q12: PR modifies 14 files. Single-pass produces:
      - Inconsistent feedback depth across files
      - Bugs missed entirely
      - Identical code flagged in one file, approved in another

    Four options:
      A) Per-file passes + separate cross-file integration pass
      B) Require devs to split PRs into 3-4 file submissions
      C) Switch to larger-context model
      D) Run 3 independent full-PR passes, flag issues in 2+ runs
    """
    print("\n" + "=" * 65)
    print("Q12 SCENARIO: 14-File PR with Inconsistent Single-Pass Results")
    print("=" * 65)

    print("""
ROOT CAUSE DIAGNOSIS:
─────────────────────
"Detailed feedback for some files but superficial for others"
"Obvious bugs missed"
"Identical code: flagged in one file, approved in another"

All three symptoms point to ONE cause: ATTENTION DILUTION
  → 14 files in one context window
  → Model's attention distributed too thin
  → Early files get more attention than later ones
  → Model cannot hold all 14 simultaneously → contradictions

OPTION ANALYSIS:
────────────────

A) Per-file passes + cross-file integration pass  ✅ CORRECT
   Mechanism:
     - Each file gets its own context window → full attention
     - Files 1-14 analysed independently (can run in parallel)
     - Integration pass receives compact summaries, not raw files
     - Cross-file issues found by dedicated pass
   Why it works:
     - Eliminates attention dilution (one file = one full context)
     - Eliminates contradictions (each file isolated, independently assessed)
     - Cross-file pass has dedicated attention for boundaries only
     - Per-file parallel = same speed, dramatically better quality

B) Require devs to split PRs into 3-4 files  ❌ Wrong
   Mechanism: shifts the burden to developers
   Why wrong:
     - Doesn't improve the model's review quality per submission
     - Disrupts development workflow
     - 3-4 files still causes some dilution
     - Addresses symptom (large PR) not cause (attention dilution)

C) Switch to larger context model  ❌ Wrong
   Mechanism: more tokens available
   Why wrong:
     - Attention dilution is NOT a token limit problem
     - Larger window ≠ better attention quality within that window
     - A 200K context model still gives less attention per file
       when 14 files are crammed in vs one file per call
     - More expensive, doesn't fix root cause

D) Three independent passes on full PR, flag consensus issues  ❌ Wrong
   Mechanism: majority vote on multi-run results
   Why wrong:
     - Each of the 3 passes has the same attention dilution problem
     - Real bugs found intermittently get suppressed by requiring consensus
     - A bug caught in 1/3 passes is still a real bug
     - Consensus filtering specifically suppresses rare-but-real issues
     - More expensive (3x the cost) for worse coverage
""")


# ══════════════════════════════════════════════════════════════════
# SECTION 3: CI/CD INTEGRATION
# How prompt chaining works in an automated pipeline context.
# Covers Task 3.6 crossover: -p flag, --output-format json, CLAUDE.md
# ══════════════════════════════════════════════════════════════════

def build_ci_review_command(
    files: list[str],
    output_schema_path: str,
    claude_md_path: str = ".claude/CLAUDE.md",
) -> str:
    """
    Build the Claude Code CLI command for CI/CD execution.

    Key flags:
      -p / --print:         non-interactive mode (prevents CI job hang)
      --output-format json: machine-parseable output for PR comment posting
      --json-schema:        enforce structured output schema

    The CLAUDE.md provides review criteria, testing standards,
    and project-specific context without bloating the CLI command.
    """
    files_arg = " ".join(f'"{f}"' for f in files)

    command = (
        f"claude -p "                              # non-interactive mode (REQUIRED for CI)
        f'--output-format json '                   # machine-parseable for PR comment posting
        f'--json-schema {output_schema_path} '     # enforce review finding schema
        f'"Review these files for security and correctness issues: {files_arg}"'
    )

    return command


def demonstrate_ci_pattern():
    """Shows how prompt chaining integrates with CI/CD."""
    print("\n" + "=" * 65)
    print("CI/CD INTEGRATION PATTERN")
    print("=" * 65)

    print("""
CLAUDE CODE CLI FOR AUTOMATED REVIEW:
──────────────────────────────────────

# Per-file analysis (run in parallel for each file)
claude -p \\
  --output-format json \\
  --json-schema review_finding_schema.json \\
  "Review auth/login.py for security issues" \\
  < auth/login.py

# Key: -p flag (--print) prevents interactive input hang in CI
# Without -p, Claude Code waits for user input → CI job hangs forever

# Collect per-file JSON results, then run integration pass
claude -p \\
  --output-format json \\
  --json-schema integration_schema.json \\
  "Find cross-file integration issues" \\
  < file_summaries.json

# Post structured findings as inline PR comments via GitHub API

CLAUDE.md IN CI CONTEXT:
─────────────────────────
# .claude/CLAUDE.md provides review standards to CI-invoked Claude Code:

## Review Standards
- Flag SQL injection as CRITICAL (never medium or low)
- Flag missing input validation as HIGH
- Skip style issues handled by our linter (black, isort)
- For auth-related code: always check for session fixation

## Available Test Fixtures
- pytest fixtures in tests/conftest.py: create_user(), mock_payment()
- Factory classes in tests/factories.py: UserFactory, OrderFactory

## Review Criteria Priority
When context is limited, prioritise: security > correctness > performance > style

# This context is available to every claude -p invocation in CI
# without being repeated in every command

SESSION ISOLATION FOR INDEPENDENT REVIEWS:
───────────────────────────────────────────
# The same session that GENERATED code should NOT review it.
# Self-review is less effective — model retains its reasoning context.

# Generator session (generates the implementation)
claude "Implement the payment checkout flow"
→ Claude generates checkout.py (retains its reasoning about why it made choices)

# Independent reviewer session (fresh context, no generation bias)
claude -p "Review checkout.py for security and correctness issues" < checkout.py
→ Fresh session with no prior reasoning → more critical, catches subtle issues

# This is why CI review is always a SEPARATE claude invocation
# from the one that generated the code being reviewed
""")


# ══════════════════════════════════════════════════════════════════
# SECTION 4: COMPLETE PIPELINE ORCHESTRATOR
# Ties both patterns together: PR review (chaining) + test planning (adaptive)
# ══════════════════════════════════════════════════════════════════

@dataclass
class CIPipelineResult:
    """Complete output from the CI pipeline."""
    review_findings: list[dict]
    integration_findings: list[dict]
    review_summary: str
    total_critical: int
    total_high: int
    suggested_test_gaps: list[str]
    pipeline_strategy: str


def run_ci_pipeline_demo():
    """
    Demonstrates the complete CI pipeline logic.
    Shows how pattern selection + both decomposition strategies work together.
    """
    print("\n" + "=" * 65)
    print("COMPLETE CI PIPELINE DEMO")
    print("=" * 65)

    # Simulate PR metadata
    pr_files = [
        "auth/login.py",
        "auth/session.py",
        "api/endpoints.py",
        "payment/checkout.py",
    ]

    print(f"\nPR contains {len(pr_files)} files:")
    for f in pr_files:
        print(f"  {f}")

    # Pattern selection
    pr_task = TaskCharacteristics(
        task_description="Review PR for security, correctness, and style",
        num_inputs=len(pr_files),
        structure_known_upfront=True,
        all_inputs_same_shape=True,
        reproducibility_required=True,
        open_ended=False,
    )

    pattern, rationale = select_decomposition_pattern(pr_task)
    print(f"\nPattern selected: {pattern}")
    print(f"Rationale: {rationale}")

    print("\nPipeline execution plan:")
    print("  Step 1: Per-file analysis (parallel)")
    for i, f in enumerate(pr_files):
        print(f"         Pass 1.{i+1}: Analyse {f} in isolation")
    print("  Step 2: Cross-file integration pass (sequential, after step 1)")
    print("  Step 3: Aggregate + format as structured JSON for PR comments")
    print("  Step 4: Post findings as inline PR comments via GitHub API")

    print("\nOutput structure for CI (--output-format json):")
    sample_output = {
        "findings": [
            {
                "file": "auth/login.py",
                "line": 12,
                "severity": "critical",
                "category": "security",
                "description": "SQL injection via string formatting",
                "suggested_fix": "Use parameterised queries: cursor.execute('SELECT ... WHERE id=?', (user_id,))",
                "detected_pattern": "SQL_INJECTION_F_STRING",
            }
        ],
        "integration_findings": [
            {
                "files": ["auth/login.py", "api/endpoints.py"],
                "severity": "high",
                "category": "error_handling",
                "description": "auth.login() returns None on failure, but api/endpoints.py raises HTTP 500",
            }
        ],
        "summary": "4 files reviewed. 2 critical security issues found.",
        "total": 7,
        "critical": 2,
    }
    print(json.dumps(sample_output, indent=2))


# ══════════════════════════════════════════════════════════════════
# SECTION 5: ANTI-PATTERNS FROM THE EXAM
# ══════════════════════════════════════════════════════════════════

def demonstrate_anti_patterns():
    """Shows the specific anti-patterns tested in Task 1.6 questions."""
    print("\n" + "=" * 65)
    print("TASK 1.6 ANTI-PATTERNS")
    print("=" * 65)

    print("""
ANTI-PATTERN 1: Single-pass on many files (Q12 root cause)
─────────────────────────────────────────────────────────────
❌ WRONG:
  claude "Review all 14 files in this PR" < all_14_files.txt

  Result:
    - Superficial analysis of later files
    - Same bug: flagged in file 2, missed in file 11
    - Cross-file issues lost in noise

✅ CORRECT: Per-file passes + integration pass
  for file in pr_files:
      claude -p f"Review {file} for local issues" < {file}
  claude -p "Find cross-file integration issues" < all_summaries.json

ANTI-PATTERN 2: Up-front full plan for open-ended tasks
─────────────────────────────────────────────────────────────
❌ WRONG (for "add tests to legacy codebase"):
  Planned upfront:
    Day 1: auth module
    Day 2: payment module
    Day 3: order module
  
  Problems:
    - Estimates based on zero data
    - Circular dependencies discovered on Day 2 → Day 1 work incomplete
    - auth already has 80% coverage (waste) → payment has 0% (missed priority)

✅ CORRECT: Map first, then prioritise, then execute adaptively
  Phase 1 discovers: payment has 0% coverage, auth has 65% coverage
  Phase 2 prioritises: payment > auth (actual data, not assumptions)
  Phase 3 executes: finds payment → tax_calculator dependency → adds to backlog

ANTI-PATTERN 3: Adaptive decomposition for predictable tasks
─────────────────────────────────────────────────────────────
❌ WRONG (for PR review):
  Phase 1: map the PR files
  Phase 2: decide what to review based on files
  Phase 3: execute review adaptively

  Problems:
    - Unnecessary overhead (we know to check security, style, correctness)
    - No consistency between runs (different plan each PR)
    - Cannot pre-configure quality criteria in CLAUDE.md

✅ CORRECT: Prompt chaining with predefined aspects
  Step 1 (all files): security issues
  Step 2 (all files): correctness issues
  Step 3 (all files): style issues
  Step 4 (summaries): cross-file integration
  
  Same structure every PR → configurable in CI → auditable

ANTI-PATTERN 4: Cross-file concerns in per-file passes
─────────────────────────────────────────────────────────────
❌ WRONG: "While reviewing auth/login.py, also check if other
          files are calling it correctly"
  
  Problems:
    - Per-file pass doesn't have other files in context
    - Model speculates about files it hasn't seen
    - Hallucination risk for non-existent cross-file issues

✅ CORRECT: Strict separation
  Per-file pass: LOCAL issues in this file only
  Integration pass: cross-file boundaries only (from summaries)
""")


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    demonstrate_pattern_selection()
    q12_scenario_analysis()
    demonstrate_ci_pattern()
    run_ci_pipeline_demo()
    demonstrate_anti_patterns()
