"""Bottom Line Synthesis Agent — Phase 5.

Produces the final verdict across two tracks: what the rules say (legal
standing) and what the FIA will likely do (enforcement risk). These two
tracks can and often do diverge.

Uses claude-opus-4-7. Output is intentionally terse.
"""
from __future__ import annotations

import json
from pydantic import BaseModel

from f1reg.agents.base import BaseAgent
from f1reg.config import settings
from f1reg.context import AuditFinding, MemoContext

_LEGAL_STANDINGS = (
    "TEXTUALLY COMPLIANT",
    "TEXTUALLY NON-COMPLIANT",
    "GENUINELY AMBIGUOUS",
)

_ENFORCEMENT_RISKS = (
    "LOW",
    "MODERATE",
    "HIGH",
    "POLITICALLY DETERMINED",
)

_FIA_PREDICTABILITY = (
    "HIGH",
    "MEDIUM",
    "LOW",
    "UNPREDICTABLE",
)

_SYSTEM = """\
You are the final synthesising agent for a Formula 1 regulatory risk memo. \
Your readers are extremely busy Formula 1 executives and legal counsel. \
Every word costs them attention.

Your job is to produce two honest assessments that may diverge:

TRACK A — LEGAL STANDING: What would a neutral, expert reader of the rule text conclude? \
This is purely about what the rules say, read in good faith. It is not a prediction of \
what the FIA will do.

TRACK B — ENFORCEMENT RISK: What will the FIA actually do? This is primarily driven by \
the political economy analysis, the precedent consistency, and the FIA's demonstrated \
use of ambiguity as a governance instrument — not by the textual analysis. Where the \
political economy analysis identifies specific FIA actors and their known tendencies, \
weight this heavily.

A critical insight: the FIA regulatory system is deliberately designed with ambiguity \
that gives regulators maximum discretion. A concept can be textually compliant and still \
face high enforcement risk if the political conditions are adverse. Your bottom_line_summary \
must be honest about this gap when it exists.

ABSOLUTE RULES — violating these makes the memo useless:
1. bottom_line_summary: THREE SENTENCES MAXIMUM. First sentence: legal standing and why. \
   Second sentence: enforcement risk and what drives it. Third sentence (only if needed): \
   the key factor that could shift the outcome either way. Plain English. No hedging.
2. political_risk_summary: THREE SENTENCES MAXIMUM. Cover: rival protest likelihood, \
   key FIA actor dynamics, and media/public exposure.
3. arguments_for and arguments_against: 3-5 bullets each. Each bullet ≤ 20 words.
4. open_questions: 3 items maximum. Genuine unresolved issues only. Empty list if none.

LEGAL STANDING (choose exactly one):
  TEXTUALLY COMPLIANT — a neutral expert reading the rules would conclude the concept is permitted
  TEXTUALLY NON-COMPLIANT — a neutral expert reading the rules would conclude it is not permitted
  GENUINELY AMBIGUOUS — the rules do not resolve the question; reasonable experts would disagree

ENFORCEMENT RISK (choose exactly one):
  LOW — FIA is unlikely to challenge this; political conditions support tolerance
  MODERATE — meaningful risk of challenge; outcome depends on how the concept is framed and who objects
  HIGH — FIA challenge or restriction is likely regardless of the textual analysis
  POLITICALLY DETERMINED — the textual analysis is essentially irrelevant; outcome will be decided \
    by political calculus, competitive stakes, and who has influence at the FIA at the time

FIA PREDICTABILITY (choose exactly one):
  HIGH — the FIA has applied rules in this area consistently; precedent is a reliable guide
  MEDIUM — some inconsistency but a discernible pattern; context matters
  LOW — the FIA has applied rules in this area inconsistently; precedent offers limited guidance
  UNPREDICTABLE — the FIA has contradicted itself in this area; past decisions provide no reliable basis

Respond only with this JSON — no preamble, no markdown fences:

{
  "legal_standing": "<LEGAL STANDING>",
  "enforcement_risk": "<ENFORCEMENT RISK>",
  "fia_predictability": "<FIA PREDICTABILITY>",
  "bottom_line_summary": "<three sentences maximum>",
  "political_risk_summary": "<three sentences maximum>",
  "arguments_for": ["<≤20 words>", ...],
  "arguments_against": ["<≤20 words>", ...],
  "open_questions": ["...", ...]
}"""

