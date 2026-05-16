"""FIA Skeptic and Liberal Construction (Defence) agents — Phase 2.

Both agents produce plain-prose arguments; no JSON output.  Inferences and
policy arguments must be labelled explicitly in the text itself.

Every `argue` / `rebut` / `final_rebuttal` method has a `stream_*` twin that
yields raw text chunks for real-time display in the Streamlit UI.
"""
from __future__ import annotations

from collections.abc import Generator

from f1reg.agents.base import BaseAgent

# ---------------------------------------------------------------------------
# Shared preamble injected into every debate prompt
# ---------------------------------------------------------------------------

_LABEL_RULE = (
    "You MAY argue beyond what the retrieved text strictly supports, but you MUST "
    "label such moves explicitly: use phrases like \"By inference...\", "
    "\"On policy grounds...\", \"In spirit if not letter...\", "
    "\"This is an extrapolation, but...\". Never present an inference as a fact.\n\n"
    "Respond in plain prose. Be sharp, specific, and adversarial. "
    "Do not use JSON. Do not use section headers unless they genuinely help. "
    "Length: 300-600 words."
)

# ---------------------------------------------------------------------------
# FIA Skeptic / Prosecutor Agent
# ---------------------------------------------------------------------------

_SKEPTIC_SYSTEM = f"""\
You are the FIA's chief regulatory prosecutor arguing before the stewards. \
Your mandate is to build the strongest possible case that the described concept \
violates the regulations, violates the intent of the rules, threatens sporting \
integrity or safety, or should be restricted via a technical directive or \
clarification.

{_LABEL_RULE}"""

_SKEPTIC_R1_USER = """\
CONCEPT:
{concept}

{phase1_context}

Build your opening argument against this concept. Identify the strongest regulatory \
objection and press it hard. What is the best case that this is illegal or should be \
restricted?"""

_SKEPTIC_R2_USER = """\
CONCEPT:
{concept}

{phase1_context}

YOUR ROUND 1 ARGUMENT:
{own_r1}

OPPONENT'S ROUND 1 ARGUMENT (Defence):
{opponent_r1}

The Defence has now made its opening case. Your job is to respond directly to the \
weakest points in that argument — the assumptions that do not hold, the precedents \
that are misread, the constructions that are too favourable. Do not repeat your \
Round 1 verbatim; advance the argument by engaging with what the Defence said."""

_SKEPTIC_R3_USER = """\
CONCEPT:
{concept}

{phase1_context}

FULL DEBATE SO FAR:
{transcript}

This is the final rebuttal round. Make your most precise and damaging point — the \
single strongest objection that the Defence has not adequately answered. Be surgical."""


class FIASkepticAgent(BaseAgent):

    def argue(self, concept: str, phase1_context: str) -> str:
        msg = _SKEPTIC_R1_USER.format(concept=concept, phase1_context=phase1_context)
        return self._call(_SKEPTIC_SYSTEM, [{"role": "user", "content": msg}])

    def stream_argue(self, concept: str, phase1_context: str) -> Generator[str, None, None]:
        msg = _SKEPTIC_R1_USER.format(concept=concept, phase1_context=phase1_context)
        yield from self._stream(_SKEPTIC_SYSTEM, [{"role": "user", "content": msg}])

    def rebut(self, concept: str, phase1_context: str, own_r1: str, opponent_r1: str) -> str:
        msg = _SKEPTIC_R2_USER.format(
            concept=concept, phase1_context=phase1_context,
            own_r1=own_r1, opponent_r1=opponent_r1,
        )
        return self._call(_SKEPTIC_SYSTEM, [{"role": "user", "content": msg}])

    def stream_rebut(self, concept: str, phase1_context: str, own_r1: str, opponent_r1: str) -> Generator[str, None, None]:
        msg = _SKEPTIC_R2_USER.format(
            concept=concept, phase1_context=phase1_context,
            own_r1=own_r1, opponent_r1=opponent_r1,
        )
        yield from self._stream(_SKEPTIC_SYSTEM, [{"role": "user", "content": msg}])

    def final_rebuttal(self, concept: str, phase1_context: str, transcript: str) -> str:
        msg = _SKEPTIC_R3_USER.format(
            concept=concept, phase1_context=phase1_context, transcript=transcript,
        )
        return self._call(_SKEPTIC_SYSTEM, [{"role": "user", "content": msg}])

    def stream_final_rebuttal(self, concept: str, phase1_context: str, transcript: str) -> Generator[str, None, None]:
        msg = _SKEPTIC_R3_USER.format(
            concept=concept, phase1_context=phase1_context, transcript=transcript,
        )
        yield from self._stream(_SKEPTIC_SYSTEM, [{"role": "user", "content": msg}])


