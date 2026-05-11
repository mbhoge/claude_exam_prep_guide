"""
session_resumption.py — Named Sessions and Resumption Strategies
================================================================
Task 1.7: Manage session state, resumption, and forking

Core operations:
  - --resume <session_name>: reload prior conversation
  - Session save/load mechanisms
  - Deciding when to resume vs start fresh
  - Handling stale tool results in resumed sessions

Run: python session_resumption.py
"""

import anthropic
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta

client = anthropic.Anthropic()


# ══════════════════════════════════════════════════════════════════
# SECTION 1: SESSION STORAGE AND LOADING
# Naive file-based storage for demo (production: database)
# ══════════════════════════════════════════════════════════════════

SESSIONS_DIR = Path("/tmp/claude_sessions")


@dataclass
class SessionMetadata:
    """
    Metadata about a persisted session.
    Helps decide whether to resume or start fresh.
    """
    name: str
    created_at: str
    last_modified: str
    message_count: int
    code_files_analyzed: list[str]  # which files were analysed in this session
    tool_results_count: int
    primary_conclusion: str         # high-level outcome of the session
    staleness_risk: str            # high | medium | low


@dataclass
class SessionState:
    """
    Complete session state for resumption.
    """
    metadata: SessionMetadata
    messages: list[dict]           # conversation history
    tool_results_cache: dict       # {tool_call_id: result}


def save_session(name: str, messages: list[dict], conclusion: str,
                 code_files: list[str]):
    """Save a named session to disk."""
    SESSIONS_DIR.mkdir(exist_ok=True)

    tool_result_count = sum(
        1 for m in messages 
        if m.get("role") == "user" and any(
            isinstance(c, dict) and c.get("type") == "tool_result"
            for c in (m.get("content") if isinstance(m.get("content"), list) else [])
        )
    )

    metadata = SessionMetadata(
        name=name,
        created_at=datetime.now().isoformat(),
        last_modified=datetime.now().isoformat(),
        message_count=len(messages),
        code_files_analyzed=code_files,
        tool_results_count=tool_result_count,
        primary_conclusion=conclusion,
        staleness_risk="medium",  # default estimate
    )

    session = SessionState(
        metadata=metadata,
        messages=messages,
        tool_results_cache={},
    )

    path = SESSIONS_DIR / f"{name}.json"
    with open(path, "w") as f:
        json.dump({
            "metadata": {
                "name": metadata.name,
                "created_at": metadata.created_at,
                "last_modified": metadata.last_modified,
                "message_count": metadata.message_count,
                "code_files_analyzed": metadata.code_files_analyzed,
                "tool_results_count": metadata.tool_results_count,
                "primary_conclusion": metadata.primary_conclusion,
                "staleness_risk": metadata.staleness_risk,
            },
            "messages": messages,
        }, f, indent=2)

    print(f"✓ Session '{name}' saved to {path}")
    return path


def load_session(name: str) -> Optional[SessionState]:
    """Load a named session from disk."""
    path = SESSIONS_DIR / f"{name}.json"
    if not path.exists():
        return None

    with open(path) as f:
        data = json.load(f)

    metadata = SessionMetadata(**data["metadata"])
    return SessionState(
        metadata=metadata,
        messages=data["messages"],
        tool_results_cache={},
    )


def list_sessions() -> list[SessionMetadata]:
    """List all available sessions with metadata."""
    if not SESSIONS_DIR.exists():
        return []

    sessions = []
    for path in SESSIONS_DIR.glob("*.json"):
        with open(path) as f:
            data = json.load(f)
            sessions.append(SessionMetadata(**data["metadata"]))
    return sessions


# ══════════════════════════════════════════════════════════════════
# SECTION 2: STALENESS DETECTION
# Evaluate whether a resumed session needs fresh data
# ══════════════════════════════════════════════════════════════════

@dataclass
class StalenessFactor:
    """Factors that indicate whether a resumed session is stale."""
    factor: str
    is_stale: bool
    severity: str  # critical | high | medium | low
    recommendation: str


