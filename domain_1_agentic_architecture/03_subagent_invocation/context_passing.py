"""
context_passing.py — Structured Context Passing and Attribution Preservation
=============================================================================
Task 1.3 Skill: Passing complete findings between agents with attribution intact.

Two problems this file solves:
  1. HOW to package prior agent findings for the next subagent's instruction
  2. WHY structured formats (not plain text) preserve provenance through synthesis

Run: python context_passing.py
"""

import anthropic
import json
from dataclasses import dataclass, field
from typing import Optional
from datetime import date

client = anthropic.Anthropic()


# ══════════════════════════════════════════════════════════════════
# SECTION 1: THE STRUCTURED FINDING FORMAT
# The canonical data structure that every subagent uses for output.
# Keeps claim separate from its evidence and provenance metadata.
# ══════════════════════════════════════════════════════════════════

@dataclass
class SourceMetadata:
    """
    Provenance data attached to every finding.
    Must survive through synthesis without being compressed away.
    """
    source_url:       Optional[str]   # Web URL or None for local docs
    document_name:    str             # Human-readable source name
    page_number:      Optional[int]   # Exact page (for documents)
    section:          Optional[str]   # Section heading (optional)
    publication_date: Optional[str]   # YYYY-MM-DD
    source_type:      str             # news | industry_report | academic | government
    confidence:       str             # measured | estimated | anecdotal | author_opinion


@dataclass
class StructuredFinding:
    """
    A single piece of evidence with full provenance.
    This is the atom of information passed between agents.
    """
    claim:            str             # Specific, falsifiable statement
    evidence_excerpt: str             # Brief quote or paraphrase from source
    metadata:         SourceMetadata

    def to_dict(self) -> dict:
        return {
            "claim":            self.claim,
            "evidence_excerpt": self.evidence_excerpt,
            "metadata": {
                "source_url":       self.metadata.source_url,
                "document_name":    self.metadata.document_name,
                "page_number":      self.metadata.page_number,
                "section":          self.metadata.section,
                "publication_date": self.metadata.publication_date,
                "source_type":      self.metadata.source_type,
                "confidence":       self.metadata.confidence,
            },
        }


@dataclass
class AgentFindings:
    """
    Complete output from one subagent invocation.
    Passed to coordinator, then (selectively) to later subagents.
    """
    agent_role:          str
    findings:            list[StructuredFinding]
    coverage_gaps:       list[str]     = field(default_factory=list)
    search_date:         str           = field(default_factory=lambda: date.today().isoformat())
    documents_analysed:  list[str]     = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "agent_role":         self.agent_role,
            "findings":           [f.to_dict() for f in self.findings],
            "coverage_gaps":      self.coverage_gaps,
            "search_date":        self.search_date,
            "documents_analysed": self.documents_analysed,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def finding_count(self) -> int:
        return len(self.findings)


# ══════════════════════════════════════════════════════════════════
# SECTION 2: WHY STRUCTURED > PLAIN TEXT
# Side-by-side comparison showing attribution loss in plain text.
# ══════════════════════════════════════════════════════════════════

