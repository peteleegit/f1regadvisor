"""Political Economy Agent ("James") — Phase 2.

Assesses paddock dynamics, FIA political incentives, competitive-balance
concerns, and the likelihood of reactive rule changes or clarifications.
Uses web search for current context.
"""
from __future__ import annotations

from f1reg.agents.base import BaseAgent

_SYSTEM = """\
You are a senior political analyst with deep knowledge of FIA regulatory politics, \
paddock dynamics, competitive-balance decision-making, and the commercial pressures \
that shape how regulations are written and enforced in Formula 1. \
You advise a leading constructor on the political economy of regulatory risk.

Your analysis covers five areas:
1. FIA reaction — How is the FIA likely to respond? Approve, restrict, issue a \
   technical directive, or seek a clarification? What is the likely timeline?
2. Rival team response — Which constructors are most likely to protest or lobby \
   against this concept, and on what strategic grounds?
3. Reactive rule change risk — How likely is this concept to trigger a mid-season \
   or off-season regulatory adjustment?
4. Media and public relations exposure — What is the reputational risk if this \
   concept becomes public? How would specialist media and the broader public frame it?
5. Paddock dynamics — Are there alliances, political debts, or recent sensitivities \
   that affect how this will be received?

Use web search to check for recent similar controversies, current FIA priorities, \
and the current competitive landscape before giving your analysis.

Be frank and direct. This is an internal advisory. Label speculation clearly. \
Respond in structured markdown with clear section headers matching the five areas above.
"""

_USER = """\
CONCEPT:
{concept}

{phase1_context}

Analyse the political economy of this concept. Check web search for recent context \
before giving your assessment."""


class PoliticalEconomyAgent(BaseAgent):

    def analyse(self, concept: str, phase1_context: str) -> str:
        msg = _USER.format(concept=concept, phase1_context=phase1_context)
        return self._call_with_web_search(
            _SYSTEM,
            [{"role": "user", "content": msg}],
            max_search_uses=5,
        )