def assess_session_staleness(
    session: SessionState,
    code_file_modifications: dict[str, str],  # {file_path: summary of change}
    time_since_last_use_hours: int,
) -> list[StalenessFactor]:
    """
    Assess whether a resumed session has stale data.

    Returns list of factors that indicate staleness.
    Agent uses this to decide whether to trust prior conclusions
    or re-investigate with fresh data.
    """
    factors = []

    # ── Time-based staleness ───────────────────────────────────────
    if time_since_last_use_hours > 7 * 24:  # > 1 week
        factors.append(StalenessFactor(
            factor="Age of session",
            is_stale=True,
            severity="medium",
            recommendation="Re-verify conclusions with current code state",
        ))

    # ── Tool result staleness ──────────────────────────────────────
    if session.metadata.tool_results_count > 5:
        factors.append(StalenessFactor(
            factor="High number of tool results cached",
            is_stale=True,
            severity="high",
            recommendation="Re-run tools for fresh data (especially web searches)",
        ))

    # ── Code file modification staleness ───────────────────────────
    analyzed_files = session.metadata.code_files_analyzed
    modified_files = {f for f in code_file_modifications}
    overlap = analyzed_files and modified_files.intersection(analyzed_files)

    if overlap:
        factors.append(StalenessFactor(
            factor=f"Code changes in analyzed files: {', '.join(list(overlap)[:3])}",
            is_stale=True,
            severity="high",
            recommendation=f"Inform agent about {len(overlap)} modified file(s)",
        ))

    # ── Session conclusion confidence ──────────────────────────────
    if "needs further investigation" in session.metadata.primary_conclusion.lower():
        factors.append(StalenessFactor(
            factor="Prior session had low-confidence conclusion",
            is_stale=True,
            severity="medium",
            recommendation="Re-investigate with fresh perspective",
        ))

    return factors


def demonstrate_staleness_scenarios():
    """Show different staleness scenarios."""
    print("\n" + "=" * 65)
    print("STALENESS SCENARIOS: When to Resume vs Start Fresh")
    print("=" * 65)

    scenarios = [
        {
            "scenario": "Analysis of payment module (0 days old, no code changes)",
            "factors": [
                StalenessFactor("Time", False, "low", ""),
                StalenessFactor("Code changes", False, "low", ""),
            ],
            "decision": "RESUME ✓",
            "approach": "--resume payment_analysis 'Extend analysis to error handling'",
        },
        {
            "scenario": "Web research (1 week old, market changes)",
            "factors": [
                StalenessFactor("Time", True, "medium", ""),
                StalenessFactor("Tool results stale", True, "high", ""),
            ],
            "decision": "START FRESH",
            "approach": "New session with injected summary of prior findings",
        },
        {
            "scenario": "Architecture analysis (3 days, specific files changed)",
            "factors": [
                StalenessFactor("Code changes in 2 files", True, "high", ""),
            ],
            "decision": "RESUME + INFORM CHANGES",
            "approach": "--resume + notify: 'auth.py lines 45-50 changed from X to Y'",
        },
    ]

    for scenario in scenarios:
        print(f"\n{scenario['scenario']}")
        print(f"  Decision: {scenario['decision']}")
        print(f"  Approach: {scenario['approach']}")
        print(f"  Factors:")
        for f in scenario["factors"]:
            status = "⚠️ STALE" if f.is_stale else "✓ OK"
            print(f"    {status}: {f.factor}")


# ══════════════════════════════════════════════════════════════════
# SECTION 3: RESUMPTION FLOW
# How to properly resume a session with optional file change info
# ══════════════════════════════════════════════════════════════════

def build_resumed_context(
    session: SessionState,
    new_query: str,
    code_changes: dict[str, str] | None = None,
) -> tuple[list[dict], str]:
    """
    Prepare context for a resumed session.

    Builds the messages array that will be used in the API call.
    If code has changed, informs the agent about specific changes.

    Args:
        session:      Loaded SessionState
        new_query:    New user question/request
        code_changes: {file_path: change_description}

    Returns:
        (messages_for_api, context_note)
    """
    # Start with prior conversation history
    messages = session.messages.copy()

    # Build the new user message with change notifications
    change_notification = ""
    if code_changes:
        change_notification = "\n\n[CODE CHANGES SINCE PRIOR SESSION]:\n"
        for file_path, change_desc in code_changes.items():
            change_notification += f"  - {file_path}: {change_desc}\n"

    new_user_message = {
        "role": "user",
        "content": f"{new_query}{change_notification}",
    }

    messages.append(new_user_message)

    context_note = (
        f"Resuming session '{session.metadata.name}' "
        f"({session.metadata.message_count} prior messages)"
    )
    if code_changes:
        context_note += f". Informing about {len(code_changes)} file change(s)"

    return messages, context_note