def demonstrate_attribution_loss():
    """
    Shows why plain text summaries destroy provenance,
    while structured findings preserve it end-to-end.
    """
    print("\n" + "=" * 65)
    print("WHY PLAIN TEXT LOSES ATTRIBUTION")
    print("=" * 65)

    # ── What web_searcher returns as plain text (bad) ──────────────
    plain_text_output = """
AI-generated music tracks have grown significantly. According to industry
reports, streaming platforms now host millions of AI-composed songs. The
market for AI music tools is expected to reach $3.2B by 2027. Artists are
divided — some embrace AI as a creative tool while others see it as a threat
to their livelihoods. Spotify and other platforms are developing AI detection
systems.
"""

    # ── What synthesiser receives when passed plain text ───────────
    print("\n❌ Plain text round-trip:")
    print("  web_searcher → coordinator → synthesiser")
    print()
    print("  Synthesiser sees:")
    print(plain_text_output.strip())
    print()
    print("  Synthesiser problems:")
    print("    ✗ '$3.2B by 2027' — which report? What year? Measured or projected?")
    print("    ✗ 'grown significantly' — what percentage? Compared to when?")
    print("    ✗ 'industry reports' — which ones? When published?")
    print("    ✗ Cannot cite, cannot verify, cannot flag confidence level")
    print("    ✗ If two sources conflict, cannot show both with attribution")

    # ── What web_searcher returns as structured findings (good) ────
    structured_output = AgentFindings(
        agent_role="web_searcher",
        findings=[
            StructuredFinding(
                claim="AI-generated music tracks grew 340% year-on-year on major streaming platforms",
                evidence_excerpt="Platform data shows 340% YoY increase in AI-composed content",
                metadata=SourceMetadata(
                    source_url="https://musicindustryreport.com/ai-2024",
                    document_name="Global Music AI Industry Report 2024",
                    page_number=None,
                    section="Streaming Adoption",
                    publication_date="2024-09-15",
                    source_type="industry_report",
                    confidence="measured",
                ),
            ),
            StructuredFinding(
                claim="AI music tools market projected to reach $3.2B by 2027",
                evidence_excerpt="Market analysis projects $3.2B valuation by 2027, up from $890M in 2023",
                metadata=SourceMetadata(
                    source_url="https://marketresearch.com/ai-music-market-2024",
                    document_name="AI Music Tools Market Analysis 2024",
                    page_number=None,
                    section="Market Projections",
                    publication_date="2024-10-01",
                    source_type="industry_report",
                    confidence="estimated",
                ),
            ),
        ],
        coverage_gaps=["Live performance AI adoption not covered by available sources"],
        search_date="2024-11-01",
    )

    print("\n✅ Structured finding round-trip:")
    print("  web_searcher → coordinator → synthesiser")
    print()
    print("  Synthesiser receives:")
    print(structured_output.to_json()[:800] + "\n  ...(truncated)")
    print()
    print("  Synthesiser can now:")
    print("    ✓ Cite: '340% growth [Global Music AI Industry Report 2024, 2024-09-15]'")
    print("    ✓ Confidence: 'measured' vs 'estimated' distinction preserved")
    print("    ✓ Conflict: if another source says 280%, can show both with sources")
    print("    ✓ Gap: note live performance data was absent")


# ══════════════════════════════════════════════════════════════════
# SECTION 3: BUILDING SYNTHESIS INSTRUCTIONS WITH FULL CONTEXT
# Shows exactly how to package prior agent results into a
# synthesis subagent's Task instruction.
# ══════════════════════════════════════════════════════════════════

def build_synthesis_instruction(
    topic: str,
    web_findings: AgentFindings,
    doc_findings: AgentFindings,
    quality_criteria: list[str] | None = None,
) -> str:
    """
    Construct a complete synthesis Task instruction.

    This is the canonical pattern for passing prior agent findings
    to a downstream subagent — EXPLICIT inclusion, not assumption.

    Args:
        topic:            Research topic (needed since subagent has no context)
        web_findings:     Output from web_searcher agent
        doc_findings:     Output from document_analyst agent
        quality_criteria: Optional synthesis quality requirements
    """
    criteria_text = "\n".join(f"  - {c}" for c in (quality_criteria or [
        "Every claim must cite a specific source from the provided findings",
        "Present conflicting data from multiple sources (both values, both sources)",
        "Do not add claims beyond what the provided findings contain",
        "Note coverage gaps where the evidence was thin or absent",
    ]))

    # Key: include the FULL structured findings — not a summary of them
    # Summarising at this point would lose attribution
    instruction = f"""Synthesise research on the following topic into a comprehensive, cited report.

TOPIC: {topic}

════════════════════════════════════════════════════════════
WEB RESEARCH FINDINGS
Source: web_searcher agent | Search date: {web_findings.search_date}
Findings count: {web_findings.finding_count()}
════════════════════════════════════════════════════════════
{web_findings.to_json()}

Coverage gaps from web research:
{chr(10).join(f"  - {g}" for g in web_findings.coverage_gaps) or "  (none noted)"}

════════════════════════════════════════════════════════════
DOCUMENT ANALYSIS FINDINGS
Source: document_analyst agent | Documents: {", ".join(doc_findings.documents_analysed)}
Findings count: {doc_findings.finding_count()}
════════════════════════════════════════════════════════════
{doc_findings.to_json()}

Coverage gaps from document analysis:
{chr(10).join(f"  - {g}" for g in doc_findings.coverage_gaps) or "  (none noted)"}

════════════════════════════════════════════════════════════
SYNTHESIS REQUIREMENTS
════════════════════════════════════════════════════════════
{criteria_text}

OUTPUT FORMAT:
  1. Executive Summary (3-5 sentences, no inline citations required)
  2. Key Findings — each with citation: [Source: document_name, date]
  3. Conflicting Evidence — present both values with both sources
  4. Coverage Gaps — where evidence was thin or absent
  5. Confidence Assessment — overall quality of the evidence base"""

    return instruction


