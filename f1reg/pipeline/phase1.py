"""Phase 1 — Regulatory Text Agent and Precedent Agent (run in parallel).

Retrieval: each regulatory_query from the ConceptDecomposition is run through
the FIARulerPro substrate.  Hits are deduplicated by regulatory_unit_id
(keeping the highest rrf_score), then sorted by (authority_score DESC,
rrf_score DESC) and trimmed to the configured limits.

Synthesis: the Regulatory Text Agent and Precedent Agent are called in
parallel via ThreadPoolExecutor.
"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

from f1reg.config import get_fiaruler_db_url, settings
from f1reg.context import MemoContext

_MAX_UNIT_CHARS = 2000

# Lock for one-time substrate engine initialisation
_engine_lock = threading.Lock()


def _init_substrate_engine():
    """Ensure the substrate global engine points at the configured DB URL.

    retrieve_precedents() creates its own sessions via get_engine(), so we
    must set the module-level _engine before any retrieval call.  This is
    idempotent — subsequent calls are no-ops once the engine is set.
    """
    import substrate.storage.database as _db_mod
    if _db_mod._engine is not None:
        return _db_mod._engine
    with _engine_lock:
        if _db_mod._engine is not None:
            return _db_mod._engine
        from substrate.storage.database import build_engine, init_db
        url = get_fiaruler_db_url()
        engine = build_engine(url)
        init_db(engine)
        _db_mod._engine = engine
        return engine


def _retrieve_all_queries(
    concept,
    session,
    *,
    regulation_limit: int,
    precedent_limit: int,
) -> tuple[list, list]:
    """Run each regulatory_query through retrieve_precedents and merge hits.

    Deduplicates by regulatory_unit_id, keeping the hit with the highest
    rrf_score per unit.  Final lists are sorted (authority DESC, rrf DESC)
    and trimmed to the configured limits.
    """
    from substrate.retrieval.retriever import retrieve_precedents

    reg_by_id: dict[int, object] = {}
    prec_by_id: dict[int, object] = {}

    for query in concept.regulatory_queries:
        result = retrieve_precedents(
            query,
            session,
            season=concept.season,
            regulation_limit=regulation_limit,
            precedent_limit=precedent_limit,
            graph_hops=1,
        )
        for h in result.regulation_hits:
            uid = h.regulatory_unit_id
            if uid not in reg_by_id or h.rrf_score > reg_by_id[uid].rrf_score:
                reg_by_id[uid] = h
        for h in result.precedent_hits:
            uid = h.regulatory_unit_id
            if uid not in prec_by_id or h.rrf_score > prec_by_id[uid].rrf_score:
                prec_by_id[uid] = h

    reg_hits = sorted(
        reg_by_id.values(), key=lambda h: (-h.authority_score, -h.rrf_score)
    )[:regulation_limit]
    prec_hits = sorted(
        prec_by_id.values(), key=lambda h: (-h.authority_score, -h.rrf_score)
    )[:precedent_limit]
    return reg_hits, prec_hits


def _fmt_reg_hit(h, session) -> str:
    from substrate.models import Document
    doc = session.get(Document, h.document_id)
    doc_title = doc.title if doc else f"Document {h.document_id}"
    auth = (h.authority_level or "").replace("FIA_", "").replace("_", " ").title()
    ident = h.identifier or ""
    art_title = h.title or ""
    header = f"[{doc_title} | {auth}]"
    if ident or art_title:
        header += f"  {ident}" + (f" — {art_title}" if art_title else "")
    raw = (h.content or "").strip()
    title_text = (h.title or "").strip()
    content = (title_text + "\n" + raw).strip() if len(raw) >= 40 and title_text else (raw or title_text)
    if len(content) > _MAX_UNIT_CHARS:
        content = content[:_MAX_UNIT_CHARS] + "... [truncated]"
    return header + ("\n" + content if content else "")


def _fmt_prec_hit(h, session) -> str:
    from substrate.models import Document
    doc = session.get(Document, h.document_id)
    doc_title = doc.title if doc else f"Document {h.document_id}"
    section = h.identifier or h.title or "(section)"
    header = f"[{doc_title} — {section}]"
    content = (h.content or "").strip()
    if len(content) > _MAX_UNIT_CHARS:
        content = content[:_MAX_UNIT_CHARS] + "... [truncated]"
    return header + ("\n" + content if content else "")


def _build_regulation_text(reg_hits, session) -> str:
    if not reg_hits:
        return "APPLICABLE REGULATIONS\n" + "=" * 40 + "\n(No regulation articles retrieved.)"
    lines = ["APPLICABLE REGULATIONS", "=" * 40]
    for h in reg_hits:
        lines.append(_fmt_reg_hit(h, session))
        lines.append("")
    return "\n".join(lines)


def _build_precedent_text(prec_hits, session) -> str:
    if not prec_hits:
        return "STEWARDS PRECEDENTS\n" + "=" * 40 + "\n(No precedent decisions retrieved.)"
    lines = ["STEWARDS PRECEDENTS", "=" * 40]
    for h in prec_hits:
        lines.append(_fmt_prec_hit(h, session))
        lines.append("")
    return "\n".join(lines)


def run_phase1(
    ctx: MemoContext,
    *,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> MemoContext:
    """Run Phase 1: retrieval + parallel Regulatory Text and Precedent agents.

    progress_callback receives a human-readable status message at each step.
    """
    from f1reg.agents.regulatory_text import RegulatoryTextAgent
    from f1reg.agents.precedent import PrecedentAgent
    from substrate.storage.database import make_session

    rl = settings.regulation_limit
    pl = settings.precedent_limit

    # ------------------------------------------------------------------
    # Step 1: retrieval
    # ------------------------------------------------------------------
    if progress_callback:
        progress_callback("Retrieving regulations and precedents from FIARulerPro...")

    engine = _init_substrate_engine()
    session = make_session(engine)
    try:
        reg_hits, prec_hits = _retrieve_all_queries(
            ctx.concept, session, regulation_limit=rl, precedent_limit=pl
        )
        ctx.regulation_hits = reg_hits
        ctx.precedent_hits = prec_hits
        regulation_text = _build_regulation_text(reg_hits, session)
        precedent_text = _build_precedent_text(prec_hits, session)
    finally:
        session.close()

    # ------------------------------------------------------------------
    # Step 2: parallel agent synthesis
    # ------------------------------------------------------------------
    if progress_callback:
        n_reg = len(reg_hits)
        n_prec = len(prec_hits)
        progress_callback(
            f"Retrieved {n_reg} regulation article(s) and {n_prec} precedent decision(s). "
            "Running Regulatory Text Agent and Precedent Agent in parallel..."
        )

    concept_summary = ctx.concept.summary

    def _run_reg():
        return RegulatoryTextAgent().analyse(concept_summary, regulation_text)

    def _run_prec():
        return PrecedentAgent().analyse(concept_summary, precedent_text)

    with ThreadPoolExecutor(max_workers=2) as pool:
        reg_future = pool.submit(_run_reg)
        prec_future = pool.submit(_run_prec)
        reg_output = reg_future.result()
        prec_output = prec_future.result()

    ctx.regulatory_text_output = reg_output
    ctx.precedent_output = prec_output
    ctx.regulatory_summary = reg_output.summary
    ctx.precedent_summary = prec_output.summary

    if progress_callback:
        progress_callback("Phase 1 complete.")

    return ctx
