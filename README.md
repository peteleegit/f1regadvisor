# F1RegAdvisor

Multi-agent AI system that assesses the regulatory risk of a Formula 1 technical concept and produces a structured risk memo with a bottom-line verdict, recommended action, and downloadable Word document.

F1RegAdvisor has no regulatory knowledge of its own. It retrieves relevant rule text and Stewards decision precedents from the **FIARulerPro** knowledge substrate (via HTTP), then runs nine specialist AI agents — including an adversarial debate, a political economy analysis, and a rival protest simulation — to synthesise a verdict.

---

## Quick Start

**Prerequisites:** Python 3.11+, an Anthropic API key, and a running FIARulerPro instance.

```bash
git clone <repo-url>
cd f1regadvisor
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements-app.txt

# Create .streamlit/secrets.toml — see docs/SETUP.md
streamlit run app.py
```

The app opens at `http://localhost:8501`. For Railway deployment, see [docs/SETUP.md](docs/SETUP.md).

---

## Documentation

| Doc | Contents |
|---|---|
| [docs/SETUP.md](docs/SETUP.md) | Local setup, Railway deployment, configuration reference, how to add a new agent |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Pipeline phases, agents, component map, session management, key design decisions |
| [docs/PRODUCTION.md](docs/PRODUCTION.md) | Current alpha limitations and what would need to change for production (auth, persistence, cost control, error recovery) |
| [docs/DESIGN.md](docs/DESIGN.md) | Original design intent — some sections superseded by ARCHITECTURE.md |

---

## Key Files

| File | Purpose |
|---|---|
| `app.py` | Streamlit UI, session management, pipeline orchestration |
| `f1reg/agents/` | One file per agent (technical_concept, debate, evidence_auditor, etc.) |
| `f1reg/pipeline/` | Phase execution files (phase1.py, phase2.py, phase345.py) |
| `f1reg/context.py` | `MemoContext` dataclass — the shared pipeline state |
| `f1reg/memo/` | Memo rendering: renderer.py (Markdown) and docx_renderer.py (Word) |
| `f1reg/config.py` | All configuration, Pydantic settings, web search domain allowlist |

---

## Pipeline at a Glance

```
Phase 0    Technical Concept Agent (interactive intake, ≤3 follow-up questions)
Phase 1    Regulatory Text Agent + Precedent Agent (parallel, from FIARulerPro /retrieve)
Phase 2    FIA Skeptic ↔ Liberal Construction debate (2–3 rounds) + Political Economy Agent
Phase 2.5  Rival Protest Agent (web search)
Phase 3    Procedural Strategy Agent (recommended action + mitigations)
Phase 4    Evidence Auditor (quality control, claude-opus-4-7)
Phase 5    Bottom Line Synthesis + memo assembly (claude-opus-4-7)
```

Wall-clock time: roughly 3–6 minutes per assessment.