# ══════════════════════════════════════════════════════════════════
# SECTION 4: CONTEXT PACKAGING PATTERNS
# Different ways to include context depending on the downstream
# agent's needs.
# ══════════════════════════════════════════════════════════════════

def package_context_for_subagent(
    subagent_role: str,
    base_task: str,
    prior_findings: dict[str, AgentFindings] | None = None,
    shared_context: dict | None = None,
) -> str:
    """
    Generic context packager. Constructs a self-contained instruction
    for any subagent role.

    The key principle: everything the subagent needs goes in here.
    The coordinator passes nothing else.
    """
    parts = [f"TASK: {base_task}"]

    if shared_context:
        # Shared context available to all subagents in this workflow
        parts.append("\nSHARED CONTEXT (verified by coordinator):")
        for key, value in shared_context.items():
            parts.append(f"  {key}: {value}")

    if prior_findings:
        # Selectively include relevant prior agent outputs
        parts.append("\nFINDINGS FROM PRIOR AGENTS:")
        for agent_name, findings in prior_findings.items():
            parts.append(f"\n[{agent_name.upper()}]")
            # Include full structured data — not a lossy summary
            parts.append(findings.to_json())

    # Role-specific additions
    role_additions = {
        "web_searcher": "\nINSTRUCTION: Return all findings as structured JSON with full metadata.",
        "document_analyst": "\nINSTRUCTION: Analyse only documents provided above. Cite page numbers.",
        "synthesiser": "\nINSTRUCTION: Synthesise ONLY from the provided findings above.",
    }
    parts.append(role_additions.get(subagent_role, ""))

    return "\n".join(parts)


# ══════════════════════════════════════════════════════════════════
# SECTION 5: CONFLICT HANDLING IN SYNTHESIS
# What to do when two sources disagree — preserve both.
# ══════════════════════════════════════════════════════════════════

CONFLICTING_FINDINGS_EXAMPLE = """
EXAMPLE: Two sources disagree on AI music market share

❌ WRONG (coordinator or synthesiser silently picks one):
"The AI music market reached $1.8B in 2024."

✅ CORRECT (both values preserved with sources):
"The AI music market size in 2024 is reported differently by two sources:
  - $1.8B [Global Music AI Industry Report 2024, industry_report, confidence: measured]
  - $2.1B [Soundcharts Market Tracker 2024, news, confidence: estimated]
Note: The discrepancy may reflect different definitions of 'AI music tools' market."
"""

def demonstrate_conflict_handling(findings_a: StructuredFinding, findings_b: StructuredFinding):
    """Show how conflicting findings should be handled in synthesis."""
    print("\n" + "=" * 65)
    print("CONFLICT HANDLING IN SYNTHESIS")
    print("=" * 65)
    print(CONFLICTING_FINDINGS_EXAMPLE)

    # When coordinator passes both to synthesiser, instruction should note:
    conflict_instruction_excerpt = f"""
If you find conflicting statistics or claims from different sources,
PRESERVE BOTH in your output — do not select one over the other.
Format: "[Claim A] [Source: {findings_a.metadata.document_name}] vs 
         [Claim B] [Source: {findings_b.metadata.document_name}]"
Note possible explanations for the discrepancy (different measurement dates,
different market definitions, different methodologies).
"""
    print("Coordinator adds to synthesis instruction:")
    print(conflict_instruction_excerpt)