def run_resumed_session(
    session_name: str,
    new_query: str,
    code_changes: dict[str, str] | None = None,
) -> Optional[str]:
    """
    Resume a named session and continue the conversation.

    Args:
        session_name:  Name of the session to resume
        new_query:     New question for the agent
        code_changes:  Dict of {file_path: change_description} if code changed
    """
    print(f"\n{'='*65}")
    print(f"RESUMING SESSION: {session_name}")
    print(f"{'='*65}")

    session = load_session(session_name)
    if not session:
        print(f"✗ Session '{session_name}' not found")
        return None

    print(f"✓ Loaded session (created {session.metadata.created_at})")
    print(f"  Prior messages: {session.metadata.message_count}")
    print(f"  Conclusion: {session.metadata.primary_conclusion[:80]}")

    if code_changes:
        print(f"  Notifying about {len(code_changes)} file change(s)")

    messages, context_note = build_resumed_context(session, new_query, code_changes)

    print(f"\nContext: {context_note}")
    print(f"Message array length: {len(messages)}")

    # In production: call API with these messages
    # response = client.messages.create(
    #     model="claude-opus-4-6",
    #     max_tokens=2000,
    #     messages=messages,
    # )
    # return response.content[0].text

    # For demo:
    return f"[API CALL] Resumed session with {len(messages)} messages"


# ══════════════════════════════════════════════════════════════════
# SECTION 4: RESUME vs FRESH DECISION FUNCTION
# The logic for choosing between resumption and starting fresh
# ══════════════════════════════════════════════════════════════════

def decide_resumption_strategy(
    prior_session: Optional[SessionState],
    code_changes: dict[str, str],
    major_refactor: bool,
    time_hours: int,
) -> tuple[str, str]:
    """
    Decide between resuming a session vs starting fresh.

    Args:
        prior_session:  Loaded session or None
        code_changes:   {file_path: change_description}
        major_refactor: Whether major architectural changes occurred
        time_hours:     Hours since prior session

    Returns:
        (strategy, rationale)
    """
    if not prior_session:
        return "new_session", "No prior session to resume"

    if major_refactor:
        return (
            "fresh_with_injected_summary",
            "Major refactor breaks prior assumptions. "
            "Start fresh but inject summary of prior findings for context."
        )

    # Check for stale code
    analyzed_files = set(prior_session.metadata.code_files_analyzed)
    changed_files = set(code_changes.keys())
    significant_changes = analyzed_files.intersection(changed_files)

    if significant_changes and len(significant_changes) > 5:
        return (
            "fresh_with_injected_summary",
            f"Too many ({len(significant_changes)}) analyzed files changed. "
            "Start fresh but inject baseline."
        )

    if significant_changes:
        return (
            "resume_with_change_notification",
            f"{len(significant_changes)} analyzed file(s) changed. "
            "Resume and notify agent about specific changes."
        )

    if time_hours > 7 * 24:
        return (
            "resume_with_freshness_check",
            "Week+ since prior session. Resume but ask agent to re-verify conclusions."
        )

    return (
        "resume_directly",
        "Code stable, recent session. Resume and continue."
    )


# ══════════════════════════════════════════════════════════════════
# SECTION 5: DEMO: FULL RESUMPTION WORKFLOW
# ══════════════════════════════════════════════════════════════════

