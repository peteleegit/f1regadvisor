"""Phase 2 — Adversarial debate chain + Phase 2.5 Rival Protest.

Execution order:
  Round 1  — FIA Skeptic + Liberal Construction (parallel)
  Round 2  — Skeptic rebut + Defence rebut + Political Economy (parallel)
  Round 3  — Optional final rebuttal (orchestrator decides via LLM)
  Phase 2.5 — Rival Protest Agent (sees full transcript)
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

from f1reg.context import DebateRound, MemoContext
from f1reg.config import settings


# ---------------------------------------------------------------------------
# Phase 1 context builder — feeds into every debate prompt
# ---------------------------------------------------------------------------

def build_phase1_context(ctx: MemoContext) -> str:
    """Assemble Phase 1 outputs into a compact context string for debate agents."""
    lines: list[str] = ["## REGULATORY CONTEXT (Phase 1 Analysis)", ""]

    if ctx.regulatory_summary:
        lines.append("### What the rules say")
        lines.append(ctx.regulatory_summary)
        lines.append("")

    rto = ctx.regulatory_text_output
    if rto:
        if rto.controlling_articles:
            lines.append("**Controlling articles:**")
            for a in rto.controlling_articles:
                lines.append(f"- {a}")
            lines.append("")
        if rto.key_definitions:
            lines.append("**Key definitions:**")
            for d in rto.key_definitions:
                lines.append(f"- {d}")
            lines.append("")
        if rto.cross_references:
            lines.append("**Cross-references:**")
            for x in rto.cross_references:
                lines.append(f"- {x}")
            lines.append("")
        if rto.gaps:
            lines.append("**Regulatory gaps:**")
            for g in rto.gaps:
                lines.append(f"- {g}")
            lines.append("")

    if ctx.precedent_summary:
        lines.append("### How the rules have been enforced")
        lines.append(ctx.precedent_summary)
        lines.append("")

    po = ctx.precedent_output
    if po:
        if po.comparable_cases:
            lines.append("**Comparable cases:**")
            for c in po.comparable_cases:
                lines.append(f"- {c}")
            lines.append("")
        if po.analogous_cases:
            lines.append("**Analogous cases:**")
            for c in po.analogous_cases:
                lines.append(f"- {c}")
            lines.append("")
        if po.distinctions:
            lines.append("**Distinctions (why prior cases may not control):**")
            for d in po.distinctions:
                lines.append(f"- {d}")
            lines.append("")
        if po.gaps:
            lines.append("**Precedent gaps:**")
            for g in po.gaps:
                lines.append(f"- {g}")
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Round 3 oracle
# ---------------------------------------------------------------------------

def should_run_round3(ctx: MemoContext) -> bool:
    """Quick LLM call: does the debate have unresolved contention worth Round 3?"""
    if len(ctx.debate_rounds) < 2:
        return False
    r2 = ctx.debate_rounds[-1]
    # Truncate to keep the oracle call cheap
    sk = r2.skeptic_argument[:1200]
    df = r2.defense_argument[:1200]
    prompt = (
        f"FIA Skeptic Round 2:\n{sk}\n\n"
        f"Defence Round 2:\n{df}\n\n"
        "Does this debate contain a significant unresolved legal or factual dispute "
        "that a third rebuttal round would meaningfully resolve? "
        "Answer with exactly one word: yes or no."
    )
    from f1reg.agents.base import _get_client
    client = _get_client()
    resp = client.messages.create(
        model=settings.fast_model,
        max_tokens=5,
        system="You are a debate moderator. Answer only 'yes' or 'no'.",
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in resp.content if hasattr(b, "text")).strip().lower()
    return text.startswith("y")


# ---------------------------------------------------------------------------
# Main Phase 2 runner
# ---------------------------------------------------------------------------

def run_phase2(
    ctx: MemoContext,
    *,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> MemoContext:
    """Run Phase 2 (debate + political economy) and Phase 2.5 (rival protest)."""
    from f1reg.agents.debate import FIASkepticAgent, LiberalConstructionAgent
    from f1reg.agents.political_economy import PoliticalEconomyAgent
    from f1reg.agents.rival_protest import RivalProtestAgent

    phase1_ctx = build_phase1_context(ctx)
    concept = ctx.concept.summary

    skeptic = FIASkepticAgent()
    defence = LiberalConstructionAgent()

    # ------------------------------------------------------------------
    # Round 1: Skeptic and Defence argue simultaneously
    # ------------------------------------------------------------------
    if progress_callback:
        progress_callback("Round 1: FIA Skeptic and Defence arguing simultaneously...")

    with ThreadPoolExecutor(max_workers=2) as pool:
        sk_r1_f = pool.submit(skeptic.argue, concept, phase1_ctx)
        df_r1_f = pool.submit(defence.argue, concept, phase1_ctx)
        sk_r1 = sk_r1_f.result()
        df_r1 = df_r1_f.result()

    ctx.debate_rounds.append(DebateRound(
        round_number=1,
        skeptic_argument=sk_r1,
        defense_argument=df_r1,
    ))

    # ------------------------------------------------------------------
    # Round 2: each reads the other's Round 1; Political Economy runs in parallel
    # ------------------------------------------------------------------
    if progress_callback:
        progress_callback(
            "Round 2: Skeptic and Defence responding to each other; "
            "Political Economy analysis running in parallel..."
        )

    with ThreadPoolExecutor(max_workers=3) as pool:
        sk_r2_f = pool.submit(skeptic.rebut, concept, phase1_ctx, sk_r1, df_r1)
        df_r2_f = pool.submit(defence.rebut, concept, phase1_ctx, df_r1, sk_r1)
        pe_f = pool.submit(PoliticalEconomyAgent().analyse, concept, phase1_ctx)
        sk_r2 = sk_r2_f.result()
        df_r2 = df_r2_f.result()
        pe = pe_f.result()

    ctx.debate_rounds.append(DebateRound(
        round_number=2,
        skeptic_argument=sk_r2,
        defense_argument=df_r2,
    ))
    ctx.political_economy_analysis = pe

    # ------------------------------------------------------------------
    # Round 3: optional — orchestrator decides
    # ------------------------------------------------------------------
    if should_run_round3(ctx):
        if progress_callback:
            progress_callback("Round 3: Genuine unresolved contention detected — running final rebuttal...")

        transcript = ctx.debate_transcript()
        with ThreadPoolExecutor(max_workers=2) as pool:
            sk_r3_f = pool.submit(skeptic.final_rebuttal, concept, phase1_ctx, transcript)
            df_r3_f = pool.submit(defence.final_rebuttal, concept, phase1_ctx, transcript)
            sk_r3 = sk_r3_f.result()
            df_r3 = df_r3_f.result()

        ctx.debate_rounds.append(DebateRound(
            round_number=3,
            skeptic_argument=sk_r3,
            defense_argument=df_r3,
        ))

    # ------------------------------------------------------------------
    # Phase 2.5: Rival Protest Agent (sees full transcript)
    # ------------------------------------------------------------------
    if progress_callback:
        progress_callback("Phase 2.5: Considering rival team legal challenge...")

    transcript = ctx.debate_transcript()
    ctx.rival_protest_analysis = RivalProtestAgent().analyse(concept, phase1_ctx, transcript)

    if progress_callback:
        progress_callback("Phase 2 complete.")

    return ctx
