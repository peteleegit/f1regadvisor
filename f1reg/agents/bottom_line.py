"""Bottom Line Synthesis Agent — Phase 5.

Reads all prior agent outputs and produces the final verdict, concise
argument summaries, political risk summary, and open questions.
Uses claude-opus-4-7.

Output is intentionally terse — the memo readers are extremely busy people.
"""
from __future__ import annotations

import json
from pydantic import BaseModel

from f1reg.agents.base import BaseAgent
from f1reg.config import settings
from f1reg.context import AuditFinding, MemoContext

_VERDICTS = (
    "LIKELY PERMITTED",
    "LIKELY PROHIBITED",
    "AMBIGUOUS",
    "HIGH-RISK GREY AREA",
    "REQUIRES FIA CLARIFICATION",
)

_SYSTEM = f"""\
You are the final synthesising agent for a Formula 1 regulatory risk memo. \
Your readers are extremely busy Formula 1 executives and legal counsel. \
Every word costs them attention.

ABSOLUTE RULES — violating these makes the memo useless:
1. bottom_line_summary: TWO SENTENCES MAXIMUM. Plain English. No qualifications or hedging. \
   State the risk directly.
2. political_risk_summary: THREE SENTENCES MAXIMUM. Cover: rival protest likelihood, \
   FIA political dynamics, and media/public exposure.
3. arguments_for and arguments_against: 3-5 bullets each. Each bullet ≤ 20 words.
4. open_questions: genuine unresolved issues only — not summaries of what was covered.

VERDICT (choose exactly one):
{chr(10).join(f"  {v}" for v in _VERDICTS)}

CONFIDENCE (choose exactly one):
  high confidence / moderate confidence / low confidence

Respond only with this JSON — no preamble, no markdown fences:

{{
  "bottom_line_verdict": "<verdict>",
  "bottom_line_confidence": "<confidence>",
  "bottom_line_summary": "<two sentences maximum>",
  "political_risk_summary": "<three sentences maximum>",
  "arguments_for": ["<≤20 words>", ...],
  "arguments_against": ["<≤20 words>", ...],
  "open_questions": ["...", ...]
}}"""

_USER = """\
CONCEPT: {concept} (Season: {season})

REGULATORY ANALYSIS:
{regulatory_summary}

PRECEDENT ANALYSIS:
{precedent_summary}

DEBATE TRANSCRIPT:
{debate_transcript}

POLITICAL ECONOMY ANALYSIS:
{political_economy}

RIVAL PROTEST SIMULATION:
{rival_protest}

RECOMMENDED ACTION: {recommended_action}
RATIONALE: {rationale}

MITIGATIONS:
{mitigations}

AUDIT FINDINGS:
{audit_findings}

Synthesise the above into the final bottom line JSON."""


class BottomLineOutput(BaseModel):
    bottom_line_verdict: str
    bottom_line_confidence: str
    bottom_line_summary: str
    political_risk_summary: str = ""
    arguments_for: list[str] = []
    arguments_against: list[str] = []
    open_questions: list[str] = []


class BottomLineAgent(BaseAgent):
    model: str = settings.senior_model

    def synthesise(self, ctx: MemoContext) -> BottomLineOutput:
        audit_text = _format_audit(ctx.audit_findings)
        msg = _USER.format(
            concept=ctx.concept.summary,
            season=ctx.concept.season,
            regulatory_summary=ctx.regulatory_summary or "(not available)",
            precedent_summary=ctx.precedent_summary or "(not available)",
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


def _format_audit(findings: list[AuditFinding]) -> str:
    if not findings:
        return "No audit findings."
    lines = []
    for f in findings:
        lines.append(f"[{f.severity}] {f.implicated_agent}: {f.issue}")
    return "\n".join(lines)


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
            bottom_line_verdict="REQUIRES FIA CLARIFICATION",
            bottom_line_confidence="low confidence",
            bottom_line_summary="Could not synthesise verdict — review full analysis manually.",
        )
