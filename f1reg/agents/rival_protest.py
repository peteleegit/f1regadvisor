"""Rival Protest Agent — Phase 2.5.

Simulates how a rival constructor's legal team would challenge this concept
through the FIA protest and right-of-review process.  Sees the full debate
transcript from Phase 2 before producing its output.  Uses web search.
"""
from __future__ import annotations

from f1reg.agents.base import BaseAgent

_SYSTEM = """\
You are simulating the legal counsel of a rival Formula 1 constructor who has \
become aware of the described concept and is war-gaming whether and how to \
challenge it through FIA processes.

Your job is to produce a realistic adversarial simulation covering:
1. Protest grounds — On which specific rules would they base a protest? \
   Which arguments from the Skeptic's debate analysis would they cite?
2. Technical framing — How would they characterise the concept technically \
   to make it sound most objectionable to the stewards?
3. Documentary strategy — What documentation would they demand in discovery? \
   What would they present as evidence?
4. Realistic prospects — What is the honest probability this challenge succeeds \
   at stewards level? On appeal? Why?
5. Media and political narrative — What story would they tell in public to build \
   pressure regardless of the legal outcome?
6. Strategic objective — Is this about actually winning the protest, forcing a \
   clarification, setting a precedent, or something else? What is the timeline?

Use web search to check for recent similar challenges, relevant stewards \
precedents, and the current posture of rival teams.

Be adversarial, specific, and realistic. Treat this as a war-gaming exercise, \
not a balanced analysis. Respond in structured markdown with clear section headers.
"""

_USER = """\
CONCEPT:
{concept}

{phase1_context}

DEBATE TRANSCRIPT (FIA Skeptic vs. Liberal Construction, all rounds):
{transcript}

Simulate how a rival team's legal counsel would mount a challenge to this concept. \
Check web search for recent relevant context first."""


class RivalProtestAgent(BaseAgent):

    def analyse(self, concept: str, phase1_context: str, transcript: str) -> str:
        msg = _USER.format(
            concept=concept,
            phase1_context=phase1_context,
            transcript=transcript,
        )
        return self._call_with_web_search(
            _SYSTEM,
            [{"role": "user", "content": msg}],
            max_search_uses=5,
        )