def demo_resumption_workflow():
    """
    Demonstrates the full resumption workflow with decision logic.
    """
    print("\n" + "=" * 65)
    print("FULL RESUMPTION WORKFLOW DEMO")
    print("=" * 65)

    # Step 1: Create an initial session
    print("\n--- STEP 1: Initial Session ---")
    initial_messages = [
        {
            "role": "user",
            "content": "Analyse the payment module architecture",
        },
        {
            "role": "assistant",
            "content": (
                "The payment module has three main components: "
                "checkout flow, gateway integration, and error handling. "
                "[Detailed analysis...]"
            ),
        },
    ]

    save_session(
        name="payment_analysis",
        messages=initial_messages,
        conclusion="Payment module requires enhanced error handling",
        code_files=["payment/checkout.py", "payment/gateway.py"],
    )

    # Step 2: Time passes, developer modifies code
    print("\n--- STEP 2: Time Passes, Code Changes ---")
    time.sleep(0.1)  # Simulate time passing

    code_modifications = {
        "payment/checkout.py": "Refactored lines 50-120: error handling → try/except wrapper",
    }

    # Step 3: Make resumption decision
    print("\n--- STEP 3: Resumption Decision ---")
    session = load_session("payment_analysis")

    strategy, rationale = decide_resumption_strategy(
        prior_session=session,
        code_changes=code_modifications,
        major_refactor=False,
        time_hours=24,
    )

    print(f"Strategy: {strategy}")
    print(f"Rationale: {rationale}")

    # Step 4: Execute the strategy
    print("\n--- STEP 4: Execute Resumption ---")
    if strategy == "resume_with_change_notification":
        result = run_resumed_session(
            session_name="payment_analysis",
            new_query="You previously analysed the payment module. "
                      "Given the code changes, do your conclusions still hold?",
            code_changes=code_modifications,
        )
        if result:
            print(f"Result: {result}")


# ══════════════════════════════════════════════════════════════════
# SECTION 6: ANTI-PATTERN DEMONSTRATIONS
# ══════════════════════════════════════════════════════════════════

def demonstrate_anti_patterns():
    """Shows resumption anti-patterns and correct alternatives."""
    print("\n" + "=" * 65)
    print("RESUMPTION ANTI-PATTERNS")
    print("=" * 65)

    print("""
ANTI-PATTERN 1: Resume with stale tool results
───────────────────────────────────────────────
Prior session:
  tool: web_search("Python web frameworks 2024")
  result: Django, Flask, FastAPI (outdated rankings)
  
Resumed session 6 months later:
  Agent trusts prior tool result
  Gives outdated advice based on old rankings
  
✗ WRONG: Let agent use old tool results
✓ RIGHT: Ask agent to re-run searches
         "Re-search for current Python web framework trends"

ANTI-PATTERN 2: Resume after major refactor without new context
────────────────────────────────────────────────────────────────
Prior session: Monolithic architecture analysis
Code state:    Refactored to microservices
Resumption:    Agent tries to apply monolithic concepts to new structure
               
✗ WRONG: Resume directly with "Continue the analysis"
✓ RIGHT: Fresh session with injected summary
         "System was monolithic (prior analysis). Now: microservices.
          Which prior issues remain? Which are resolved? New issues?"

ANTI-PATTERN 3: Not informing agent about code changes
─────────────────────────────────────────────────────
Prior session: Security analysis of auth/login.py
Code change:   Lines 45-67 changed from plain password to hashed
Resumption:    Agent doesn't know about this change
               Repeats prior security findings (now false positives)

✗ WRONG: Resume without mentioning file changes
✓ RIGHT: Resume + notify
         "Since prior analysis, auth/login.py lines 45-67 changed.
          [show the change]. How does this affect your prior findings?"

ANTI-PATTERN 4: Hardcoding old tool results in fresh session
──────────────────────────────────────────────────────────
Fresh session:
  "Based on prior web search, the market trends are X, Y, Z.
   [hardcoded old search results]
   Given these trends, analyse the product strategy."
  
Problem: If trends changed, agent may contradict hardcoded data
         with current reasoning (inconsistent)

✓ RIGHT: Inject as summary, not as data
         "Prior research found these trends: [summary, not results].
          Re-search for current data and compare."
""")


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════

import time

if __name__ == "__main__":
    demonstrate_staleness_scenarios()
    demonstrate_anti_patterns()
    demo_resumption_workflow()

    print("\n" + "=" * 65)
    print("AVAILABLE SESSIONS")
    print("=" * 65)
    sessions = list_sessions()
    for s in sessions:
        print(f"  {s.name}: {s.created_at[:10]}, {s.message_count} messages")