# ══════════════════════════════════════════════════════════════════
# SECTION 6: COMPLETE EXAMPLE WITH SAMPLE DATA
# Demonstrates a full coordinator → web_searcher → synthesiser
# pipeline with structured finding passing.
# ══════════════════════════════════════════════════════════════════

def run_full_context_passing_demo():
    """
    Demonstrates the complete context-passing flow with sample data.
    Uses simulated findings to show the structure without API calls.
    """
    print("\n" + "=" * 65)
    print("FULL CONTEXT PASSING DEMO: Coordinator → Agents → Synthesis")
    print("=" * 65)

    # Simulate web_searcher output
    web_findings = AgentFindings(
        agent_role="web_searcher",
        findings=[
            StructuredFinding(
                claim="AI music generation tools saw 340% adoption growth in 2024",
                evidence_excerpt="Platform telemetry shows 340% YoY increase in AI-assisted tracks",
                metadata=SourceMetadata(
                    source_url="https://musictech.com/ai-adoption-2024",
                    document_name="MusicTech AI Report 2024",
                    page_number=None,
                    section=None,
                    publication_date="2024-10-15",
                    source_type="industry_report",
                    confidence="measured",
                ),
            ),
            StructuredFinding(
                claim="Professional music producers report 40% reduction in production time using AI tools",
                evidence_excerpt="Survey of 500 producers: median production time reduced from 8 weeks to 4.8 weeks",
                metadata=SourceMetadata(
                    source_url="https://producersurvey.org/2024",
                    document_name="Global Producer Survey 2024",
                    page_number=None,
                    section="Workflow Impact",
                    publication_date="2024-09-01",
                    source_type="academic",
                    confidence="measured",
                ),
            ),
        ],
        coverage_gaps=["AI adoption in live performance not covered"],
        search_date="2024-11-01",
    )

    # Simulate document_analyst output
    doc_findings = AgentFindings(
        agent_role="document_analyst",
        findings=[
            StructuredFinding(
                claim="AI-composed music raises copyright attribution challenges under existing law",
                evidence_excerpt="Current IP frameworks do not clearly address authorship of AI-generated works",
                metadata=SourceMetadata(
                    source_url=None,
                    document_name="AI and Copyright: A Legal Analysis",
                    page_number=23,
                    section="Authorship and Attribution",
                    publication_date="2024-07-01",
                    source_type="academic",
                    confidence="author_opinion",
                ),
            ),
        ],
        coverage_gaps=["Economic impact on session musicians not addressed in provided documents"],
        documents_analysed=["AI and Copyright: A Legal Analysis"],
        search_date="2024-11-01",
    )

    print(f"\nStep 1: web_searcher returns {web_findings.finding_count()} structured findings")
    print(f"Step 2: document_analyst returns {doc_findings.finding_count()} structured findings")
    print("\nStep 3: Coordinator builds synthesis instruction (includes BOTH sets):")

    synthesis_instruction = build_synthesis_instruction(
        topic="Impact of AI on professional music production",
        web_findings=web_findings,
        doc_findings=doc_findings,
    )

    print(f"\nSynthesis instruction size: {len(synthesis_instruction)} chars")
    print("Instruction preview (first 600 chars):")
    print(synthesis_instruction[:600])
    print("\n... (full instruction passed to synthesiser subagent via Task tool)")

    print("\nStep 4: Synthesiser executes with complete, attributed findings")
    print("        Result preserves source citations throughout the report")

    # Show what a synthesiser call looks like
    print("\n" + "─" * 65)
    print("API call the coordinator makes for synthesis subagent:")
    print("─" * 65)
    print("""client.messages.create(
    model="claude-opus-4-6",
    system=SYNTHESISER.system_prompt,      # AgentDefinition
    tools=[],                               # No tools needed
    messages=[{
        "role": "user",
        "content": synthesis_instruction    # ALL findings included
        #           ↑ This is the ONLY context the synthesiser has
        #             It was passed explicitly by the coordinator
    }]
)""")


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Task 1.3 — Context Passing and Attribution Preservation")
    print("=" * 65)

    demonstrate_attribution_loss()
    run_full_context_passing_demo()

    print("\n✓ Context passing patterns demonstrated.")
    print("  See parallel_spawning.py for parallel Task emission and fork_session.")
