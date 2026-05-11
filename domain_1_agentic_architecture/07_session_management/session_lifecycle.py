"""
session_lifecycle.py — Session Lifecycle and State Management
=============================================================
Task 1.7: Manage session state, resumption, and forking

Complete lifecycle:
  Create → (modify/resume/fork) → persist

Advanced patterns:
  - Session state transitions (new → active → paused → resumed → completed)
  - File change detection and notification protocol
  - Session isolation (independent file systems per session)
  - Merge strategies when resuming with conflicting file versions

Run: python session_lifecycle.py
"""

import anthropic
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from datetime import datetime
from enum import Enum

client = anthropic.Anthropic()


# ══════════════════════════════════════════════════════════════════
# SECTION 1: SESSION STATES AND TRANSITIONS
# State machine for session lifecycle
# ══════════════════════════════════════════════════════════════════

class SessionState(str, Enum):
    """Session states in the lifecycle."""
    NEW         = "new"         # Just created, no messages yet
    ACTIVE      = "active"      # Being worked on
    PAUSED      = "paused"      # User stepped away, can be resumed
    RESUMED     = "resumed"     # Was paused, now active again
    COMPLETED   = "completed"   # Converged on conclusion, no further work expected
    FORKED      = "forked"      # A fork was created from this session


@dataclass
class SessionTransition:
    """Record of a state transition."""
    from_state: SessionState
    to_state: SessionState
    reason: str
    timestamp: str


class SessionStateMachine:
    """
    Tracks allowed state transitions and enforces the session lifecycle.
    """
    ALLOWED_TRANSITIONS = {
        SessionState.NEW:       [SessionState.ACTIVE],
        SessionState.ACTIVE:    [SessionState.PAUSED, SessionState.COMPLETED, SessionState.FORKED],
        SessionState.PAUSED:    [SessionState.RESUMED, SessionState.FORKED],
        SessionState.RESUMED:   [SessionState.PAUSED, SessionState.COMPLETED, SessionState.FORKED],
        SessionState.COMPLETED: [SessionState.RESUMED],  # can reopen a completed session
        SessionState.FORKED:    [SessionState.PAUSED, SessionState.COMPLETED],
    }

    def __init__(self, initial_state: SessionState = SessionState.NEW):
        self.current_state = initial_state
        self.transitions: list[SessionTransition] = []

    def can_transition_to(self, target_state: SessionState) -> bool:
        """Check if transition is allowed."""
        return target_state in self.ALLOWED_TRANSITIONS.get(self.current_state, [])

    def transition(self, target_state: SessionState, reason: str) -> bool:
        """Attempt a state transition."""
        if not self.can_transition_to(target_state):
            return False

        transition = SessionTransition(
            from_state=self.current_state,
            to_state=target_state,
            reason=reason,
            timestamp=datetime.now().isoformat(),
        )
        self.transitions.append(transition)
        self.current_state = target_state
        return True

    def history(self) -> list[dict]:
        """Get transition history."""
        return [
            {
                "from": t.from_state.value,
                "to": t.to_state.value,
                "reason": t.reason,
                "timestamp": t.timestamp,
            }
            for t in self.transitions
        ]


def demonstrate_state_machine():
    """Show session state transitions."""
    print("\n" + "=" * 65)
    print("SESSION STATE MACHINE")
    print("=" * 65)

    print("""
ALLOWED TRANSITIONS:
───────────────────
NEW         → ACTIVE (start working)
ACTIVE      → PAUSED (step away)
           → COMPLETED (conclude)
           → FORKED (create branch)
PAUSED      → RESUMED (continue)
           → FORKED (create branch from paused state)
RESUMED     → PAUSED (step away again)
           → COMPLETED
           → FORKED
COMPLETED   → RESUMED (reopen if needed)
FORKED      → PAUSED (if resumed, pause again)
           → COMPLETED (if resumed, complete)

INVALID TRANSITIONS (not allowed):
──────────────────────────────────
ACTIVE      → RESUMED (must PAUSE first to RESUME)
COMPLETED   → ACTIVE (must RESUMED from COMPLETED)
""")

    # Example session lifecycle
    sm = SessionStateMachine()
    print("\n" + "─" * 65)
    print("EXAMPLE SESSION LIFECYCLE")
    print("─" * 65)

    transitions = [
        (SessionState.ACTIVE, "User starts working on analysis"),
        (SessionState.PAUSED, "User steps away after 30 min (save state)"),
        (SessionState.RESUMED, "User returns next day (--resume)"),
        (SessionState.FORKED, "User creates a fork to explore alternative"),
        (SessionState.COMPLETED, "User concludes the primary analysis"),
    ]

    for target_state, reason in transitions:
        success = sm.transition(target_state, reason)
        if success:
            print(f"  ✓ {sm.transitions[-1].from_state.value} → {target_state.value}")
            print(f"    Reason: {reason}")
        else:
            print(f"  ✗ Invalid transition attempted: {sm.current_state.value} → {target_state.value}")

    print("\nFinal state:", sm.current_state.value)


