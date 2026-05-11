"""
Task 2.2 – Structured Error Responses for MCP Tools
====================================================
Directly tested in Sample Question 8 (web search subagent timeout).

Key concept: generic errors hide context from the coordinator.
Structured errors enable intelligent recovery decisions.

Anti-patterns:
  - "Operation failed" (coordinator can't decide: retry? skip? escalate?)
  - Returning empty success on failure (coordinator thinks task succeeded)
  - Terminating entire workflow on a single failure
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ErrorCategory(str, Enum):
    TRANSIENT   = "transient"    # timeout, service unavailable → may retry
    VALIDATION  = "validation"   # bad input → fix before retrying
    PERMISSION  = "permission"   # auth failure → don't retry without auth fix
    BUSINESS    = "business"     # policy violation → don't retry


@dataclass
class MCPToolError:
    """
    Structured error that enables intelligent coordinator recovery.
    Always set isError=True in the tool_result when returning this.
    """
    error_category: ErrorCategory
    is_retryable: bool
    message: str
    attempted_query: str = ""
    partial_results: list = None
    alternative_approaches: list = None

    def to_dict(self) -> dict:
        return {
            "isError": True,
            "errorCategory": self.error_category.value,
            "isRetryable": self.is_retryable,
            "message": self.message,
            "attempted_query": self.attempted_query,
            "partial_results": self.partial_results or [],
            "alternative_approaches": self.alternative_approaches or [],
        }

    def to_json_string(self) -> str:
        import json
        return json.dumps(self.to_dict(), indent=2)


# ─────────────────────────────────────────────────────────
# MCP tool implementations with proper error responses
# ─────────────────────────────────────────────────────────

def web_search_tool(query: str, timeout_seconds: int = 10) -> dict:
    """
    MCP tool with structured error responses.
    Demonstrates all four error categories.
    """
    import time
    import random

    # Simulate different failure modes
    failure_mode = random.choice(["success", "timeout", "auth", "policy", "empty"])

    if failure_mode == "success":
        return {
            "isError": False,
            "results": [
                {"title": "Result 1", "url": "https://example.com/1", "snippet": "..."},
                {"title": "Result 2", "url": "https://example.com/2", "snippet": "..."},
            ],
        }

    elif failure_mode == "timeout":
        # Transient – safe to retry
        return MCPToolError(
            error_category=ErrorCategory.TRANSIENT,
            is_retryable=True,
            message=f"Search timed out after {timeout_seconds}s. Service may be temporarily slow.",
            attempted_query=query,
            partial_results=[],  # Nothing retrieved before timeout
            alternative_approaches=[
                "Retry with same query",
                f"Try narrower query: '{query.split()[0]}'",
                "Wait 30s before retry (service may be overloaded)",
            ],
        ).to_dict()

    elif failure_mode == "auth":
        # Permission error – retrying without fixing auth is pointless
        return MCPToolError(
            error_category=ErrorCategory.PERMISSION,
            is_retryable=False,
            message="Search API authentication failed. API key may be expired or invalid.",
            attempted_query=query,
            alternative_approaches=[
                "Check API key configuration",
                "Use document_analyst subagent with pre-loaded documents instead",
            ],
        ).to_dict()

    elif failure_mode == "policy":
        # Business rule violation
        return MCPToolError(
            error_category=ErrorCategory.BUSINESS,
            is_retryable=False,
            message="Query contains restricted terms. Policy prohibits searching for this content.",
            attempted_query=query,
            alternative_approaches=[
                "Rephrase query to avoid restricted terms",
                "Use internal knowledge base instead",
            ],
        ).to_dict()

    elif failure_mode == "empty":
        # ✅ This is NOT an error – it's a valid empty result
        # Distinguish from access failures!
        return {
            "isError": False,
            "results": [],
            "note": "Search succeeded but found no matching results for this query.",
        }


# ─────────────────────────────────────────────────────────
# Coordinator recovery based on structured error
# ─────────────────────────────────────────────────────────

def coordinator_handle_search_result(result: dict, original_query: str) -> str:
    """
    Shows how coordinator makes intelligent recovery decisions
    based on structured error context (vs generic "Operation failed").
    """
    if not result.get("isError"):
        if not result.get("results"):
            # Valid empty result – note gap but don't fail
            return f"Search returned no results for '{original_query}'. Noting as coverage gap."
        return f"Search succeeded with {len(result['results'])} results."

    category = result.get("errorCategory")
    is_retryable = result.get("isRetryable", False)
    alternatives = result.get("alternative_approaches", [])

    if category == ErrorCategory.TRANSIENT and is_retryable:
        return f"Transient failure – will retry. Alternatives: {alternatives}"

    elif category == ErrorCategory.PERMISSION:
        # Don't retry – fix auth or use alternative approach
        alt = alternatives[0] if alternatives else "use alternative source"
        return f"Auth failure (non-retryable). Action: {alt}"

    elif category == ErrorCategory.BUSINESS:
        return f"Policy violation. Cannot retry. Alternatives: {alternatives}"

    else:
        # Unknown category – propagate with full context
        return f"Unclassified error. Partial results: {result.get('partial_results', [])}. Continuing with available data."


# ─────────────────────────────────────────────────────────
# Anti-patterns
# ─────────────────────────────────────────────────────────

def antipattern_generic_error():
    """❌ WRONG: generic error hides recovery options from coordinator."""
    return {"error": "Operation failed"}
    # Coordinator cannot determine:
    #   - Was this transient or permanent?
    #   - Should it retry?
    #   - Was there partial data?
    #   - What was attempted?


def antipattern_silent_suppression():
    """❌ WRONG: returning empty success masks the failure."""
    # Simulated timeout – but we return as if it succeeded
    try:
        raise TimeoutError("Search timed out")
    except TimeoutError:
        return {"isError": False, "results": []}
    # Coordinator thinks search succeeded with no results
    # vs correctly knowing it failed and should retry


def antipattern_terminate_on_single_failure(results: list) -> bool:
    """❌ WRONG: aborting entire pipeline when one subagent fails."""
    for result in results:
        if result.get("isError"):
            raise SystemExit("Subagent failed – aborting entire research pipeline")
    # Better: proceed with partial results, note gaps in output


# ─────────────────────────────────────────────────────────
# Q8 pattern: timeout → structured error → coordinator recovers
# ─────────────────────────────────────────────────────────

def q8_timeout_recovery_pattern():
    """
    Implements the correct answer to Sample Question 8:
    "Web search subagent times out. Which error propagation approach
    best enables intelligent recovery?"

    Answer A: Return structured error context including failure type,
    attempted query, partial results, and potential alternatives.
    """
    # Subagent encounters timeout
    timeout_error = MCPToolError(
        error_category=ErrorCategory.TRANSIENT,
        is_retryable=True,
        message="Web search timed out after 30s",
        attempted_query="AI impact on music production 2024",
        partial_results=[
            # Some results retrieved before timeout
            {"title": "Partial result", "url": "https://example.com"}
        ],
        alternative_approaches=[
            "Retry with 60s timeout",
            "Narrow query: 'AI music tools'",
            "Use document_analyst with cached papers instead",
        ],
    )

    # Coordinator receives structured context and makes intelligent decision
    recovery_action = coordinator_handle_search_result(
        timeout_error.to_dict(),
        "AI impact on music production 2024",
    )
    print(f"Q8 recovery decision: {recovery_action}")
    return recovery_action


if __name__ == "__main__":
    q8_timeout_recovery_pattern()