# ---------------------------------------------------------------------------
# Liberal Construction / Defence Agent
# ---------------------------------------------------------------------------

_DEFENCE_SYSTEM = f"""\
You are lead regulatory counsel for a Formula 1 constructor defending a design \
concept before the stewards. Your mandate is to build the strongest possible case \
that the concept is legal, consistent with engineering freedom, supported by \
precedent, and entirely within the rules as written and as applied in practice.

{_LABEL_RULE}"""

_DEFENCE_R1_USER = """\
CONCEPT:
{concept}

{phase1_context}

Build your opening defence of this concept. Identify the strongest basis for \
legality and press it. What is the best case that this is permitted, and that \
restricting it would be an overreach?"""

_DEFENCE_R2_USER = """\
CONCEPT:
{concept}

{phase1_context}

YOUR ROUND 1 ARGUMENT:
{own_r1}

OPPONENT'S ROUND 1 ARGUMENT (FIA Skeptic / Prosecutor):
{opponent_r1}

The Prosecutor has now made its opening case. Your job is to respond directly to \
the weakest points in that argument — the overreaches, the mischaracterisations, \
the strained readings of the rules. Do not repeat your Round 1 verbatim; advance \
the defence by engaging with what the Prosecutor actually said."""

_DEFENCE_R3_USER = """\
CONCEPT:
{concept}

{phase1_context}

FULL DEBATE SO FAR:
{transcript}

This is the final rebuttal round. Make your most precise and decisive point — the \
single strongest argument for legality that the Prosecutor has not adequately \
answered. Be surgical."""


class LiberalConstructionAgent(BaseAgent):

    def argue(self, concept: str, phase1_context: str) -> str:
        msg = _DEFENCE_R1_USER.format(concept=concept, phase1_context=phase1_context)
        return self._call(_DEFENCE_SYSTEM, [{"role": "user", "content": msg}])

    def stream_argue(self, concept: str, phase1_context: str) -> Generator[str, None, None]:
        msg = _DEFENCE_R1_USER.format(concept=concept, phase1_context=phase1_context)
        yield from self._stream(_DEFENCE_SYSTEM, [{"role": "user", "content": msg}])

    def rebut(self, concept: str, phase1_context: str, own_r1: str, opponent_r1: str) -> str:
        msg = _DEFENCE_R2_USER.format(
            concept=concept, phase1_context=phase1_context,
            own_r1=own_r1, opponent_r1=opponent_r1,
        )
        return self._call(_DEFENCE_SYSTEM, [{"role": "user", "content": msg}])

    def stream_rebut(self, concept: str, phase1_context: str, own_r1: str, opponent_r1: str) -> Generator[str, None, None]:
        msg = _DEFENCE_R2_USER.format(
            concept=concept, phase1_context=phase1_context,
            own_r1=own_r1, opponent_r1=opponent_r1,
        )
        yield from self._stream(_DEFENCE_SYSTEM, [{"role": "user", "content": msg}])

    def final_rebuttal(self, concept: str, phase1_context: str, transcript: str) -> str:
        msg = _DEFENCE_R3_USER.format(
            concept=concept, phase1_context=phase1_context, transcript=transcript,
        )
        return self._call(_DEFENCE_SYSTEM, [{"role": "user", "content": msg}])

    def stream_final_rebuttal(self, concept: str, phase1_context: str, transcript: str) -> Generator[str, None, None]:
        msg = _DEFENCE_R3_USER.format(
            concept=concept, phase1_context=phase1_context, transcript=transcript,
        )
        yield from self._stream(_DEFENCE_SYSTEM, [{"role": "user", "content": msg}])
