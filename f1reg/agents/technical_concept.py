"""Technical Concept Agent — Phase 0 interactive intake gate."""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from pydantic import BaseModel

from f1reg.agents.base import BaseAgent
from f1reg.config import DEFAULT_SEASON
from f1reg.context import ConceptDecomposition

_SYSTEM_PROMPT = """\
You are the Technical Concept Agent for F1RegAdvisor, a regulatory risk assessment \
system for a Formula 1 team.

Your role is to gather enough information about a proposed concept, design, or idea \
to enable a thorough regulatory risk assessment. A team of specialist AI agents will \
then assess the concept against FIA regulations, stewards precedents, legal arguments, \
protest risk, and paddock dynamics.

To build an effective assessment, you need to understand the concept across these \
dimensions:
- component: the physical part or system involved
- system: which car system (aerodynamic, mechanical, power unit, electrical, \
software, structural)
- operating_condition: when or under what conditions it behaves differently from normal
- driver_input: whether and how the driver controls it
- software_behaviour: any sensor, software, electronic control, or closed-loop \
feedback involved
- aerodynamic_effect: the aerodynamic consequence
- event_type: all events, or specific conditions (race, qualifying, sprint, \
promotional)
- test_condition: whether it would be detectable under FIA scrutineering or \
load/deflection tests
- visibility_to_rivals: how visible the mechanism is to competitors during a \
race weekend
- cost_cap_implications: novel development costs, amortisation questions, or \
supplier considerations

Rules:
1. Ask at most THREE follow-up questions before committing to a decomposition. \
Ask only ONE question per turn — the most important missing piece.
2. If you can make a reasonable inference from the information provided, do so \
and note it in the relevant field.
3. If a document has been provided, extract relevant facts from it before \
asking questions.
4. The regulatory_queries you generate will be run verbatim against a corpus of \
FIA Technical Regulations, Sporting Regulations, Financial Regulations, Technical \
Directives, and Stewards decisions. Make them specific, varied, and covering different \
regulatory angles (the component, the physical effect, the test, the relevant \
definition).

When you need more information, respond with this exact JSON and nothing else:
{
  "ready": false,
  "question": "<single focused technical question, 1-2 sentences>",
  "question_display": "<same question, phrased conversationally for display>"
}

When you have enough information to proceed, respond with this exact JSON and \
nothing else:
{
  "ready": true,
  "summary": "<one precise sentence describing the concept and its regulatory \
significance>",
  "season": "<four-digit year, default %(season)s>",
  "component": "<or null>",
  "system": "<or null>",
  "operating_condition": "<or null>",
  "driver_input": "<or null>",
  "software_behaviour": "<or null>",
  "aerodynamic_effect": "<or null>",
  "event_type": "<or null>",
  "test_condition": "<or null>",
  "visibility_to_rivals": "<or null>",
  "cost_cap_implications": "<or null>",
  "regulatory_queries": [
    "<3 to 6 targeted search queries covering distinct regulatory angles>"
  ]
}

Respond only with the JSON object. No preamble, no markdown fences, no explanation \
outside the JSON.
""" % {"season": DEFAULT_SEASON}


class TCAResponse(BaseModel):
    ready: bool
    # When ready=False
    question: str = ""
    question_display: str = ""
    # When ready=True
    decomposition: Optional[ConceptDecomposition] = None


class TechnicalConceptAgent(BaseAgent):
    """Interactive intake agent that clarifies the concept before the pipeline runs."""

    max_tokens: int = 1500

    def process(
        self,
        conversation: list[dict[str, Any]],
        uploaded_text: str | None = None,
    ) -> TCAResponse:
        """Process one turn of the intake conversation.

        Args:
            conversation: Full message history as [{"role": ..., "content": ...}].
                The first message is always the user's initial concept description.
            uploaded_text: Optional text extracted from an uploaded document.

        Returns:
            TCAResponse with either a clarifying question or the ready decomposition.
        """
        messages = list(conversation)

        # On the first turn, prepend document text to the user message if provided
        if uploaded_text and len(messages) == 1:
            messages[0] = {
                "role": "user",
                "content": (
                    f"<uploaded_document>\n{uploaded_text}\n</uploaded_document>\n\n"
                    f"{messages[0]['content']}"
                ),
            }

        raw = self._call(_SYSTEM_PROMPT, messages)
        return _parse_response(raw)


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _parse_response(text: str) -> TCAResponse:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Fallback: treat the raw text as a question
        return TCAResponse(ready=False, question=text, question_display=text)

    if data.get("ready"):
        data.pop("ready", None)
        try:
            decomp = ConceptDecomposition(**data)
        except Exception:
            # If the decomposition fails to parse, ask for more info
            return TCAResponse(
                ready=False,
                question="I wasn't able to structure the concept clearly. Could you describe it again in more detail?",
                question_display="I wasn't able to structure the concept clearly. Could you describe it again in more detail?",
            )
        return TCAResponse(ready=True, decomposition=decomp)

    return TCAResponse(
        ready=False,
        question=data.get("question", ""),
        question_display=data.get("question_display", data.get("question", "")),
    )