_USER = """\
CONCEPT: {concept} (Season: {season})

REGULATORY ANALYSIS:
{regulatory_summary}

REGULATORY AMBIGUITIES (classified by intent):
{regulatory_ambiguities}

PRECEDENT ANALYSIS:
{precedent_summary}

PRECEDENT CONSISTENCY: {consistency_rating} | Trend: {trend_direction}
{consistency_analysis}

DEBATE TRANSCRIPT:
{debate_transcript}

POLITICAL ECONOMY ANALYSIS (primary input for enforcement risk and FIA predictability):
{political_economy}

RIVAL PROTEST SIMULATION:
{rival_protest}

RECOMMENDED ACTION: {recommended_action}
RATIONALE: {rationale}

MITIGATIONS:
{mitigations}

AUDIT FINDINGS:
{audit_findings}

Synthesise the above into the final bottom line JSON. Remember: legal standing is what \
the rules say; enforcement risk is what the FIA will do. These can diverge significantly."""


class BottomLineOutput(BaseModel):
    legal_standing: str
    enforcement_risk: str
    fia_predictability: str
    bottom_line_summary: str
    political_risk_summary: str = ""
    arguments_for: list[str] = []
    arguments_against: list[str] = []
    open_questions: list[str] = []


class BottomLineAgent(BaseAgent):
    model: str = settings.verdict_model

    def synthesise(self, ctx: MemoContext) -> BottomLineOutput:
        audit_text = _format_audit(ctx.audit_findings)
        rto = ctx.regulatory_text_output
        po = ctx.precedent_output
        msg = _USER.format(
            concept=ctx.concept.summary,
            season=ctx.concept.season,
            regulatory_summary=ctx.regulatory_summary or "(not available)",
            regulatory_ambiguities=_format_ambiguities(rto),
            precedent_summary=ctx.precedent_summary or "(not available)",
            consistency_rating=po.consistency_rating if po else "INSUFFICIENT PRECEDENT",
            trend_direction=po.trend_direction if po else "UNCLEAR",
            consistency_analysis=po.consistency_analysis if po else "",
            debate_transcript=ctx.debate_transcript(),
            political_economy=ctx.political_economy_analysis or "(not available)",
            rival_protest=ctx.rival_protest_analysis or "(not available)",
            recommended_action=ctx.recommended_action or "(not available)",
            rationale=ctx.recommended_action_rationale or "",
            mitigations=ctx.mitigations or "(not available)",
            audit_findings=audit_text,
        )
        raw = self._call(_SYSTEM, [{"role": "user", "content": msg}])
        return _parse(raw)


def _format_ambiguities(rto) -> str:
    if not rto or not rto.ambiguities:
        return "(none identified)"
    return "\n".join(f"- {a}" for a in rto.ambiguities)


def _format_audit(findings: list[AuditFinding]) -> str:
    if not findings:
        return "No audit findings."
    return "\n".join(f"[{f.severity}] {f.implicated_agent}: {f.issue}" for f in findings)


def _parse(raw: str) -> BottomLineOutput:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0].strip()
    try:
        data = json.loads(text)
        return BottomLineOutput(**{k: v for k, v in data.items()
                                    if k in BottomLineOutput.model_fields})
    except Exception:
        return BottomLineOutput(
            legal_standing="GENUINELY AMBIGUOUS",
            enforcement_risk="MODERATE",
            fia_predictability="LOW",
            bottom_line_summary="Could not synthesise verdict — review full analysis manually.",
        )
