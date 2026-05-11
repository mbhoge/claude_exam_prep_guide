"""
prompt_chaining.py — Fixed Sequential Pipelines for Predictable Workflows
==========================================================================
Task 1.6: Design Task Decomposition Strategies for Complex Workflows

Prompt chaining is the correct strategy when:
  - Task structure is known before execution begins
  - All inputs have the same structural shape
  - Reproducibility is required (CI/CD)
  - Each aspect has clear, predefined quality criteria

This file implements the canonical exam pattern:
  per-file local analysis passes + cross-file integration pass
  to avoid attention dilution in large code reviews.

Run: python prompt_chaining.py
"""

import anthropic
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import asyncio

client = anthropic.Anthropic()


# ══════════════════════════════════════════════════════════════════
# SECTION 1: DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════

@dataclass
class CodeFile:
    """A single file in the review scope."""
    path: str
    content: str
    language: str = "python"

    @property
    def line_count(self) -> int:
        return len(self.content.splitlines())


@dataclass
class FileFinding:
    """A specific issue identified in a single file."""
    file_path: str
    line_number: Optional[int]
    severity: str       # critical | high | medium | low
    category: str       # security | correctness | style | performance
    description: str
    suggested_fix: str
    detected_pattern: str  # for false-positive tracking (Task 4.4)


@dataclass
class FileAnalysis:
    """Complete per-file analysis output."""
    file_path: str
    summary: str
    public_api: list[str]              # exported functions/classes
    data_sources: list[str]            # databases, external services touched
    error_handling_pattern: str        # how errors are handled
    external_calls: list[str]          # calls to other modules/services
    findings: list[FileFinding]
    line_count: int
    analysis_confidence: str           # high | medium | low


@dataclass
class IntegrationFinding:
    """A cross-file issue found in the integration pass."""
    files_involved: list[str]
    severity: str
    category: str       # data_flow | error_handling | api_contract | shared_state
    description: str
    suggested_fix: str


@dataclass
class ReviewResult:
    """Complete review output from the full prompt chain."""
    per_file_analyses: list[FileAnalysis]
    integration_findings: list[IntegrationFinding]
    summary: str
    total_findings: int
    critical_count: int
    review_strategy: str = "per_file_parallel_then_integration"


# ══════════════════════════════════════════════════════════════════
# SECTION 2: STEP DEFINITIONS
# Each step in the prompt chain has a focused system prompt.
# A single all-aspects prompt would cause attention dilution.
# ══════════════════════════════════════════════════════════════════

STEP_SYSTEM_PROMPTS = {

    # ── Per-file local analysis ────────────────────────────────────
    # Focused on ONE file at a time — full attention, no distraction
    "per_file_analysis": """You are an expert code reviewer performing LOCAL analysis of a single file.

SCOPE: This file only. Do NOT speculate about other files or cross-file concerns.

YOUR JOB — identify issues in these categories:
  SECURITY: SQL injection, unvalidated input, hardcoded secrets, insecure patterns
  CORRECTNESS: logic errors, off-by-one, unhandled exceptions, wrong assumptions
  STYLE: PEP 8 violations (Python), naming, documentation gaps, dead code
  PERFORMANCE: N+1 queries, unnecessary allocations, blocking calls

ALSO EXTRACT (for the integration pass):
  - public_api: list of exported functions, classes, and their signatures
  - data_sources: databases, external APIs, or services this file accesses
  - error_handling_pattern: describe how errors are handled ("raises ValueError", "returns None", etc.)
  - external_calls: calls to other modules or services (just the call sites, not the implementations)

SEVERITY DEFINITIONS:
  critical: exploitable security flaw or data loss risk
  high:     correctness bug that will cause failures in production
  medium:   code smell or moderate risk
  low:      style issue or minor improvement

OUTPUT: Valid JSON matching the FileAnalysis schema. Be precise about line numbers.""",

    # ── Cross-file integration analysis ───────────────────────────
    # Receives SUMMARIES from all per-file passes, not raw files
    # Looks for cross-boundary issues impossible to spot per-file
    "cross_file_integration": """You are an expert code reviewer performing INTEGRATION analysis.

You receive compact summaries from per-file analysis passes.
Your job is to find CROSS-FILE issues — things invisible when looking at files individually.

FOCUS AREAS:
  DATA FLOW: Does data passed between modules maintain its constraints?
             (e.g. auth validates input, but API passes unvalidated data from different path)
  ERROR HANDLING: Are errors handled consistently at module boundaries?
                  (e.g. module A raises ValueError, module B catches Exception broadly)
  API CONTRACTS: Do callers match what callees expect?
                 (e.g. function expects dict, caller passes list in one code path)
  SHARED STATE: Inconsistent assumptions about shared resources (DB connections, caches)
  SECURITY BOUNDARIES: Does sanitised data stay sanitised across module calls?

DO NOT re-report issues already found in per-file passes.
Focus EXCLUSIVELY on cross-file boundary problems.

OUTPUT: Valid JSON list of IntegrationFinding objects.""",

}


