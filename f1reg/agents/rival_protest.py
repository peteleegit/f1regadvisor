"""Rival Protest Agent — Phase 2.5.

Simulates how a rival constructor's legal team would challenge this concept
through the FIA protest and right-of-review process.  Sees the full debate
transcript from Phase 2 before producing its output.  Uses web search.
"""
from __future__ import annotations

import re

from f1reg.agents.base import BaseAgent

_SYSTEM = """\
You are simulating the legal counsel of a rival Formula 1 constructor who has \
become aware of the described concept and is war-gaming whether and how to \
challenge it through FIA processes.

Your job is to produce a realistic adversarial simulation. Use web search to \
check for recent similar challenges, relevant stewards precedents, and the \
current posture of rival teams.

Be adversarial, specific, and realistic. Treat this as a war-gaming exercise, \
not a balanced analysis.

Respond using EXACTLY these six section headings in this order — no other \
top-level headings, no preamble, no commentary about what web searches returned:

## 1. Protest Grounds
## 2. Technical Framing
## 3. Documentary Strategy
## 4. Realistic Prospects
## 5. Media and Political Narrative
## 6. Strategic Objective

Start your response with "## 1. Protest Grounds" and nothing before it.
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

    def analyse(
        self,
        concept: str,
        phase1_context: str,
        transcript: str,
        progress_callback=None,
    ) -> str:
        msg = _USER.format(
            concept=concept,
            phase1_context=phase1_context,
            transcript=transcript,
        )
        result = self._call_with_web_search(
            _SYSTEM,
            [{"role": "user", "content": msg}],
            max_search_uses=5,
            progress_callback=progress_callback,
        )
        # Strip anything before the first expected section heading.
        # We anchor on "## 1." which is the first mandated heading; this
        # survives web-search result text that may contain other headings.
        m = re.search(r"^##\s+1\.", result, re.MULTILINE)
        if not m:
            # Fallback: strip before the first ## heading of any kind
            m = re.search(r"^##\s", result, re.MULTILINE)
        if m:
            result = result[m.start():]
        return result