# ══════════════════════════════════════════════════════════════════
# SECTION 2: FILE VERSION MANAGEMENT
# Detecting and notifying about file changes when resuming
# ══════════════════════════════════════════════════════════════════

@dataclass
class FileVersion:
    """Snapshot of a file at a point in time."""
    path: str
    content_hash: str        # SHA256 of file content
    line_count: int
    last_modified: str
    analyzed_by_session: str  # which session analyzed this version


@dataclass
class FileChange:
    """Represents a change to a file between two versions."""
    path: str
    old_version: FileVersion
    new_version: FileVersion
    change_type: str  # added_lines | removed_lines | modified_lines | structural
    affected_lines: list[int]
    change_summary: str
    detected_in_analyzed_sections: bool  # was this file analysed in the session?


def detect_file_changes(
    session_file_versions: dict[str, FileVersion],
    current_file_versions: dict[str, FileVersion],
) -> list[FileChange]:
    """
    Detect which files changed since the session last saw them.

    Returns list of FileChange objects for files that are different.
    """
    changes = []

    for file_path, old_version in session_file_versions.items():
        if file_path not in current_file_versions:
            continue  # file was deleted

        new_version = current_file_versions[file_path]

        if old_version.content_hash != new_version.content_hash:
            # File changed
            change = FileChange(
                path=file_path,
                old_version=old_version,
                new_version=new_version,
                change_type="modified_lines",
                affected_lines=[45, 46, 50, 67],  # example
                change_summary=f"File changed from {old_version.line_count} to {new_version.line_count} lines",
                detected_in_analyzed_sections=True,
            )
            changes.append(change)

    return changes


def build_file_change_notification(
    changes: list[FileChange],
    prioritize_by_analysis: bool = True,
) -> str:
    """
    Build a user-facing notification about file changes.

    Args:
        changes:                    List of FileChange objects
        prioritize_by_analysis:     If True, list files that were analyzed first

    Returns:
        Formatted notification string for the resumed session
    """
    if not changes:
        return ""

    # Sort: analyzed files first (higher priority)
    if prioritize_by_analysis:
        changes = sorted(
            changes,
            key=lambda c: (not c.detected_in_analyzed_sections, c.path)
        )

    notification = "[FILE CHANGES SINCE PRIOR SESSION]:\n\n"

    for i, change in enumerate(changes, 1):
        priority = "⚠️ IMPORTANT" if change.detected_in_analyzed_sections else "ℹ️"
        notification += f"{i}. {priority} {change.path}\n"
        notification += f"   {change.change_summary}\n"
        if change.detected_in_analyzed_sections:
            notification += f"   Status: THIS FILE WAS ANALYZED IN YOUR PRIOR SESSION\n"
        notification += "\n"

    return notification