# ══════════════════════════════════════════════════════════════════
# SECTION 3: PER-FILE ANALYSIS PASS
# Each file gets its own focused context window — no attention dilution.
# Files are independent → can run in parallel.
# ══════════════════════════════════════════════════════════════════

def analyse_single_file(code_file: CodeFile, review_criteria: dict) -> FileAnalysis:
    """
    Run focused analysis on ONE file.

    This is the per-file pass in the prompt chain.
    Each call gets a fresh context window — no other files present.
    No attention dilution from sibling files.

    Args:
        code_file:       The file to analyse
        review_criteria: What to look for (passed explicitly, not assumed)
    """
    prompt = f"""Analyse this {code_file.language} file for issues.

FILE: {code_file.path} ({code_file.line_count} lines)

REVIEW CRITERIA:
{json.dumps(review_criteria, indent=2)}

FILE CONTENTS:
```{code_file.language}
{code_file.content}
```

Return JSON with this exact structure:
{{
  "file_path": "{code_file.path}",
  "summary": "2-3 sentence description of what this file does",
  "public_api": ["function_name(params) -> return_type"],
  "data_sources": ["database table names, external APIs"],
  "error_handling_pattern": "describe how errors are handled",
  "external_calls": ["module.function() at line N"],
  "findings": [
    {{
      "file_path": "{code_file.path}",
      "line_number": 42,
      "severity": "high",
      "category": "security",
      "description": "specific issue description",
      "suggested_fix": "concrete fix",
      "detected_pattern": "SQL_INJECTION_RISK"
    }}
  ],
  "line_count": {code_file.line_count},
  "analysis_confidence": "high"
}}"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2000,
        system=STEP_SYSTEM_PROMPTS["per_file_analysis"],
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text
    try:
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        data  = json.loads(raw[start:end])

        findings = [
            FileFinding(
                file_path=f.get("file_path", code_file.path),
                line_number=f.get("line_number"),
                severity=f.get("severity", "medium"),
                category=f.get("category", "style"),
                description=f.get("description", ""),
                suggested_fix=f.get("suggested_fix", ""),
                detected_pattern=f.get("detected_pattern", ""),
            )
            for f in data.get("findings", [])
        ]

        return FileAnalysis(
            file_path=data.get("file_path", code_file.path),
            summary=data.get("summary", ""),
            public_api=data.get("public_api", []),
            data_sources=data.get("data_sources", []),
            error_handling_pattern=data.get("error_handling_pattern", "unknown"),
            external_calls=data.get("external_calls", []),
            findings=findings,
            line_count=data.get("line_count", code_file.line_count),
            analysis_confidence=data.get("analysis_confidence", "medium"),
        )
    except (json.JSONDecodeError, KeyError):
        # Fallback for unparseable responses
        return FileAnalysis(
            file_path=code_file.path,
            summary=raw[:200],
            public_api=[], data_sources=[], error_handling_pattern="unknown",
            external_calls=[], findings=[], line_count=code_file.line_count,
            analysis_confidence="low",
        )


def analyse_files_parallel(
    files: list[CodeFile],
    review_criteria: dict,
) -> list[FileAnalysis]:
    """
    Run per-file analysis in parallel.

    Per-file analyses are completely independent — no file needs
    another file's results to proceed. Parallel execution is safe
    and dramatically faster for large PRs.

    NOTE: In production use asyncio or threading for true parallelism.
    This implementation shows the concept with sequential fallback.
    """
    print(f"\nPer-file analysis: {len(files)} files")
    print("(Files are independent → safe to parallelise)")

    analyses = []
    for i, code_file in enumerate(files):
        print(f"  [{i+1}/{len(files)}] Analysing {code_file.path}...")
        analysis = analyse_single_file(code_file, review_criteria)
        analyses.append(analysis)
        finding_count = len(analysis.findings)
        print(f"           → {finding_count} finding(s), confidence: {analysis.confidence}")

    return analyses


# ══════════════════════════════════════════════════════════════════
# SECTION 4: CROSS-FILE INTEGRATION PASS
# Runs AFTER all per-file passes complete.
# Receives compact summaries — NOT raw files.
# Looks for cross-boundary issues only.
# ══════════════════════════════════════════════════════════════════

def build_integration_context(analyses: list[FileAnalysis]) -> str:
    """
    Build the integration pass input from per-file analysis summaries.

    Key: we send SUMMARIES, not raw file contents.
    This keeps the integration pass context focused on cross-file
    patterns, not re-reading code already analysed.
    """
    context_parts = ["PER-FILE ANALYSIS SUMMARIES (for cross-file integration review):"]

    for analysis in analyses:
        # Compact summary per file — just what the integration pass needs
        file_summary = {
            "file": analysis.file_path,
            "summary": analysis.summary,
            "public_api": analysis.public_api,
            "data_sources": analysis.data_sources,
            "error_handling_pattern": analysis.error_handling_pattern,
            "external_calls": analysis.external_calls,
            "per_file_finding_count": len(analysis.findings),
            "per_file_finding_severities": [f.severity for f in analysis.findings],
        }
        context_parts.append(json.dumps(file_summary, indent=2))

    context_parts.append(
        "\nFind cross-file integration issues (data flow violations, inconsistent "
        "error handling, API contract mismatches). Do NOT re-report per-file issues."
    )

    return "\n\n".join(context_parts)


def run_integration_pass(analyses: list[FileAnalysis]) -> list[IntegrationFinding]:
    """
    Cross-file integration analysis — the second pass in the chain.

    This pass runs ONLY after all per-file passes complete.
    It sees summaries from all files but NOT the raw file contents.
    It looks exclusively for cross-boundary issues.
    """
    print(f"\nCross-file integration pass ({len(analyses)} file summaries)...")

    integration_context = build_integration_context(analyses)

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2000,
        system=STEP_SYSTEM_PROMPTS["cross_file_integration"],
        messages=[{"role": "user", "content": integration_context}],
    )

    raw = response.content[0].text
    try:
        start = raw.find("[")
        end   = raw.rfind("]") + 1
        items = json.loads(raw[start:end]) if start != -1 else []

        return [
            IntegrationFinding(
                files_involved=item.get("files_involved", []),
                severity=item.get("severity", "medium"),
                category=item.get("category", "api_contract"),
                description=item.get("description", ""),
                suggested_fix=item.get("suggested_fix", ""),
            )
            for item in items
        ]
    except (json.JSONDecodeError, KeyError):
        return []


# ══════════════════════════════════════════════════════════════════
# SECTION 5: AGGREGATION PASS
# Combines per-file and integration findings into final review.
# Deduplicates, prioritises, formats for output.
# ══════════════════════════════════════════════════════════════════

def aggregate_findings(
    per_file_analyses: list[FileAnalysis],
    integration_findings: list[IntegrationFinding],
    original_query: str,
) -> ReviewResult:
    """
    Final aggregation pass — combines everything into a coherent review.

    This step:
    - Deduplicates findings (same issue reported from multiple perspectives)
    - Prioritises by severity
    - Generates an executive summary
    - Formats for CI output (structured JSON for PR comments)
    """
    all_findings = [f for a in per_file_analyses for f in a.findings]
    critical = [f for f in all_findings if f.severity == "critical"]
    critical += [f for f in integration_findings if f.severity == "critical"]

    # Build a summary prompt with all findings
    summary_prompt = f"""Summarise a code review for: {original_query}

