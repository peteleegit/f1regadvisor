"""F1RegAdvisor — Regulatory Risk Memo System.

Run with:
    streamlit run app.py

Requires .streamlit/secrets.toml:
    [auth]
    password = "..."

    [anthropic]
    api_key = "sk-ant-..."

    [substrate]
    db_url = "sqlite:///C:/path/to/FIARulerPro/fiaruler.db"
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

# ---------------------------------------------------------------------------
# Page config — must be first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="F1RegAdvisor — Regulatory Risk Memo",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Auth gate
# ---------------------------------------------------------------------------
def _check_password() -> bool:
    if st.session_state.get("authenticated"):
        return True

    st.title("F1RegAdvisor")
    st.caption("Regulatory Risk Memo System — Internal Use Only")
    st.divider()

    with st.form("login"):
        pw = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")

    if submitted:
        try:
            expected = st.secrets["auth"]["password"]
        except Exception:
            expected = None
        if expected and pw == expected:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password.")

    return False


if not _check_password():
    st.stop()


# ---------------------------------------------------------------------------
# Lazy setup — after auth so cold start on login page is fast
# ---------------------------------------------------------------------------
from f1reg.config import configure_api_key  # noqa: E402
from f1reg.agents.technical_concept import TechnicalConceptAgent  # noqa: E402
from f1reg.context import MemoContext  # noqa: E402

configure_api_key()


@st.cache_resource(show_spinner=False)
def _get_tca() -> TechnicalConceptAgent:
    return TechnicalConceptAgent()


tca = _get_tca()


# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
_PHASE2_KEYS = (
    "ph2_r1_done", "ph2_r2_done",
    "ph2_r3_checked", "ph2_r3_needs", "ph2_r3_done",
    "ph2_protest_done",
)
_PHASE345_KEYS = ("phase345_done",)


def _reset() -> None:
    for key in ("phase", "ctx", "tca_messages", "display_messages",
                "uploaded_text", "question_count",
                "phase1_done", "phase2_done") + _PHASE2_KEYS + _PHASE345_KEYS:
        st.session_state.pop(key, None)


def _stream_into(gen, placeholder) -> str:
    """Consume a text-chunk generator, streaming into an st.empty() placeholder.

    Returns the full accumulated text.
    """
    text = ""
    for chunk in gen:
        text += chunk
        placeholder.markdown(text + " ▌")
    placeholder.markdown(text)
    return text


_ROUND_LABELS = {
    1: "Round 1: Opening Statements",
    2: "Round 2: Rebuttals",
    3: "Round 3: Closing Statements",
}


def _debate_columns(round_num: int):
    """Create two-column debate layout. Returns (sk_ph, col2).

    sk_ph is an st.empty() in col1 for streaming the Skeptic's text.
    col2 is the column context for the caller to use with st.spinner / st.markdown.
    """
    st.markdown(f"**{_ROUND_LABELS.get(round_num, f'Round {round_num}')}**")
    col1, col2 = st.columns(2)
    with col1:
        st.caption("FIA Skeptic / Prosecutor")
        sk_ph = st.empty()
    with col2:
        st.caption("Liberal Construction / Defence")
    return sk_ph, col2



if "phase" not in st.session_state:
    st.session_state.phase = "intake"          # "intake" | "running" | "complete"
if "tca_messages" not in st.session_state:
    st.session_state.tca_messages = []         # sent to the TCA API
if "display_messages" not in st.session_state:
    st.session_state.display_messages = []     # shown in the chat UI
if "question_count" not in st.session_state:
    st.session_state.question_count = 0
if "uploaded_text" not in st.session_state:
    st.session_state.uploaded_text = None


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("F1RegAdvisor")
    st.caption("Regulatory Risk Memo System")

    if st.button("New Assessment", use_container_width=True, type="primary"):
        _reset()
        st.rerun()

    st.divider()

    with st.expander("About"):
        st.markdown(
            """
**F1RegAdvisor** produces structured regulatory risk memos to help experts
assess whether a concept, design, or idea is likely permitted, prohibited,
ambiguous, or requires FIA clarification.

**How it works**

1. Describe your concept. The system may ask up to three follow-up
   questions to gather enough detail.
2. Nine specialist AI agents then analyse the concept in parallel and
   in sequence — covering applicable regulations, stewards precedents,
   legal arguments for and against, political and protest risk, and
   recommended mitigations.
3. The output is a structured memo with a bottom-line verdict, downloadable
   as PDF.

