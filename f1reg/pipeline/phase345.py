"""Phases 3, 4, and 5 — strategy, audit, and final memo synthesis.

These three phases run sequentially: each depends on the previous.

  Phase 3 — Procedural Strategy Agent
  Phase 4 — Evidence Auditor (claude-opus-4-7)
  Phase 5 — Bottom Line Synthesis (claude-opus-4-7) + memo assembly
"""
from __future__ import annotations

from typing import Callable, Optional

from f1reg.context import MemoContext
from f1reg.pipeline.phase2 import build_phase1_context


def run_phase345(
    ctx: MemoContext,
    *,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> MemoContext:
    """Run Phases 3–5 and assemble the final memo into ctx.memo_markdown."""
    from f1reg.agents.procedural_strategy import ProceduralStrategyAgent
    from f1reg.agents.evidence_auditor import EvidenceAuditorAgent
    from f1reg.agents.bottom_line import BottomLineAgent
    from f1reg.memo.renderer import build_memo_markdown

    phase1_ctx = build_phase1_context(ctx)

    # ------------------------------------------------------------------
    # Phase 3: Procedural Strategy
    # ------------------------------------------------------------------
    if progress_callback:
        progress_callback("Phase 3: Developing mitigation strategy and recommended action...")

    ph3 = ProceduralStrategyAgent().analyse(ctx, phase1_ctx)
    ctx.recommended_action = ph3.recommended_action
    ctx.recommended_action_rationale = ph3.recommended_action_rationale
    ctx.mitigations = "\n".join(f"- {m}" for m in ph3.mitigations)

    # ------------------------------------------------------------------
    # Phase 4: Evidence Audit
    # ------------------------------------------------------------------
    if progress_callback:
        progress_callback("Phase 4: Evidence Auditor reviewing all outputs for quality issues...")

    ctx.audit_findings = EvidenceAuditorAgent().audit(ctx)

    # ------------------------------------------------------------------
    # Phase 5: Bottom Line Synthesis
    # ------------------------------------------------------------------
    if progress_callback:
        progress_callback("Phase 5: Synthesising bottom line verdict and assembling memo...")

    ph5 = BottomLineAgent().synthesise(ctx)
    ctx.legal_standing = ph5.legal_standing
    ctx.enforcement_risk = ph5.enforcement_risk
    ctx.fia_predictability = ph5.fia_predictability
    ctx.bottom_line_summary = ph5.bottom_line_summary
    ctx.political_risk_summary = ph5.political_risk_summary
    ctx.arguments_for = "\n".join(f"- {a}" for a in ph5.arguments_for)
    ctx.arguments_against = "\n".join(f"- {a}" for a in ph5.arguments_against)
    ctx.open_questions = "\n".join(f"- {q}" for q in ph5.open_questions)

    # ------------------------------------------------------------------
    # Assemble final memo
    # ------------------------------------------------------------------
    ctx.memo_markdown = build_memo_markdown(ctx)

    return ctx
