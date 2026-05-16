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
def _reset() -> None:
    for key in ("phase", "ctx", "tca_messages", "display_messages",
                "uploaded_text", "question_count"):
        st.session_state.pop(key, None)


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
# Phase: running — pipeline progress display
# ---------------------------------------------------------------------------
elif st.session_state.phase == "running":
    ctx: MemoContext = st.session_state.ctx
    concept = ctx.concept

    st.subheader("Assessment in progress")
    st.markdown(f"> {concept.summary}")

    # Show conversation so the user remembers what was asked
    with st.expander("Concept intake conversation", expanded=False):
        for msg in st.session_state.display_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    st.divider()

    # Placeholder for pipeline phases 1-5
    # This block will be replaced as each phase is implemented.
    st.info(
        "**Pipeline phases 1–5 are under construction.**\n\n"
        "The concept decomposition below has been captured and will drive the "
        "full multi-agent analysis once the remaining agents are implemented.\n\n"
        "Phase 0 (Technical Concept Agent) is complete."
    )

    st.subheader("Concept decomposition")
    fields = {
        "Season": concept.season,
        "Component": concept.component,
        "System": concept.system,
        "Operating condition": concept.operating_condition,
        "Driver input": concept.driver_input,
        "Software behaviour": concept.software_behaviour,
        "Aerodynamic effect": concept.aerodynamic_effect,
        "Event type": concept.event_type,
        "Test condition": concept.test_condition,
        "Visibility to rivals": concept.visibility_to_rivals,
        "Cost-cap implications": concept.cost_cap_implications,
    }
    for label, value in fields.items():
        if value:
            st.markdown(f"**{label}:** {value}")

    st.subheader("Regulatory search queries")
    for q in concept.regulatory_queries:
        st.markdown(f"- {q}")

    if st.button("Start new assessment", type="primary"):
        _reset()
        st.rerun()


# ---------------------------------------------------------------------------
# Phase: complete — memo display
# ---------------------------------------------------------------------------
elif st.session_state.phase == "complete":
    ctx: MemoContext = st.session_state.ctx

    if ctx.memo_markdown:
        st.markdown(ctx.memo_markdown)

        # PDF download
        try:
            import markdown as md_lib
            import weasyprint
            html_body = md_lib.markdown(ctx.memo_markdown, extensions=["tables", "fenced_code"])
            html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body {{ font-family: Georgia, serif; max-width: 900px; margin: 40px auto;
         font-size: 13px; line-height: 1.6; color: #111; }}
  h1 {{ font-size: 20px; }} h2 {{ font-size: 16px; border-bottom: 1px solid #ccc; }}
  h3 {{ font-size: 14px; }} blockquote {{ color: #555; border-left: 3px solid #ccc;
  padding-left: 12px; }} code {{ background: #f4f4f4; padding: 1px 4px; }}
</style></head><body>{html_body}</body></html>"""
            pdf_bytes = weasyprint.HTML(string=html).write_pdf()
            st.download_button(
                "Download memo as PDF",
                data=pdf_bytes,
                file_name="risk_memo.pdf",
                mime="application/pdf",
            )
        except Exception as e:
            st.caption(f"PDF generation unavailable: {e}")

    if st.button("Start new assessment", type="primary"):
        _reset()
        st.rerun()