**This tool is for internal use only.** Outputs are AI-generated and must
be reviewed by a qualified expert before any regulatory decision is made.
            """
        )

    st.divider()
    if st.button("Sign out", use_container_width=True):
        st.session_state.clear()
        st.rerun()


# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------
st.title("F1 Regulatory Risk Assessment")
st.warning(
    "**INTERNAL USE ONLY — PROTOTYPE**  \n"
    "Outputs are AI-generated and may be incomplete or incorrect. "
    "Always verify with a qualified regulatory expert before acting on any conclusion."
)

# ---------------------------------------------------------------------------
# Phase: intake — Technical Concept Agent conversation
# ---------------------------------------------------------------------------
if st.session_state.phase == "intake":

    st.markdown(
        "Describe the concept, design, or idea you want assessed. "
        "The system will ask up to three follow-up questions before running the "
        "full analysis."
    )

    # File upload (shown only at the start of a new conversation)
    if not st.session_state.display_messages:
        uploaded = st.file_uploader(
            "Optional: upload a supporting document (PDF or text)",
            type=["pdf", "txt", "md"],
            label_visibility="visible",
        )
        if uploaded and st.session_state.uploaded_text is None:
            if uploaded.type == "application/pdf":
                try:
                    import pdfplumber
                    with pdfplumber.open(io.BytesIO(uploaded.read())) as pdf:
                        st.session_state.uploaded_text = "\n".join(
                            p.extract_text() or "" for p in pdf.pages
                        )
                except Exception as e:
                    st.warning(f"Could not read PDF: {e}")
            else:
                st.session_state.uploaded_text = uploaded.read().decode("utf-8", errors="replace")
            if st.session_state.uploaded_text:
                st.success(f"Document loaded: {uploaded.name}")

    # Display conversation history
    for msg in st.session_state.display_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    user_input = st.chat_input("Describe the concept...")
    if user_input:
        # Show user message immediately
        st.session_state.display_messages.append({"role": "user", "content": user_input})
        st.session_state.tca_messages.append({"role": "user", "content": user_input})

        with st.spinner("Thinking..."):
            response = tca.process(
                st.session_state.tca_messages,
                uploaded_text=st.session_state.uploaded_text,
            )

        if response.ready and response.decomposition:
            # Concept is fully understood — confirm and transition
            concept = response.decomposition
            confirm_msg = (
                f"Got it. Here's how I've understood the concept:\n\n"
                f"> {concept.summary}\n\n"
                f"**Season:** {concept.season}  \n"
                f"**Regulatory queries:** {', '.join(concept.regulatory_queries)}\n\n"
                f"Starting the full assessment now..."
            )
            st.session_state.display_messages.append(
                {"role": "assistant", "content": confirm_msg}
            )
            st.session_state.ctx = MemoContext(
                raw_input=user_input,
                uploaded_text=st.session_state.uploaded_text,
                concept=concept,
            )
            st.session_state.phase = "running"
            st.rerun()

        else:
            # Store the raw JSON as the assistant message for TCA context
            st.session_state.tca_messages.append(
                {"role": "assistant", "content": f'{{"ready": false, "question": "{response.question}"}}'}
            )
            # Show the display-friendly question in the chat
            st.session_state.display_messages.append(
                {"role": "assistant", "content": response.question_display}
            )
            st.session_state.question_count += 1
            st.rerun()


# ---------------------------------------------------------------------------
# Phase: running — Phase 1 execution and results display
# ---------------------------------------------------------------------------
elif st.session_state.phase == "running":
    ctx: MemoContext = st.session_state.ctx
    concept = ctx.concept

    st.subheader("Assessment in progress")
    st.markdown(f"> {concept.summary}")

    with st.expander("Concept intake conversation", expanded=False):
        for msg in st.session_state.display_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    st.divider()

    # ------------------------------------------------------------------
    # Run Phase 1 if not already done
    # ------------------------------------------------------------------
    if not st.session_state.get("phase1_done"):
        from f1reg.pipeline.phase1 import run_phase1

        with st.status("Running regulatory analysis...", expanded=True) as _status:
            def _progress(msg: str) -> None:
                st.write(msg)

            try:
                run_phase1(ctx, progress_callback=_progress)
                st.session_state.ctx = ctx
                st.session_state.phase1_done = True
                _status.update(label="Phase 1 complete", state="complete", expanded=False)
            except Exception as _err:
                _status.update(label=f"Phase 1 failed: {_err}", state="error")
                st.stop()

    # ------------------------------------------------------------------
    # Display Phase 1 results
    # ------------------------------------------------------------------
    if ctx.regulatory_summary:
        with st.expander("Regulatory Analysis", expanded=True):
            st.markdown(ctx.regulatory_summary)

            rto = ctx.regulatory_text_output
            if rto and rto.controlling_articles:
                st.markdown("**Controlling articles:**")
                for a in rto.controlling_articles:
                    st.markdown(f"- {a}")
            if rto and rto.key_definitions:
                st.markdown("**Key definitions:**")
                for d in rto.key_definitions:
                    st.markdown(f"- {d}")
            if rto and rto.gaps:
                st.markdown("**Regulatory gaps:**")
                for g in rto.gaps:
                    st.markdown(f"- {g}")

    if ctx.precedent_summary:
        with st.expander("Precedent Analysis", expanded=True):
            st.markdown(ctx.precedent_summary)

            po = ctx.precedent_output
            if po and po.comparable_cases:
                st.markdown("**Comparable cases:**")
                for c in po.comparable_cases:
                    st.markdown(f"- {c}")
            if po and po.analogous_cases:
                st.markdown("**Analogous cases:**")
                for c in po.analogous_cases:
                    st.markdown(f"- {c}")
            if po and po.gaps:
                st.markdown("**Precedent gaps:**")
                for g in po.gaps:
                    st.markdown(f"- {g}")

    # ------------------------------------------------------------------
    # Phase 2 — progressive streaming debate
    # ------------------------------------------------------------------
    if st.session_state.get("phase1_done"):
        from f1reg.pipeline.phase2 import build_phase1_context, should_run_round3
        from f1reg.agents.debate import FIASkepticAgent, LiberalConstructionAgent
        from f1reg.agents.political_economy import PoliticalEconomyAgent
        from f1reg.agents.rival_protest import RivalProtestAgent
        from f1reg.context import DebateRound
        from concurrent.futures import ThreadPoolExecutor

        st.subheader("Adversarial Debate")
        phase1_ctx = build_phase1_context(ctx)
        concept = ctx.concept.summary

        # ---- Round 1 ----
        sk1_ph, r1_col2 = _debate_columns(1)

        if not st.session_state.get("ph2_r1_done"):
            try:
                skeptic = FIASkepticAgent()
                defence = LiberalConstructionAgent()
                with r1_col2:
                    with st.spinner("Analysing..."):
                        with ThreadPoolExecutor(max_workers=1) as _pool:
                            _df_f = _pool.submit(defence.argue, concept, phase1_ctx)
                            _sk1 = _stream_into(skeptic.stream_argue(concept, phase1_ctx), sk1_ph)
                            _df1 = _df_f.result()
                    st.markdown(_df1)
                ctx.debate_rounds.append(DebateRound(1, _sk1, _df1))
                st.session_state.ctx = ctx
                st.session_state.ph2_r1_done = True
            except Exception as _err:
                st.error(f"Round 1 failed: {_err}")
                st.stop()
        else:
            _r = ctx.debate_rounds[0]
            sk1_ph.markdown(_r.skeptic_argument)
            with r1_col2:
                st.markdown(_r.defense_argument)

        st.divider()

        # ---- Round 2 + Political Economy ----
        if st.session_state.get("ph2_r1_done"):
            sk2_ph, r2_col2 = _debate_columns(2)

            if not st.session_state.get("ph2_r2_done"):
                pe_ph = st.empty()
                try:
                    _sk1 = ctx.debate_rounds[0].skeptic_argument
                    _df1 = ctx.debate_rounds[0].defense_argument
                    skeptic = FIASkepticAgent()
                    defence = LiberalConstructionAgent()
                    with r2_col2:
                        with st.spinner("Analysing..."):
                            with ThreadPoolExecutor(max_workers=2) as _pool:
                                _df2_f = _pool.submit(defence.rebut, concept, phase1_ctx, _df1, _sk1)
                                _pe_f = _pool.submit(PoliticalEconomyAgent().analyse, concept, phase1_ctx)
                                _sk2 = _stream_into(
                                    skeptic.stream_rebut(concept, phase1_ctx, _sk1, _df1), sk2_ph
                                )
                                _df2 = _df2_f.result()
                                _pe = _pe_f.result()
                        st.markdown(_df2)
                    pe_ph.markdown(_pe)
                    ctx.debate_rounds.append(DebateRound(2, _sk2, _df2))
                    ctx.political_economy_analysis = _pe
                    st.session_state.ctx = ctx
                    st.session_state.ph2_r2_done = True
                except Exception as _err:
                    st.error(f"Round 2 failed: {_err}")
                    st.stop()
            else:
                _r = ctx.debate_rounds[1]
                sk2_ph.markdown(_r.skeptic_argument)
                with r2_col2:
                    st.markdown(_r.defense_argument)
                st.markdown("**Political Economy Analysis**")
                st.markdown(ctx.political_economy_analysis or "")

            st.divider()

            # ---- Round 3 (optional) ----
            if st.session_state.get("ph2_r2_done"):
                if not st.session_state.get("ph2_r3_checked"):
                    with st.spinner("Checking whether a third debate round is warranted..."):
                        _needs_r3 = should_run_round3(ctx)
                    st.session_state.ph2_r3_needs = _needs_r3
                    st.session_state.ph2_r3_checked = True
                else:
                    _needs_r3 = st.session_state.get("ph2_r3_needs", False)

                if _needs_r3:
                    sk3_ph, r3_col2 = _debate_columns(3)

                    if not st.session_state.get("ph2_r3_done"):
                        try:
                            _transcript = ctx.debate_transcript()
                            skeptic = FIASkepticAgent()
                            defence = LiberalConstructionAgent()
                            with r3_col2:
                                with st.spinner("Analysing..."):
                                    with ThreadPoolExecutor(max_workers=1) as _pool:
                                        _df3_f = _pool.submit(
                                            defence.final_rebuttal, concept, phase1_ctx, _transcript
                                        )
                                        _sk3 = _stream_into(
                                            skeptic.stream_final_rebuttal(
                                                concept, phase1_ctx, _transcript
                                            ),
                                            sk3_ph,
                                        )
                                        _df3 = _df3_f.result()
                                st.markdown(_df3)
                            ctx.debate_rounds.append(DebateRound(3, _sk3, _df3))
                            st.session_state.ctx = ctx
                            st.session_state.ph2_r3_done = True
                        except Exception as _err:
                            st.error(f"Round 3 failed: {_err}")
                            st.stop()
                    else:
                        _r = ctx.debate_rounds[2]
                        sk3_ph.markdown(_r.skeptic_argument)
                        with r3_col2:
                            st.markdown(_r.defense_argument)

                    st.divider()

                # ---- Phase 2.5 — Rival Protest (agent runner only) ----
                _r3_done = not _needs_r3 or st.session_state.get("ph2_r3_done")
                if _r3_done and not st.session_state.get("ph2_protest_done"):
                    try:
                        _transcript = ctx.debate_transcript()
                        with st.spinner(
                            "Simulating rival team legal challenge "
                            "(searching web for recent context)..."
                        ):
                            _protest = RivalProtestAgent().analyse(
                                concept, phase1_ctx, _transcript
                            )
                        ctx.rival_protest_analysis = _protest
                        st.session_state.ctx = ctx
                        st.session_state.ph2_protest_done = True
                        st.session_state.phase2_done = True
                        st.rerun()
                    except Exception as _err:
                        st.error(f"Rival Protest agent failed: {_err}")
                        st.stop()

    # ------------------------------------------------------------------
    # Phase 3-4-5 — runs after rival protest completes
    # ------------------------------------------------------------------
    if st.session_state.get("ph2_protest_done"):
        if not st.session_state.get("phase345_done"):
            from f1reg.pipeline.phase345 import run_phase345

            with st.status(
                "Completing analysis — strategy, audit, and verdict...",
                expanded=True,
            ) as _s345:
                try:
                    run_phase345(
                        ctx,
                        progress_callback=lambda msg: st.write(msg),
                    )
                    st.session_state.ctx = ctx
                    st.session_state.phase345_done = True
                    _s345.update(
                        label="Analysis complete — memo ready",
                        state="complete",
                        expanded=False,
                    )
                except Exception as _err:
                    _s345.update(
                        label=f"Phase 3-5 failed: {_err}", state="error"
                    )
                    st.stop()

        if st.session_state.get("phase345_done"):
            st.session_state.phase = "complete"
            st.rerun()

    if st.button("Start new assessment", type="primary"):
        _reset()
        st.rerun()


# ---------------------------------------------------------------------------
# Phase: complete — memo display
# ---------------------------------------------------------------------------
elif st.session_state.phase == "complete":
    ctx: MemoContext = st.session_state.ctx

    if ctx.memo_markdown:
        # Word download button at the top so it's immediately visible
        try:
            import re as _re
            from f1reg.memo.docx_renderer import build_memo_docx
            _docx_data = build_memo_docx(ctx)
            _slug = _re.sub(r"[^a-z0-9]+", "_", ctx.concept.summary.lower())[:40].strip("_")
            _docx_name = f"f1_memo_{_slug}_{ctx.concept.season}.docx"
            st.download_button(
                "Download memo as Word (.docx)",
                data=_docx_data,
                file_name=_docx_name,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                type="primary",
            )
        except Exception as _docx_err:
            st.caption(f"Word export unavailable: {_docx_err}")

        st.divider()
        st.markdown(ctx.memo_markdown)

    if st.button("Start new assessment", use_container_width=True):
        _reset()
        st.rerun()
