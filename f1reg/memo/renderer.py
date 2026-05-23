"""Assembles MemoContext into final Markdown memo.

Structure is optimised for busy readers — verdict and action at the top,
full analysis in an appendix at the bottom.
"""
from __future__ import annotations

import datetime

from f1reg.context import MemoContext


def build_memo_markdown(ctx: MemoContext) -> str:
    concept = ctx.concept
    date_str = datetime.date.today().strftime("%d %B %Y").lstrip("0")

    sections: list[str] = []

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    sections.append(
        f"# F1 Regulatory Risk Memo\n\n"
        f"**Concept:** {concept.summary}  \n"
        f"**Season:** {concept.season}  \n"
        f"**Assessed:** {date_str}"
    )

    sections.append("---")

    # ------------------------------------------------------------------
    # Bottom line — two-track verdict leads the document
    # ------------------------------------------------------------------
    legal = ctx.legal_standing or "ASSESSMENT INCOMPLETE"
    enforcement = ctx.enforcement_risk or "ASSESSMENT INCOMPLETE"
    predictability = ctx.fia_predictability or "ASSESSMENT INCOMPLETE"

    bl_table = (
        "| | |\n"
        "|---|---|\n"
        f"| **Legal standing** | {legal} |\n"
        f"| **Enforcement risk** | {enforcement} |\n"
        f"| **FIA predictability** | {predictability} |"
    )
    bl_body = ctx.bottom_line_summary or ""
    sections.append(f"## Bottom Line\n\n{bl_table}\n\n{bl_body}")

    # ------------------------------------------------------------------
    # Recommended action
    # ------------------------------------------------------------------
    action = ctx.recommended_action or "(not assessed)"
    rationale = ctx.recommended_action_rationale or ""
    action_body = f"**{action}.**" + (f"  {rationale}" if rationale else "")
    sections.append(f"## Recommended Action\n\n{action_body}")

    sections.append("---")

    # ------------------------------------------------------------------
    # FIA Reality Assessment — elevated above advocacy arguments.
    # Draws from structured outputs of Phase 1 agents.
    # ------------------------------------------------------------------
    reality_parts: list[str] = []

    po = ctx.precedent_output
    if po and po.consistency_rating:
        consistency_line = f"**Precedent consistency:** {po.consistency_rating}"
        if po.trend_direction and po.trend_direction != "UNCLEAR":
            consistency_line += f" — trend: {po.trend_direction}"
        reality_parts.append(consistency_line)
        if po.consistency_analysis:
            reality_parts.append(po.consistency_analysis)

    rto = ctx.regulatory_text_output
    if rto and rto.ambiguities:
        reality_parts.append("**Regulatory ambiguities — classified by likely FIA intent:**")
        for a in rto.ambiguities:
            reality_parts.append(f"- {a}")

    if reality_parts:
        sections.append("## FIA Reality Assessment\n\n" + "\n\n".join(reality_parts))

    # ------------------------------------------------------------------
    # Arguments — concise bullet lists
    # ------------------------------------------------------------------
    if ctx.arguments_for:
        sections.append(f"## Arguments For Legality\n\n*[Advocacy — not factual synthesis]*\n\n{ctx.arguments_for}")

    if ctx.arguments_against:
        sections.append(f"## Arguments Against / Key Risks\n\n*[Advocacy — not factual synthesis]*\n\n{ctx.arguments_against}")

    # ------------------------------------------------------------------
    # Political and protest risk
    # ------------------------------------------------------------------
    pol_risk = ctx.political_risk_summary or ""
    if pol_risk:
        sections.append(f"## Political and Protest Risk\n\n{pol_risk}")

    # ------------------------------------------------------------------
    # Mitigations
    # ------------------------------------------------------------------
    if ctx.mitigations:
        sections.append(f"## Mitigations\n\n{ctx.mitigations}")

    # ------------------------------------------------------------------
    # Open questions
    # ------------------------------------------------------------------
    oq_parts: list[str] = []
    if ctx.open_questions:
        oq_parts.append(ctx.open_questions)

    low_findings = [f for f in ctx.audit_findings if f.severity == "LOW"]
    if low_findings:
        for f in low_findings:
            oq_parts.append(f"- *[Audit flag — {f.implicated_agent}]* {f.issue} {f.recommendation}")

    if oq_parts:
        sections.append("## Open Questions\n\n" + "\n\n".join(oq_parts))

    # ------------------------------------------------------------------
    # HIGH severity audit flags — prominent warning
    # ------------------------------------------------------------------
    high_findings = [f for f in ctx.audit_findings if f.severity == "HIGH"]
    if high_findings:
        flag_lines = ["> **⚠ AUDIT FLAGS — review before acting**\n>"]
        for f in high_findings:
            flag_lines.append(f"> **{f.implicated_agent}:** {f.issue}  \n> *Recommendation: {f.recommendation}*")
        sections.append("\n>\n".join(flag_lines))

    # ------------------------------------------------------------------
    # Disclaimer
    # ------------------------------------------------------------------
    sections.append(
        "---\n\n"
        "*This memo is AI-generated by F1RegAdvisor. All conclusions must be verified "
        "by qualified regulatory counsel before any regulatory decision is made. "
        "Legal standing reflects what the rules say; enforcement risk reflects political "
        "and institutional factors that may diverge from a strict textual reading.*"
    )

    # ------------------------------------------------------------------
    # Appendix — full analysis
    # ------------------------------------------------------------------
    appendix: list[str] = ["---\n\n## Appendix — Full Analysis"]

    if ctx.regulatory_summary:
        reg_detail = ctx.regulatory_summary
        if rto and rto.controlling_articles:
            reg_detail += "\n\n**Controlling articles:**\n" + "\n".join(f"- {a}" for a in rto.controlling_articles)
        if rto and rto.gaps:
            reg_detail += "\n\n**Regulatory gaps:**\n" + "\n".join(f"- {g}" for g in rto.gaps)
        appendix.append(f"### Regulatory Analysis\n\n{reg_detail}")

    if ctx.precedent_summary:
        prec_detail = ctx.precedent_summary
        if po and po.comparable_cases:
            prec_detail += "\n\n**Comparable cases:**\n" + "\n".join(f"- {c}" for c in po.comparable_cases)
        appendix.append(f"### Precedent Analysis\n\n{prec_detail}")

    if ctx.political_economy_analysis:
        appendix.append(f"### Political Economy (Full)\n\n{ctx.political_economy_analysis}")

    if ctx.rival_protest_analysis:
        appendix.append(f"### Rival Protest Simulation\n\n{ctx.rival_protest_analysis}")

    transcript = ctx.debate_transcript()
    if transcript:
        appendix.append(f"### Debate Transcript\n\n{transcript}")

    sections.extend(appendix)

    return "\n\n".join(sections)