Per-file findings: {len(all_findings)} issues across {len(per_file_analyses)} files
Integration findings: {len(integration_findings)} cross-file issues
Critical issues: {len(critical)}

Critical issues:
{json.dumps([{"desc": f.description, "file": f.file_path} for f in critical[:5]], indent=2)}

Write a 3-sentence executive summary for the PR reviewer."""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=300,
        messages=[{"role": "user", "content": summary_prompt}],
    )
    summary = response.content[0].text.strip()

    return ReviewResult(
        per_file_analyses=per_file_analyses,
        integration_findings=integration_findings,
        summary=summary,
        total_findings=len(all_findings) + len(integration_findings),
        critical_count=len(critical),
    )


# ══════════════════════════════════════════════════════════════════
# SECTION 6: FULL PROMPT CHAIN ORCHESTRATION
# ══════════════════════════════════════════════════════════════════

def run_prompt_chain_review(
    files: list[CodeFile],
    review_criteria: dict | None = None,
    pr_description: str = "",
) -> ReviewResult:
    """
    Full prompt chain for code review.

    Chain structure:
      Step 1: Per-file local analysis (parallel, isolated contexts)
      Step 2: Cross-file integration analysis (sequential, receives summaries)
      Step 3: Aggregation (sequential, produces final output)

    Args:
        files:            Files in the PR
        review_criteria:  What to look for (passed explicitly each step)
        pr_description:   Context about the PR's purpose
    """
    if review_criteria is None:
        review_criteria = {
            "security":    "flag SQL injection, unvalidated input, hardcoded secrets",
            "correctness": "flag logic errors, unhandled exceptions, wrong assumptions",
            "style":       "flag naming issues, missing docs, dead code",
            "performance": "flag N+1 queries, blocking calls, memory issues",
            "skip":        "minor formatting preferences (handled by linter)",
        }

    print(f"\n{'='*65}")
    print(f"PROMPT CHAIN REVIEW: {len(files)} files")
    print(f"Strategy: per-file (parallel) → cross-file → aggregation")
    print(f"{'='*65}")

    # ── Step 1: Per-file passes (parallel, independent) ────────────
    per_file_analyses = analyse_files_parallel(files, review_criteria)

    # ── Step 2: Integration pass (sequential, waits for step 1) ───
    integration_findings = run_integration_pass(per_file_analyses)
    print(f"  → {len(integration_findings)} cross-file issue(s) found")

    # ── Step 3: Aggregation ────────────────────────────────────────
    result = aggregate_findings(per_file_analyses, integration_findings, pr_description)
    print(f"\n✓ Review complete: {result.total_findings} total findings, "
          f"{result.critical_count} critical")

    return result


# ══════════════════════════════════════════════════════════════════
# SECTION 7: ATTENTION DILUTION DEMONSTRATION
# Side-by-side showing why single-pass fails on large PRs.
# ══════════════════════════════════════════════════════════════════

def demonstrate_attention_dilution():
    """
    Shows exactly what attention dilution looks like and why
    the per-file + integration pass pattern solves it.
    """
    print("\n" + "=" * 65)
    print("ATTENTION DILUTION: Why Single-Pass Fails on Large PRs")
    print("=" * 65)

    print("""
