"""Phase 1 — Regulatory Text Agent and Precedent Agent (run in parallel).

Retrieval: each regulatory_query from the ConceptDecomposition is sent to the
FIARulerPro /retrieve HTTP endpoint.  Hits arrive pre-deduplicated, sorted, and
trimmed; document titles are resolved server-side.

Synthesis: the Regulatory Text Agent and Precedent Agent are called in
parallel via ThreadPoolExecutor.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

import httpx

from f1reg.config import get_fiaruler_api_key, get_fiaruler_api_url, settings
from f1reg.context import MemoContext

_MAX_UNIT_CHARS = 2000


def _retrieve_via_api(
    concept,
    *,
    regulation_limit: int,
    precedent_limit: int,
) -> tuple[list[dict], list[dict]]:
    """Call the FIARulerPro /retrieve endpoint and return (reg_hits, prec_hits).

    Hits are dicts matching the RetrieveHit schema:
      regulatory_unit_id, document_id, document_title, authority_level,
      authority_score, rrf_score, identifier, title, content
    """
    api_url = get_fiaruler_api_url().rstrip("/")
    api_key = get_fiaruler_api_key()

    payload = {
        "queries": concept.regulatory_queries,
        "season": concept.season,
        "regulation_limit": regulation_limit,
        "precedent_limit": precedent_limit,
        "graph_hops": 1,
    }
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    try:
        resp = httpx.post(
            f"{api_url}/retrieve",
            json=payload,
            headers=headers,
            timeout=180.0,
        )
    except httpx.ConnectError as exc:
        raise RuntimeError(
            f"Cannot reach FIARulerPro at {api_url}. "
            "Check F1REG_FIARULER_API_URL / secrets.toml."
        ) from exc
    except httpx.TimeoutException as exc:
        raise RuntimeError(
            f"FIARulerPro /retrieve timed out after 180 s ({api_url})."
        ) from exc

    if resp.status_code == 401:
        raise RuntimeError(
            "FIARulerPro returned 401 Unauthorized. "
            "Check F1REG_FIARULER_API_KEY / secrets.toml."
        )
    if resp.status_code != 200:
        raise RuntimeError(
            f"FIARulerPro /retrieve returned HTTP {resp.status_code}: {resp.text[:200]}"
        )

    data = resp.json()
    return data["regulation_hits"], data["precedent_hits"]


def _fmt_reg_hit(h: dict) -> str:
    doc_title = h.get("document_title") or f"Document {h['document_id']}"
    auth = (h.get("authority_level") or "").replace("FIA_", "").replace("_", " ").title()
    ident = h.get("identifier") or ""
    art_title = h.get("title") or ""
    header = f"[{doc_title} | {auth}]"
    if ident or art_title:
        header += f"  {ident}" + (f" — {art_title}" if art_title else "")
    raw = (h.get("content") or "").strip()
    title_text = art_title.strip()
    content = (title_text + "\n" + raw).strip() if len(raw) >= 40 and title_text else (raw or title_text)
    if len(content) > _MAX_UNIT_CHARS:
        content = content[:_MAX_UNIT_CHARS] + "... [truncated]"
    return header + ("\n" + content if content else "")


def _fmt_prec_hit(h: dict) -> str:
    doc_title = h.get("document_title") or f"Document {h['document_id']}"
    section = h.get("identifier") or h.get("title") or "(section)"
    header = f"[{doc_title} — {section}]"
    content = (h.get("content") or "").strip()
    if len(content) > _MAX_UNIT_CHARS:
        content = content[:_MAX_UNIT_CHARS] + "... [truncated]"
    return header + ("\n" + content if content else "")


def _build_regulation_text(reg_hits: list[dict]) -> str:
    if not reg_hits:
        return "APPLICABLE REGULATIONS\n" + "=" * 40 + "\n(No regulation articles retrieved.)"
    lines = ["APPLICABLE REGULATIONS", "=" * 40]
    for h in reg_hits:
        lines.append(_fmt_reg_hit(h))
        lines.append("")
    return "\n".join(lines)


def _build_precedent_text(prec_hits: list[dict]) -> str:
    if not prec_hits:
        return "STEWARDS PRECEDENTS\n" + "=" * 40 + "\n(No precedent decisions retrieved.)"
    lines = ["STEWARDS PRECEDENTS", "=" * 40]
    for h in prec_hits:
        lines.append(_fmt_prec_hit(h))
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

    rl = settings.regulation_limit
    pl = settings.precedent_limit

    # ------------------------------------------------------------------
    # Step 1: retrieval via HTTP API
    # ------------------------------------------------------------------
    if progress_callback:
        progress_callback("Retrieving regulations and precedents from FIARulerPro...")

    reg_hits, prec_hits = _retrieve_via_api(
        ctx.concept, regulation_limit=rl, precedent_limit=pl
    )

    # Expansion hits (rrf_score=0.0) bypass the regulation_limit cap on the
    # FIARulerPro side. With 5-6 queries and active graph expansion the total
    # can reach 50-60 articles, which is too much for agent synthesis.
    # Cap to 15 total: scored hits keep their ranked order; expansion hits are
    # sorted by authority and trimmed to fill the remainder.
    _MAX_REG_HITS = 15
    if len(reg_hits) > _MAX_REG_HITS:
        scored = [h for h in reg_hits if h.get("rrf_score", 0) > 0]
        expansion = sorted(
            [h for h in reg_hits if h.get("rrf_score", 0) == 0],
            key=lambda h: -h.get("authority_score", 0),
        )
        reg_hits = (scored + expansion)[:_MAX_REG_HITS]

    ctx.regulation_hits = reg_hits
    ctx.precedent_hits = prec_hits
    regulation_text = _build_regulation_text(reg_hits)
    precedent_text = _build_precedent_text(prec_hits)

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
