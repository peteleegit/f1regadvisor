"""Procedural Strategy Agent — Phase 3.

Recommends mitigations and a clear recommended course of action based on
all Phase 1 and Phase 2 outputs.
"""
from __future__ import annotations

import json
from pydantic import BaseModel

from f1reg.agents.base import BaseAgent
from f1reg.context import MemoContext

_ACTION_OPTIONS = (
    "Proceed as designed",
    "Modify then proceed",
    "Seek FIA clarification before proceeding",
    "Escalate to legal counsel",
    "Prepare regulatory defence",
    "Do not proceed",
)

_SYSTEM = f"""\
You are a Formula 1 regulatory strategy specialist. Based on a regulatory risk analysis \
and adversarial debate, you recommend specific mitigations and a clear course of action.

Be specific and actionable. Generic advice ("consult lawyers") is not useful. \
Each mitigation should identify a concrete design change, operating constraint, \
documentation step, or procedural action.

RECOMMENDED ACTION must be exactly one of:
{chr(10).join(f"  - {o}" for o in _ACTION_OPTIONS)}

Respond only with this JSON object — no preamble, no markdown fences:

{{
  "recommended_action": "<one of the options above>",
  "recommended_action_rationale": "<2-3 sentences explaining why — plain English>",
  "mitigations": [
    "<specific mitigation 1>",
    "<specific mitigation 2>",
    ...
  ]
}}"""

_USER = """\
CONCEPT:
{concept}

{phase1_context}

DEBATE SUMMARY:
{debate_transcript}

POLITICAL & RIVAL RISK:
{political_economy}

RIVAL PROTEST SIMULATION:
{rival_protest}

Based on all of the above, provide your recommended action and mitigations."""


class ProceduralStrategyOutput(BaseModel):
    recommended_action: str
    recommended_action_rationale: str
    mitigations: list[str] = []


class ProceduralStrategyAgent(BaseAgent):

    def analyse(self, ctx: MemoContext, phase1_context: str) -> ProceduralStrategyOutput:
        msg = _USER.format(
            concept=ctx.concept.summary,
            phase1_context=phase1_context,
            debate_transcript=ctx.debate_transcript(),
            political_economy=ctx.political_economy_analysis or "(not available)",
            rival_protest=ctx.rival_protest_analysis or "(not available)",
        )
        raw = self._call(_SYSTEM, [{"role": "user", "content": msg}])
        return _parse(raw)


def _parse(raw: str) -> ProceduralStrategyOutput:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0].strip()
    try:
        data = json.loads(text)
        return ProceduralStrategyOutput(**{k: v for k, v in data.items()
                                           if k in ProceduralStrategyOutput.model_fields})
    except Exception:
        return ProceduralStrategyOutput(
            recommended_action="Escalate to legal counsel",
            recommended_action_rationale="Could not parse structured output.",
            mitigations=[raw],
        )