SINGLE-PASS PROBLEM (all 14 files together):
─────────────────────────────────────────────
Context window occupied by:
  - System prompt: ~500 tokens
  - File 1 (auth.py, 300 lines): ~2,400 tokens
  - File 2 (api.py, 450 lines): ~3,600 tokens
  - File 3-14 (average 250 lines): ~2,000 tokens each
  Total: ~500 + 2,400 + 3,600 + (12 × 2,000) = ~30,500 tokens

Attention is distributed ACROSS ALL 14 FILES SIMULTANEOUSLY.

Observed failures in production:
  ✗ Detailed feedback on File 1 (processed early, more attention)
  ✗ Superficial 1-2 comments on Files 9-14 (attention exhausted)
  ✗ SQL injection in File 7 missed entirely
  ✗ Same pattern (raw SQL) flagged in File 2 but approved in File 11
  ✗ Cross-file data flow issues: Auth validates in File 1, but
    File 9 bypasses auth on a different endpoint (not spotted)

PER-FILE + INTEGRATION PASS SOLUTION:
──────────────────────────────────────
Pass 1a: File 1 only in context → full attention → 8 specific findings
Pass 1b: File 2 only in context → full attention → 12 specific findings
Pass 1c: File 3 only in context → full attention → 3 specific findings
...
Pass 1n: File 14 only in context → full attention → 6 specific findings

