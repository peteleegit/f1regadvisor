# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick start

```bash
pip install -r requirements-app.txt

# Create .streamlit/secrets.toml (see docs/SETUP.md for full reference)
streamlit run app.py   # http://localhost:8501
```

F1RegAdvisor requires a running FIARulerPro instance. Set `F1REG_FIARULER_API_URL` (default `http://localhost:8000`) and `F1REG_FIARULER_API_KEY` to match.

Configuration uses the `F1REG_` env prefix (Pydantic `BaseSettings` in `f1reg/config.py`). Secrets can also come from `.streamlit/secrets.toml` — the `[fiaruler]` and `[anthropic]` sections override env vars when running under Streamlit.

There are no tests yet.

---

## Architecture

F1RegAdvisor has no regulatory knowledge of its own. It retrieves rule text and Stewards decisions from FIARulerPro via `POST /retrieve`, then runs nine specialist agents to produce a structured risk memo.

### Pipeline

```
Phase 0    TechnicalConceptAgent       interactive intake, ≤3 follow-up Q&A → ConceptDecomposition
Phase 1    RegulatoryTextAgent         what do the rules literally say + where are they vague?
           PrecedentAgent              (parallel) how have these rules been enforced?
Phase 2    FIASkepticAgent             builds strongest case for violation
           LiberalConstructionAgent    (parallel) builds strongest case for legality
           PoliticalEconomyAgent       (parallel, web search) FIA actors, rival posture, reactive rule risk
Phase 2.5  RivalProtestAgent           (web search) simulates rival constructor's protest strategy
Phase 3    ProceduralStrategyAgent     recommended action + mitigations
Phase 4    EvidenceAuditorAgent        cross-agent quality control
Phase 5    BottomLineAgent             (claude-opus-4-7) two-track verdict: legal standing + enforcement risk
```

Phase 2 (debate) may run a Round 3 if `should_run_round3()` (a lightweight Claude call) determines genuine unresolved contention in Round 2.

### MemoContext — the pipeline bus

`f1reg/context.py` defines `MemoContext`, a dataclass that accumulates every agent output. It is stored in Streamlit session state and passed by reference through all phase files. Every agent reads whatever prior fields it needs and writes its own. This is the correct place to add new fields when adding agents — do not create parallel state structures.

### Agent model split

Most agents use `F1REG_PRIMARY_MODEL` (default `claude-sonnet-4-6`), including `EvidenceAuditorAgent`. `BottomLineAgent` uses `F1REG_VERDICT_MODEL` (default `claude-opus-4-7`) — the final verdict is the one step where the senior model is kept. `F1REG_SENIOR_MODEL` is defined in config but currently unused by any agent.

### Web search agents

`PoliticalEconomyAgent` and `RivalProtestAgent` call `_call_with_web_search()` from `base.py`, which uses Anthropic's `web_search_20250305` tool (up to 2 searches per call, `max_search_uses=2`). Domain allowlist is in `f1reg/config.py` as `WEB_SEARCH_DOMAINS`.

Both agents accept a `web_search: bool = True` kwarg. When `False`, they call `_call()` instead, skipping web search entirely. F1 Ruler exposes this as a toggle in the intake modal ("Search the web for the latest media and political F1 news?") that defaults to off.

**Critical:** Both agents strip preamble from web-search results using `re.search(r'(?m)^##\s+1\b', result)` and demote `## ` headings to `#### `. If you add a new agent using `_call_with_web_search`, apply the same pattern — Claude often emits thinking-aloud text before its structured output.

`_call_with_web_search` in `base.py` filters response blocks using `getattr(b, "type", "") == "text"` (not `hasattr`) — this is intentional.

### Parallelism

`ThreadPoolExecutor` for parallel agent calls. No orchestration framework. The pipeline graph is fixed, so this is sufficient. When phases need true parallel agent calls, see how Phase 1 and Phase 2 Round 1/Round 2 are structured in `f1reg/pipeline/phase1.py` and `phase2.py`.

### Debate agents get summaries, not raw text

All Phase 2+ agents receive `build_phase1_context(ctx)` — a compact formatted string of Phase 1 outputs — not the raw regulation text. This is deliberate: it keeps downstream prompts concise and forces the analysis agents (Phase 1) to do the extraction work.

### Session persistence

`app.py` maintains a module-level dict of `MemoContext` objects keyed by UUID session ID, appended to the URL as `?sid=<uuid>`. This survives Streamlit WebSocket reconnects. Sessions expire after 2 hours (TTL evicted on next page load). Do not persist this dict to disk — it is intentionally in-memory and process-scoped.

### Memo structure

The memo is verdict-first. The `Bottom Line` and `Recommended Action` appear before any analysis. The appendix contains the full debate transcript and all agent outputs. `renderer.py` produces Markdown; `docx_renderer.py` wraps it in a `.docx` for download. The two-track bottom line (`legal_standing` vs `enforcement_risk`) is a core design choice — they can diverge, and the synthesis agent must be honest about that gap.

### Adding a new agent

1. Create `f1reg/agents/<name>.py`, subclassing `BaseAgent`
2. Add the output field(s) to `MemoContext` in `f1reg/context.py`
3. Call it from the appropriate phase file in `f1reg/pipeline/`
4. Add a UI section in `app.py`
5. Include the output in memo assembly (`renderer.py` and `docx_renderer.py`) if it should appear in the final product
