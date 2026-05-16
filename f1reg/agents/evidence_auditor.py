"""Evidence Auditor — Phase 4.

Reviews all agent outputs for quality issues.  Uses claude-opus-4-7 for
deeper cross-agent reasoning.  HIGH severity findings are flagged prominently
in the memo; LOW severity findings are added to Open Questions.
"""
from __future__ import annotations

import json

from f1reg.agents.base import BaseAgent
from f1reg.config import settings
from f1reg.context import AuditFinding, MemoContext

_SYSTEM = """\
You are the Evidence Auditor for a multi-agent Formula 1 regulatory risk assessment. \
Review all agent outputs for quality issues.

Check for:
1. Conclusions stated as certain when they are inferences or extrapolations
2. Rules from the wrong season, outdated versions, or superseded regulations cited as current
3. Speculation not clearly labelled as such
4. Contradictions across agents that are not acknowledged
5. Material legal risks raised in the analysis but absent from the recommended mitigations
6. Over-reliance on public media reporting treated as authoritative

SEVERITY:
- HIGH: a material error that meaningfully changes the legal risk assessment
- LOW: a minor labelling issue, a missing caveat, or an additional consideration

Report only genuine issues. Do not manufacture findings to appear thorough.

Respond only with this JSON — no preamble, no markdown fences:

{
  "findings": [
    {
      "severity": "HIGH or LOW",
      "implicated_agent": "name of the agent whose output has the issue",
      "issue": "concise description of the problem",
      "recommendation": "specific correction or caveat to add"
    }
  ]
}

If you find no issues, return: {"findings": []}"""

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

Audit the above for quality issues."""


class EvidenceAuditorAgent(BaseAgent):
    model: str = settings.senior_model

    def audit(self, ctx: MemoContext) -> list[AuditFinding]:
        msg = _USER.format(
            concept=ctx.concept.summary,
            season=ctx.concept.season,
            regulatory_summary=ctx.regulatory_summary or "(not available)",
            precedent_summary=ctx.precedent_summary or "(not available)",
            debate_transcript=ctx.debate_transcript(),
            political_economy=ctx.political_economy_analysis or "(not available)",
            rival_protest=ctx.rival_protest_analysis or "(not available)",
            recommended_action=ctx.recommended_action or "(not available)",
            rationale=ctx.recommended_action_rationale or "(not available)",
            mitigations=ctx.mitigations or "(not available)",
        )
        raw = self._call(_SYSTEM, [{"role": "user", "content": msg}])
        return _parse(raw)


def _parse(raw: str) -> list[AuditFinding]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0].strip()
    try:
        data = json.loads(text)
        findings = []
        for f in data.get("findings", []):
            findings.append(AuditFinding(
                severity=f.get("severity", "LOW"),
                implicated_agent=f.get("implicated_agent", "Unknown"),
                issue=f.get("issue", ""),
                recommendation=f.get("recommendation", ""),
            ))
        return findings
    except Exception:
        return []
