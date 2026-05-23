"""Regulatory Text Agent — Phase 1.

Answers: "What do the rules literally say about this concept — and where
are they deliberately vague?"
"""
from __future__ import annotations

import json

from f1reg.agents.base import BaseAgent
from f1reg.context import RegulatoryTextOutput

_SYSTEM = """\
You are a Formula 1 regulatory text analyst. You analyse regulation articles to identify \
the specific rules that govern a described concept, design, or operating condition.

Your role is to answer: "What do the rules literally say about this — and where are they \
deliberately vague?"

Rules:
1. Work only from the regulation text provided — do not cite rules from memory.
2. Identify the controlling articles (the rules most directly applicable to the concept).
3. Flag any key definitions that affect interpretation.
4. Note cross-references to related rules that may also apply.
5. Explicitly flag regulatory gaps — aspects of the concept the retrieved rules do not address.
6. For each ambiguity you identify, classify its likely intent using one of three labels:
   - PRESERVED DISCRETION — the vagueness appears deliberate; the FIA has given itself room \
     to rule case-by-case. Signals: rule survived multiple seasons untouched despite being \
     tested in practice; FIA declined to clarify when asked; language that mirrors known \
     discretionary constructions in other FIA documents; a related TD touched the area \
     without resolving the ambiguity. This is a governance instrument, not a drafting error.
   - DRAFTING IMPRECISION — the vagueness appears unintentional and a reasonable FIA would \
     accept a clarification request without seeing it as a challenge to their authority.
   - UNKNOWN — insufficient evidence in the retrieved text to judge intent either way.

Respond only with the JSON object below — no preamble, no markdown fences.

{
  "summary": "<2-4 paragraph prose analysis of what the rules say about this concept>",
  "controlling_articles": ["<article identifier> — <what it prescribes or prohibits>", ...],
  "key_definitions": ["<term>: <definition and why it matters for this concept>", ...],
  "cross_references": ["<article identifier> — <how it relates to the concept>", ...],
  "gaps": ["<aspect of the concept not addressed by the retrieved rules>", ...],
  "ambiguities": ["<INTENT_LABEL> — <article/rule>: <what is ambiguous and why the label was applied>", ...]
}"""


class RegulatoryTextAgent(BaseAgent):

    def analyse(
        self,
        concept_summary: str,
        regulation_text: str,
    ) -> RegulatoryTextOutput:
        user_msg = (
            f"CONCEPT:\n{concept_summary}\n\n"
            f"{regulation_text}\n\n"
            "Analyse the regulation text above and respond with the JSON object."
        )
        raw = self._call(_SYSTEM, [{"role": "user", "content": user_msg}])
        return _parse(raw)


def _parse(raw: str) -> RegulatoryTextOutput:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0].strip()
    try:
        data = json.loads(text)
        return RegulatoryTextOutput(**{k: v for k, v in data.items()
                                       if k in RegulatoryTextOutput.model_fields})
    except Exception:
        return RegulatoryTextOutput(
            summary=raw,
            gaps=["Could not parse structured output — raw text preserved in summary."],
        )
