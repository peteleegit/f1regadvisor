"""Pipeline orchestrator — phases 1-5.

Stub implementation. Phase 0 (Technical Concept Agent) is complete and
wired into app.py. This module will grow as each phase is implemented.
"""
from __future__ import annotations

from typing import Callable, Optional

from f1reg.context import MemoContext


class Orchestrator:
    """Runs phases 1-5 of the assessment pipeline.

    Progress is reported via an optional callback:
        progress_callback(phase: str, message: str)
    """

    def run(
        self,
        ctx: MemoContext,
        *,
        progress_callback: Optional[Callable[[str, str], None]] = None,
    ) -> MemoContext:
        raise NotImplementedError(
            "Pipeline phases 1-5 are not yet implemented. "
            "Phase 0 (Technical Concept Agent) is complete."
        )
