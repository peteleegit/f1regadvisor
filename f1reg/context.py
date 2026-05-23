"""Shared pipeline state — MemoContext accumulates all agent outputs."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Phase 0 — Technical Concept Agent output
# ---------------------------------------------------------------------------

class ConceptDecomposition(BaseModel):
    summary: str
    season: str = "2026"
    component: Optional[str] = None
    system: Optional[str] = None
    operating_condition: Optional[str] = None
    driver_input: Optional[str] = None
    software_behaviour: Optional[str] = None
    aerodynamic_effect: Optional[str] = None
    event_type: Optional[str] = None
    test_condition: Optional[str] = None
    visibility_to_rivals: Optional[str] = None
    cost_cap_implications: Optional[str] = None
    regulatory_queries: list[str] = field(default_factory=list)

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Phase 1 — Regulatory Text Agent and Precedent Agent outputs
# ---------------------------------------------------------------------------

class RegulatoryTextOutput(BaseModel):
    summary: str
    controlling_articles: list[str] = []
    key_definitions: list[str] = []
    cross_references: list[str] = []
    gaps: list[str] = []
    # Each entry: "<INTENT_LABEL> — <article/rule>: <what is ambiguous and why>"
    # INTENT_LABEL one of: PRESERVED DISCRETION | DRAFTING IMPRECISION | UNKNOWN
    ambiguities: list[str] = []


class PrecedentOutput(BaseModel):
    summary: str
    comparable_cases: list[str] = []
    analogous_cases: list[str] = []
    distinctions: list[str] = []
    gaps: list[str] = []
    # CONSISTENT | MIXED | CONTRADICTORY | INSUFFICIENT PRECEDENT
    consistency_rating: str = "INSUFFICIENT PRECEDENT"
    # MORE PERMISSIVE | MORE RESTRICTIVE | STABLE | UNCLEAR
    trend_direction: str = "UNCLEAR"
    consistency_analysis: str = ""


# ---------------------------------------------------------------------------
# Phase 2 — Debate
# ---------------------------------------------------------------------------

@dataclass
class DebateRound:
    round_number: int
    skeptic_argument: str
    defense_argument: str


# ---------------------------------------------------------------------------
# Phase 4 — Evidence Auditor findings
# ---------------------------------------------------------------------------

@dataclass
class AuditFinding:
    severity: str          # "HIGH" or "LOW"
    implicated_agent: str  # which agent produced the problematic output
    issue: str
    recommendation: str


# ---------------------------------------------------------------------------
# Top-level pipeline state
# ---------------------------------------------------------------------------

@dataclass
class MemoContext:
    raw_input: str
    uploaded_text: Optional[str] = None     # text extracted from uploaded document

    # Phase 0
    concept: Optional[ConceptDecomposition] = None

    # Phase 1
    regulation_hits: list = field(default_factory=list)
    precedent_hits: list = field(default_factory=list)
    regulatory_summary: Optional[str] = None
    precedent_summary: Optional[str] = None
    regulatory_text_output: Optional[RegulatoryTextOutput] = None
    precedent_output: Optional[PrecedentOutput] = None

    # Phase 2 — debate + political economy (runs alongside Round 2)
    debate_rounds: list[DebateRound] = field(default_factory=list)
    political_economy_analysis: Optional[str] = None

    # Phase 2.5 — rival protest (sees full debate transcript)
    rival_protest_analysis: Optional[str] = None

    # Phase 3 — procedural strategy
    mitigations: Optional[str] = None
    recommended_action: Optional[str] = None
    recommended_action_rationale: Optional[str] = None

    # Phase 4 — evidence audit
    audit_findings: list[AuditFinding] = field(default_factory=list)

    # Phase 5 — synthesised bottom line
    # legal_standing: what the rules say read in good faith
    #   TEXTUALLY COMPLIANT | TEXTUALLY NON-COMPLIANT | GENUINELY AMBIGUOUS
    legal_standing: Optional[str] = None
    # enforcement_risk: what the FIA is likely to actually do
    #   LOW | MODERATE | HIGH | POLITICALLY DETERMINED
    enforcement_risk: Optional[str] = None
    # fia_predictability: how consistently the FIA applies rules in this area
    #   HIGH | MEDIUM | LOW | UNPREDICTABLE
    fia_predictability: Optional[str] = None
    bottom_line_summary: Optional[str] = None
    political_risk_summary: Optional[str] = None
    arguments_for: Optional[str] = None
    arguments_against: Optional[str] = None
    open_questions: Optional[str] = None

    # Final assembled memo (Markdown)
    memo_markdown: Optional[str] = None

    # ---------------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------------

    def debate_transcript(self) -> str:
        _labels = {
            1: "Round 1: Opening Statements",
            2: "Round 2: Rebuttals",
            3: "Round 3: Closing Statements",
        }
        if not self.debate_rounds:
            return ""
        lines: list[str] = []
        for r in self.debate_rounds:
            label = _labels.get(r.round_number, f"Round {r.round_number}")
            lines.append(f"### {label}")
            lines.append(f"**FIA Skeptic:**\n{r.skeptic_argument}")
            lines.append(f"**Liberal Construction / Defence:**\n{r.defense_argument}")
        return "\n\n".join(lines)
