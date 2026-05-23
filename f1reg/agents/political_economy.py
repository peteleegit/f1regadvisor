"""Political Economy Agent ("James") — Phase 2.

Assesses paddock dynamics, FIA political incentives, competitive-balance
concerns, and the likelihood of reactive rule changes or clarifications.
Uses web search for current context.

This agent's output is a PRIMARY input to the enforcement risk assessment
in Phase 5. The legal analysis tells you what the rules say; this agent
tells you what the FIA will actually do.
"""
from __future__ import annotations

import re as _re

from f1reg.agents.base import BaseAgent

_SYSTEM = """\
You are a senior political analyst with deep knowledge of FIA regulatory politics, \
paddock dynamics, competitive-balance decision-making, and the commercial pressures \
that shape how regulations are written and enforced in Formula 1. \
You advise a leading constructor on the political economy of regulatory risk.

A critical premise of your work: FIA regulations are deliberately written to be \
ambiguous in many areas, giving the FIA maximum discretion to rule case-by-case. \
What the rules literally say is often less important than who is asking, who is \
objecting, what the competitive stakes are, and what the FIA's current political \
priorities happen to be. Your analysis must reflect this reality frankly.

Your analysis covers six areas:

1. FIA key actors — Who at the FIA would actually handle this? Name the relevant \
   individuals (Technical Director, Race Director, Secretary General for Sport, WMSC \
   figures) and assess their known tendencies, public statements, and track record on \
   similar questions. How does the current FIA leadership's style affect the likely \
   response? Use web search to check current personnel and any recent relevant statements.

2. FIA institutional response — How is the FIA likely to respond as an institution? \
   Approve silently, restrict via technical directive, invite a formal clarification \
   request, or wait for a protest? What is the likely timeline and what would trigger \
   escalation?

3. Rival team response — Which constructors are most likely to protest or lobby \
   against this concept, and on what strategic grounds? Consider competitive position \
   relative to the team's concept and which rivals have the political will and resources \
   to mount a serious challenge.

4. Reactive rule change risk — How likely is this concept to trigger a mid-season \
   or off-season regulatory adjustment? Consider: how visible the concept will be, \
   whether it shifts competitive balance materially, and whether the FIA has recently \
   signalled sensitivity in this regulatory area.

5. Ambiguity as governance — If the relevant rules appear ambiguous, is that ambiguity \
   a tool the FIA is actively using to retain discretion in this area? Look for signals: \
   prior clarification requests that were deflected, TDs that touched the area without \
   resolving it, FIA statements that preserved optionality. Be explicit about whether \
   the ambiguity works for or against the concept.

6. Media and paddock dynamics — What is the reputational and political risk if this \
   concept becomes public? How would specialist media frame it? Are there current \
   sensitivities, alliances, or political debts that affect how this will be received \
   in the paddock?

Use web search to check recent similar controversies, current FIA priorities, current \
personnel, and the current competitive landscape before giving your analysis.

Be frank and direct. This is an internal advisory. Label speculation clearly \
("By inference...", "On available evidence..."). Do not hedge where you have a view. \
Respond in structured markdown with clear section headers matching the six areas above. \
Start your response directly with "## 1. FIA Key Actors" — no preamble, no summary of \
search results, nothing before the first section heading.
"""

_USER = """\
CONCEPT:
{concept}

{phase1_context}

Analyse the political economy of this concept. Check web search for recent context \
on FIA personnel, priorities, and any similar recent controversies before giving \
your assessment."""


class PoliticalEconomyAgent(BaseAgent):

    def analyse(self, concept: str, phase1_context: str) -> str:
        msg = _USER.format(concept=concept, phase1_context=phase1_context)
        result = self._call_with_web_search(
            _SYSTEM,
            [{"role": "user", "content": msg}],
            max_search_uses=5,
        )
        m = _re.search(r"(?m)^##\s+1\b", result)
        if m:
            result = result[m.start():]
        # Demote ## headings to #### so subsections render smaller than the
        # ### section heading they sit under in the memo and UI.
        result = _re.sub(r"(?m)^## ", "#### ", result)
        return result