def demonstrate_file_change_notification():
    """Show how file changes are detected and communicated."""
    print("\n" + "=" * 65)
    print("FILE CHANGE DETECTION AND NOTIFICATION")
    print("=" * 65)

    # Simulated file versions from prior session
    prior_versions = {
        "payment/checkout.py": FileVersion(
            path="payment/checkout.py",
            content_hash="abc123...",
            line_count=145,
            last_modified="2024-11-01",
            analyzed_by_session="payment_analysis",
        ),
        "auth/login.py": FileVersion(
            path="auth/login.py",
            content_hash="def456...",
            line_count=78,
            last_modified="2024-11-01",
            analyzed_by_session="payment_analysis",
        ),
        "utils/helpers.py": FileVersion(
            path="utils/helpers.py",
            content_hash="xyz789...",
            line_count=200,
            last_modified="2024-11-01",
            analyzed_by_session="payment_analysis",
        ),
    }

    # Current file versions (some changed)
    current_versions = {
        "payment/checkout.py": FileVersion(
            path="payment/checkout.py",
            content_hash="abc123_modified...",  # changed
            line_count=162,
            last_modified="2024-11-03",
            analyzed_by_session="payment_analysis",
        ),
        "auth/login.py": FileVersion(
            path="auth/login.py",
            content_hash="def456...",  # unchanged
            line_count=78,
            last_modified="2024-11-01",
            analyzed_by_session="payment_analysis",
        ),
        "utils/helpers.py": FileVersion(
            path="utils/helpers.py",
            content_hash="xyz789_modified...",  # changed
            line_count=215,
            last_modified="2024-11-04",
            analyzed_by_session="payment_analysis",
        ),
    }

    # Detect changes
    changes = detect_file_changes(prior_versions, current_versions)

    # Build notification
    notification = build_file_change_notification(changes)

    print(f"Detected {len(changes)} file change(s):\n")
    print(notification)

    print("Session resume command would be:")
    print('  claude --resume payment_analysis')
    print('  "<user_query_here>')
    print('  "')
    print(notification.strip())
    print('"')


# ══════════════════════════════════════════════════════════════════
# SECTION 3: SESSION ISOLATION
# Each session has its own file view/context
# ══════════════════════════════════════════════════════════════════

class SessionFileContext:
    """
    A session's view of the codebase.
    Isolates file state between sessions.
    """

    def __init__(self, session_name: str):
        self.session_name = session_name
        self.file_snapshots: dict[str, FileVersion] = {}
        self.created_at = datetime.now().isoformat()

    def snapshot_files(self, files: dict[str, str]):
        """Create snapshots of files as the session sees them."""
        import hashlib

        for path, content in files.items():
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            self.file_snapshots[path] = FileVersion(
                path=path,
                content_hash=content_hash,
                line_count=len(content.splitlines()),
                last_modified=datetime.now().isoformat(),
                analyzed_by_session=self.session_name,
            )

    def get_snapshot(self, file_path: str) -> Optional[FileVersion]:
        """Get a file snapshot from this session's context."""
        return self.file_snapshots.get(file_path)


def demonstrate_session_isolation():
    """Show how sessions are isolated from each other."""
    print("\n" + "=" * 65)
    print("SESSION ISOLATION")
    print("=" * 65)

    print("""
WHAT SESSION ISOLATION MEANS:
──────────────────────────────
Session A sees:
  auth/login.py (v1.0, 78 lines, analyzed)
  auth/session.py (exists, not analyzed)
  
Session B (forked from Session A later) sees:
  auth/login.py (v2.0, 85 lines, because code changed)
  auth/session.py (exists, not analyzed)

Session B starts with Session A's MESSAGES (they're forked).
But Session B has its OWN file snapshots (current versions at fork time).

Example:
────────
Session A analysis (Nov 1):
  "auth/login.py uses plain password hashing [code at time of analysis]"

Code changes (Nov 2):
  auth/login.py is refactored to use bcrypt

Session B created (Nov 2, forked from A):
  Message history: inherits Session A's messages (includes analysis of old code)
  File snapshots: Session B's file snapshots (current code, uses bcrypt)
  
  Ambiguity: Prior message says "uses plain hashing" but current file uses bcrypt
  
  Solution: When resuming Session A (not B), notify it about the code change.
            Session B (fork) doesn't have this problem — it starts fresh at fork time.
""")

    # Simulate two session contexts
    original_files = {
        "auth/login.py": "def login(user, pwd):\n    hash = pwd.encode()  # plain\n    ...",
    }

    modified_files = {
        "auth/login.py": (
            "def login(user, pwd):\n"
            "    hash = bcrypt.hashpw(pwd)  # bcrypt\n"
            "    ...\n"
            "    # Enhanced error handling\n"
            "    try:\n"
            "        ...\n"
            "    except bcrypt.InvalidSaltError:\n"
            "        ...\n"
        ),
    }

    session_a = SessionFileContext("payment_analysis_nov1")
    session_a.snapshot_files(original_files)

    session_b = SessionFileContext("payment_analysis_nov2_forked")
    session_b.snapshot_files(modified_files)

    print("\nSession A (original):")
    for path, snapshot in session_a.file_snapshots.items():
        print(f"  {path}: {snapshot.line_count} lines, hash={snapshot.content_hash[:8]}...")

    print("\nSession B (forked, newer code):")
    for path, snapshot in session_b.file_snapshots.items():
        print(f"  {path}: {snapshot.line_count} lines, hash={snapshot.content_hash[:8]}...")

    print("\nKey point: Same session name, different file snapshots at different times")
    print("This is why file change notification is critical for resumed sessions")


