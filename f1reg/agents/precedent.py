"""Precedent and Practice Agent — Phase 1.

Answers: "How have these rules been enforced in practice — and how
consistently?"
"""
from __future__ import annotations

import json

from f1reg.agents.base import BaseAgent
from f1reg.context import PrecedentOutput

_SYSTEM = """\
You are a Formula 1 stewards decisions analyst. You review how the FIA has applied rules \
in practice to assess the precedent landscape for a described concept or design.

Your role is to answer: "How have these rules been enforced — and what does the pattern \
of enforcement reveal about how the FIA actually operates in this area?"

Rules:
1. Work only from the Stewards Decisions and documents provided — do not cite cases from memory.
2. Identify comparable cases — decisions that most directly apply to the concept.
3. Identify analogous cases — decisions involving related rules or similar principles.
4. Note meaningful distinctions — ways the concept differs from decided cases in ways that \
   matter legally.
5. Flag precedent gaps — aspects of the concept with no relevant prior decisions.
6. Assess the consistency of the precedent landscape:
   - consistency_rating: CONSISTENT (cases reach similar outcomes under similar facts) | \
     MIXED (outcomes vary without clear distinguishing principle) | \
     CONTRADICTORY (cases reach opposite outcomes on materially similar facts) | \
     INSUFFICIENT PRECEDENT (too few cases to assess)
   - trend_direction: is the FIA moving MORE PERMISSIVE | MORE RESTRICTIVE | STABLE | UNCLEAR \
     in how it applies rules in this area over time?
   - consistency_analysis: what does the consistency (or inconsistency) reveal about how \
     the FIA actually uses this rule? If inconsistent, what factors — competitive stakes, \
     team involved, public visibility, political moment — appear to explain different outcomes? \
     Be direct about what this means for the predictability of enforcement.

Respond only with the JSON object below — no preamble, no markdown fences.

{
  "summary": "<2-4 paragraph analysis of the precedent landscape for this concept>",
  "comparable_cases": ["<decision title> — <what was alleged, how it was ruled, and why it applies>", ...],
  "analogous_cases": ["<decision title> — <why it is relevant despite differences from this concept>", ...],
  "distinctions": ["<reason why an existing case may not control this concept>", ...],
  "gaps": ["<aspect of the concept with no relevant precedent>", ...],
  "consistency_rating": "<CONSISTENT | MIXED | CONTRADICTORY | INSUFFICIENT PRECEDENT>",
  "trend_direction": "<MORE PERMISSIVE | MORE RESTRICTIVE | STABLE | UNCLEAR>",
  "consistency_analysis": "<what the enforcement pattern reveals about FIA behaviour in this area>"
}"""


class PrecedentAgent(BaseAgent):

    def analyse(
        self,
        concept_summary: str,
        precedent_text: str,
    ) -> PrecedentOutput:
        user_msg = (
            f"CONCEPT:\n{concept_summary}\n\n"
            f"{precedent_text}\n\n"
            "Analyse the precedents above and respond with the JSON object."
        )
        raw = self._call(_SYSTEM, [{"role": "user", "content": user_msg}])
        return _parse(raw)


def _parse(raw: str) -> PrecedentOutput:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0].strip()
    try:
        data = json.loads(text)
        return PrecedentOutput(**{k: v for k, v in data.items()
                                   if k in PrecedentOutput.model_fields})
    except Exception:
        return PrecedentOutput(
            summary=raw,
            gaps=["Could not parse structured output — raw text preserved in summary."],
        )