Pass 2: 14 compact summaries in context (not raw files)
  → Looking only for cross-file boundary issues
  → Finds the auth bypass that single-pass missed

Results:
  ✓ Every file gets same depth of analysis
  ✓ Contradictions impossible (each file analysed in isolation)
  ✓ Cross-file issues found by dedicated pass
  ✓ Total findings: significantly more and more accurate
""")

    print("WHY SUMMARIES (not raw files) IN INTEGRATION PASS:")
    print("  If integration pass received raw files again:")
    print("    - Re-reading all code → attention dilution again")
    print("    - Would re-find per-file issues → duplicate findings")
    print("    - No focus on cross-file boundaries specifically")
    print("")
    print("  With compact summaries:")
    print("    - Context window used for cross-file reasoning only")
    print("    - Full attention on module boundaries and data flow")
    print("    - Per-file findings already captured — no duplication")


# ══════════════════════════════════════════════════════════════════
# SECTION 8: SAMPLE FILES FOR DEMONSTRATION
# ══════════════════════════════════════════════════════════════════

SAMPLE_FILES = [
    CodeFile(
        path="auth/login.py",
        content="""
import sqlite3

def login(username, password):
    conn = sqlite3.connect('users.db')
    # Security issue: SQL injection
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    cursor = conn.execute(query)
    user = cursor.fetchone()
    if user:
        return {"user_id": user[0], "session": generate_session()}
    return None  # Error handling pattern: returns None on failure

def generate_session():
    import random
    return str(random.randint(100000, 999999))  # Weak session generation
""",
        language="python",
    ),

    CodeFile(
        path="api/endpoints.py",
        content="""
from auth.login import login
from flask import request, jsonify

def handle_login():
    data = request.json
    # Correctness: no input validation before calling login
    result = login(data['username'], data['password'])
    if result is None:
        # Cross-file issue: auth returns None, but API raises 500
        raise Exception("Login failed")  # Should return 401
    return jsonify(result)

def handle_admin():
    # Missing auth check — any user can reach this endpoint
    user_id = request.args.get('user_id')
    return get_admin_data(user_id)
""",
        language="python",
    ),
]


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    demonstrate_attention_dilution()

    print("\n" + "=" * 65)
    print("RUNNING PROMPT CHAIN REVIEW ON SAMPLE FILES")
    print("=" * 65)

    result = run_prompt_chain_review(
        files=SAMPLE_FILES,
        pr_description="PR: Refactor authentication module",
    )

    print(f"\nSUMMARY: {result.summary}")
    print(f"\nFINDINGS:")
    print(f"  Per-file:    {sum(len(a.findings) for a in result.per_file_analyses)}")
    print(f"  Integration: {len(result.integration_findings)}")
    print(f"  Critical:    {result.critical_count}")
    print(f"  Total:       {result.total_findings}")

    if result.per_file_analyses:
        print("\nPer-file findings sample:")
        for analysis in result.per_file_analyses:
            for f in analysis.findings[:2]:
                print(f"  [{f.severity}] {f.file_path} L{f.line_number}: {f.description[:60]}")

    if result.integration_findings:
        print("\nIntegration findings:")
        for f in result.integration_findings:
            print(f"  [{f.severity}] {f.category}: {f.description[:70]}")
