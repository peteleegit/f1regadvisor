# F1RegAdvisor — Setup Guide

## Prerequisites

- Python 3.11 or later
- An Anthropic API key (`sk-ant-...`)
- A running FIARulerPro instance (local or Railway) with the `/retrieve` endpoint accessible
- The FIARulerPro retrieve API key (set via `FIARULER_RETRIEVE_API_KEY` on the FIARulerPro side)

---

## Local Development

### 1. Clone and install

```bash
git clone <repo-url>
cd f1regadvisor
python -m venv .venv

# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements-app.txt
```

### 2. Configure secrets

Create `.streamlit/secrets.toml` (this file is git-ignored):

```toml
[auth]
password = "your-chosen-password"

[anthropic]
api_key = "sk-ant-..."

[fiaruler]
api_url = "http://localhost:8000"
api_key = "your-fiaruler-retrieve-key"
```

`api_url` should point to the FIARulerPro FastAPI server. If running FIARulerPro locally, start it first:

```bash
# In the FIARulerPro directory:
FIARULER_RETRIEVE_API_KEY=your-fiaruler-retrieve-key uvicorn substrate.api.app:app --port 8000
```

### 3. Run the app

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`.

---

## How the App Works

`app.py` manages a three-phase Streamlit state machine:

| Phase | State value | What happens |
|---|---|---|
| Intake | `"intake"` | Technical Concept Agent converses with the user (up to 3 turns) |
| Running | `"running"` | Phases 1–5 execute sequentially; debate streams live |
| Complete | `"complete"` | Final memo displayed; Word download available |

The `MemoContext` object accumulates all agent outputs and is stored in `st.session_state.ctx` throughout the run. Clicking **New Assessment** calls `_reset()`, which clears all pipeline state and returns to the intake phase.

### Document upload

At the start of a new assessment, users can upload a PDF or text file. The content is extracted (via `pdfplumber` for PDFs) and prepended to the first Technical Concept Agent turn, so the agent can read it before asking clarifying questions.

### Streaming debate display

Each debate round uses `stream_*` methods on the agent (e.g. `FIASkepticAgent.stream_argue()`), which yield text chunks from the Claude streaming API. The Streamlit UI streams the Skeptic's text into a placeholder while the Defence's response runs in a background thread. Both columns fill in near-real-time.

---

## Running Tests

```bash
pytest -v
```

```bash
# With coverage:
pytest --cov=f1reg --cov-report=term-missing
```

---

## Railway Deployment

F1RegAdvisor is deployed as a separate Railway service in the **same Railway project** as FIARulerPro. Services in the same project share a private network, which is how F1RegAdvisor reaches FIARulerPro at `localhost:8000` without going over the public internet.

### First-time setup

1. Create a new Railway service in the **fiaruler-pro project** (not a separate project).
2. Connect the service to this GitHub repo and select the **Dockerfile** builder.
3. Set environment variables in Railway:

| Variable | Value |
|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-...` |
| `APP_PASSWORD` | Login password for the UI |
| `F1REG_FIARULER_API_URL` | `http://localhost:8000` |
| `F1REG_FIARULER_API_KEY` | Must match `FIARULER_RETRIEVE_API_KEY` on the fiaruler-pro service |
| `PORT` | `8501` |

4. Deploy. Railway builds the Docker image and starts `start.sh`.

### How startup works

`start.sh` runs at container start:

1. Creates `/app/.streamlit/secrets.toml` from the environment variables above.
2. Launches `streamlit run app.py` on `$PORT`.

There is no database download or warm-up step — F1RegAdvisor is stateless between sessions.

### Updating the app (code changes)

Push to `main`. Railway detects the push and automatically rebuilds and redeploys the service. The rebuild takes 2–3 minutes (pip install + Docker layer caching).

---

## Configuration Reference

### Application settings (`F1REG_` prefix, or `.env` file)

| Variable | Default | Description |
|---|---|---|
| `F1REG_FIARULER_API_URL` | `http://localhost:8000` | FIARulerPro `/retrieve` base URL |
| `F1REG_FIARULER_API_KEY` | *(empty)* | Bearer token for FIARulerPro auth |
| `F1REG_PRIMARY_MODEL` | `claude-sonnet-4-6` | Model for most agents |
| `F1REG_SENIOR_MODEL` | `claude-opus-4-7` | Model for Evidence Auditor and Bottom Line |
| `F1REG_DEFAULT_SEASON` | `2026` | Season assumed when user doesn't specify |
| `F1REG_REGULATION_LIMIT` | `10` | Max regulation hits per retrieval call |
| `F1REG_PRECEDENT_LIMIT` | `8` | Max precedent hits per retrieval call |

Streamlit secrets (`.streamlit/secrets.toml`) override `F1REG_FIARULER_API_URL` and `F1REG_FIARULER_API_KEY` when the app runs under Streamlit. Set both for safety.

### Railway-specific variables

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key (injected into secrets.toml by start.sh) |
| `APP_PASSWORD` | UI login password |
| `F1REG_FIARULER_API_URL` | FIARulerPro private network URL |
| `F1REG_FIARULER_API_KEY` | Retrieve bearer token |
| `PORT` | Streamlit port (set to `8501`) |

---

## Adding a New Agent

1. Create `f1reg/agents/my_agent.py` subclassing `BaseAgent`. Implement a method that calls `self._call()` (or `self._call_with_web_search()`) and returns a typed output.
2. Add the output field(s) to `MemoContext` in `f1reg/context.py`.
3. Call the agent from the appropriate phase file (`phase1.py`, `phase2.py`, or `phase345.py`) and write the result into `ctx`.
4. Update `build_phase1_context()` in `phase2.py` if downstream agents need to see the new output.
5. Update `renderer.py` and `docx_renderer.py` to include the new section in the memo.
6. Update the `BottomLineAgent` and `EvidenceAuditorAgent` prompts if the new agent's output should influence the final verdict or quality check.

The architecture is intentionally flat — agents are independent functions, not nodes in a framework graph. Adding an agent is adding a function call and a field on `MemoContext`.