# ══════════════════════════════════════════════════════════════════
# SECTION 4: CHOOSING RESUMPTION vs FRESH SESSION
# Complete decision tree
# ══════════════════════════════════════════════════════════════════

def decide_resumption_vs_fresh(
    session_exists: bool,
    code_changes_count: int,
    major_refactor: bool,
    time_since_session_hours: int,
    session_confidence: str,  # high | medium | low
) -> tuple[str, str]:
    """
    Decision function: Resume or start fresh?

    Returns: (strategy, explanation)
    """
    if not session_exists:
        return "new_session", "No prior session to resume"

    if major_refactor:
        return (
            "fresh_with_summary",
            "Major refactor invalidates prior assumptions. Start fresh with baseline summary."
        )

    if code_changes_count > 10:
        return (
            "fresh_with_summary",
            f"Too many ({code_changes_count}) file changes. Start fresh with baseline."
        )

    if session_confidence == "low":
        return (
            "fresh_perspective",
            "Prior session had uncertain conclusions. Start fresh for more reliable analysis."
        )

    if code_changes_count > 0:
        return (
            "resume_with_notification",
            f"Resume and notify about {code_changes_count} file change(s)."
        )

    if time_since_session_hours > 7 * 24:
        return (
            "resume_with_verification",
            "Session is old. Resume and ask model to verify prior conclusions."
        )

    return (
        "resume_directly",
        "Code stable, recent session. Resume and continue."
    )


def demonstrate_decision_tree():
    """Show the decision tree for resumption vs fresh."""
    print("\n" + "=" * 65)
    print("RESUMPTION DECISION TREE")
    print("=" * 65)

    test_cases = [
        {
            "scenario": "Session exists, 1 file changed, recent (6 hours)",
            "inputs": {
                "session_exists": True,
                "code_changes_count": 1,
                "major_refactor": False,
                "time_since_session_hours": 6,
                "session_confidence": "high",
            },
            "expected": ("resume_with_notification", "..."),
        },
        {
            "scenario": "Session exists, major refactor (40 files changed)",
            "inputs": {
                "session_exists": True,
                "code_changes_count": 40,
                "major_refactor": True,
                "time_since_session_hours": 2,
                "session_confidence": "high",
            },
            "expected": ("fresh_with_summary", "..."),
        },
        {
            "scenario": "Session old (2 weeks), no code changes",
            "inputs": {
                "session_exists": True,
                "code_changes_count": 0,
                "major_refactor": False,
                "time_since_session_hours": 14 * 24,
                "session_confidence": "medium",
            },
            "expected": ("resume_with_verification", "..."),
        },
    ]

    for case in test_cases:
        strategy, explanation = decide_resumption_vs_fresh(**case["inputs"])
        print(f"\n{case['scenario']}")
        print(f"  Decision: {strategy}")
        print(f"  Reason: {explanation[:80]}")


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    demonstrate_state_machine()
    demonstrate_file_change_notification()
    demonstrate_session_isolation()
    demonstrate_decision_tree()
