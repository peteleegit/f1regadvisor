# F1RegAdvisor — Architecture

## Overview

F1RegAdvisor is a multi-agent regulatory risk memo system for Formula 1. It accepts a concept description from a user, runs it through a structured pipeline of nine specialist AI agents, and produces a formatted **Regulatory Risk Memo** with a bottom-line verdict, recommended action, and downloadable Word document.

F1RegAdvisor has no regulatory knowledge of its own. All regulatory text and Stewards decision precedents are retrieved over HTTP from the **FIARulerPro** knowledge substrate. F1RegAdvisor adds adversarial multi-agent reasoning, structured advocacy debate, political analysis, and synthesised risk assessment on top of that retrieval layer.

> **See also:** `docs/DESIGN.md` — the original design intent document. Note that several sections of DESIGN.md are now outdated: the substrate connection is HTTP (not a direct Python import), output is Word not PDF, and Railway deployment is live.

---

## Component Map

```
┌─────────────────────────────────────────────────────────────────────┐
│  F1RegAdvisor                                                        │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Streamlit UI  (app.py, port 8501)                           │   │
│  │  phase: intake → running → complete                          │   │
│  └────────────────────────┬─────────────────────────────────────┘   │
│                           │                                          │
│  ┌────────────────────────▼─────────────────────────────────────┐   │
│  │  Phase 0 — Technical Concept Agent                           │   │
│  │  Interactive intake, ≤3 follow-up questions                  │   │
│  │  → ConceptDecomposition (summary, season, queries, ...)      │   │
│  └────────────────────────┬─────────────────────────────────────┘   │
│                           │                                          │
│  ┌────────────────────────▼─────────────────────────────────────┐   │
│  │  Phase 1 — Retrieval + Analysis                (parallel)    │   │
│  │  ┌──────────────────────────┐  ┌─────────────────────────┐  │   │
│  │  │  RegulatoryText Agent    │  │  Precedent Agent        │  │   │
│  │  │  "What do the rules say?"│  │  "How enforced?"        │  │   │
│  │  └──────────────────────────┘  └─────────────────────────┘  │   │
│  │            ▲                              ▲                   │   │
│  │            └──────── HTTP /retrieve ──────┘                   │   │
│  └────────────────────────┬─────────────────────────────────────┘   │
│                           │                                          │
│  ┌────────────────────────▼─────────────────────────────────────┐   │
│  │  Phase 2 — Adversarial Debate                (2–3 rounds)   │   │
│  │  Round 1: FIA Skeptic ↔ Liberal Construction (parallel)      │   │
│  │  Round 2: rebuttals + Political Economy Agent (parallel)      │   │
│  │  Round 3: optional closing (orchestrator decides)            │   │
│  │                                                              │   │
│  │  Phase 2.5 — Rival Protest Agent             (web search)   │   │
│  └────────────────────────┬─────────────────────────────────────┘   │
│                           │                                          │
│  ┌────────────────────────▼─────────────────────────────────────┐   │
│  │  Phase 3 — Procedural Strategy Agent                         │   │
│  │  Phase 4 — Evidence Auditor          (claude-opus-4-7)       │   │
│  │  Phase 5 — Bottom Line Synthesis     (claude-opus-4-7)       │   │
│  └────────────────────────┬─────────────────────────────────────┘   │
│                           │                                          │
│  ┌────────────────────────▼─────────────────────────────────────┐   │
│  │  Memo Assembly                                                │   │
│  │  renderer.py → Markdown (displayed in Streamlit)              │   │
│  │  docx_renderer.py → Word (.docx) download                    │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                           │ HTTP POST /retrieve
                           │ Bearer auth
              ┌────────────▼───────────────┐
              │  FIARulerPro               │
              │  (substrate Railway svc)   │
              │  fiaruler-pro.railway      │
              │  .internal:8000            │
              └────────────────────────────┘
```

---

## Pipeline — Phase by Phase

### Phase 0 — Technical Concept Agent (intake)

**File:** `f1reg/agents/technical_concept.py`

An interactive conversational agent that refines the user's concept description before the pipeline runs. It may ask at most **three** follow-up questions (one per turn), then commits to a structured `ConceptDecomposition`.

The `ConceptDecomposition` captures:

| Field | Purpose |
|---|---|
| `summary` | One precise sentence describing the concept and its regulatory significance |
| `season` | Four-digit year (default: `F1REG_DEFAULT_SEASON`) |
| `component`, `system`, `operating_condition` | Technical dimensions of the concept |
| `driver_input`, `software_behaviour`, `aerodynamic_effect` | Functional dimensions |
| `event_type`, `test_condition`, `visibility_to_rivals`, `cost_cap_implications` | Contextual dimensions |
| `regulatory_queries` | 3–6 targeted search strings, varied to cover distinct regulatory angles |

The agent accepts an optional uploaded document (PDF or text) and extracts relevant facts from it before asking clarifying questions.

---

### Phase 1 — Retrieval + Analysis

**File:** `f1reg/pipeline/phase1.py`

Phase 1 has two steps that run sequentially: retrieval, then parallel agent synthesis.

**Step 1 — Retrieval via HTTP**

All `regulatory_queries` from the `ConceptDecomposition` are sent in a single `POST /retrieve` call to FIARulerPro. The payload specifies `regulation_limit`, `precedent_limit`, and `graph_hops=1`. FIARulerPro runs each query in parallel and returns deduplicated, ranked hits.

The response is split into:
- `regulation_hits` — FIA regulations, technical directives, sporting regulations
- `precedent_hits` — Stewards decisions

**Step 2 — Parallel agent synthesis**

Two agents run simultaneously, each receiving the formatted text of its respective hits:

**RegulatoryTextAgent** (`f1reg/agents/regulatory_text.py`)
- Answers: "What do the rules literally say?"
- Identifies controlling articles, key definitions, cross-references, and regulatory gaps
- Output: `RegulatoryTextOutput` (summary + structured lists)

**PrecedentAgent** (`f1reg/agents/precedent.py`)
- Answers: "How have these rules been enforced in practice?"
- Identifies comparable cases, analogous cases, distinctions, and precedent gaps
- Output: `PrecedentOutput` (summary + structured lists)

---

### Phase 2 — Adversarial Debate

**File:** `f1reg/pipeline/phase2.py`, `f1reg/agents/debate.py`

All debate agents receive `build_phase1_context(ctx)` — a compact formatted string of the Phase 1 regulatory and precedent analysis. They do **not** receive the raw regulation text; they work from the Phase 1 agents' structured summaries.

**Round 1 (parallel)**

- **FIASkepticAgent** — builds the strongest argument that the concept violates the rules, the intent of the rules, or threatens sporting integrity
- **LiberalConstructionAgent** — builds the strongest argument that the concept is legal, consistent with engineering freedom, and supported by precedent

Both agents may argue beyond what the retrieved text strictly supports, but must label inferences explicitly ("By inference...", "On policy grounds...", etc.).

**Round 2 (parallel)**

Each agent reads the other's Round 1 argument and responds, specifically targeting the weakest points. The **PoliticalEconomyAgent** also runs during Round 2, independently:

**PoliticalEconomyAgent** (`f1reg/agents/political_economy.py`)
- Uses web search to assess current FIA priorities, rival team posture, and recent regulatory controversies
- Covers: FIA reaction, rival team response, reactive rule change risk, media exposure, paddock dynamics

**Round 3 (optional)**

A lightweight oracle LLM call (`should_run_round3()`) checks whether genuine unresolved legal or factual contention in Round 2 warrants a closing rebuttal round. If yes, Skeptic and Defence each produce a final surgical argument.

---

### Phase 2.5 — Rival Protest Agent

**File:** `f1reg/agents/rival_protest.py`

Runs after all debate rounds are complete. Sees the full debate transcript. Uses web search to check for recent similar challenges.

Simulates how a rival constructor's legal team would challenge the concept: protest grounds, technical framing, documentary strategy, realistic prospects at stewards level and on appeal, and the media narrative they would construct.

---

### Phase 3 — Procedural Strategy Agent

**File:** `f1reg/agents/procedural_strategy.py`

Reads all Phase 1 and Phase 2 outputs and recommends:
- **Recommended action** — exactly one of: *Proceed as designed / Modify then proceed / Seek FIA clarification before proceeding / Escalate to legal counsel / Prepare regulatory defence / Do not proceed*
- **Rationale** — 2–3 sentence plain-English explanation
- **Mitigations** — concrete list: design changes, operating constraints, documentation steps, procedural actions

---

### Phase 4 — Evidence Auditor

**File:** `f1reg/agents/evidence_auditor.py`  
**Model:** `claude-opus-4-7`

Reviews all agent outputs for quality issues:
1. Conclusions stated as certain when they are inferences
2. Wrong-season or outdated regulations cited as current
3. Speculation not clearly labelled
4. Contradictions across agents
5. Material risks raised but absent from mitigations
6. Public media reporting treated as authoritative

Produces a list of `AuditFinding` records with severity `HIGH` or `LOW`. HIGH findings appear as a prominent blockquote warning in the final memo. LOW findings are appended to Open Questions.

---

### Phase 5 — Bottom Line Synthesis

**File:** `f1reg/agents/bottom_line.py`  
**Model:** `claude-opus-4-7`

Reads all prior agent outputs and produces:
- **Verdict** (exactly one): `LIKELY PERMITTED` / `LIKELY PROHIBITED` / `AMBIGUOUS` / `HIGH-RISK GREY AREA` / `REQUIRES FIA CLARIFICATION`
- **Confidence**: `high confidence` / `moderate confidence` / `low confidence`
- **Bottom line summary**: two sentences maximum, plain English, no hedging
- **Political risk summary**: three sentences covering rival protest likelihood, FIA dynamics, media exposure
- **Arguments for/against legality**: 3–5 bullets each, ≤20 words per bullet
- **Open questions**: genuine unresolved issues only

---

### Memo Assembly

**Files:** `f1reg/memo/renderer.py`, `f1reg/memo/docx_renderer.py`

The memo is verdict-first — the most time-pressed reader gets the answer immediately:

```
Bottom Line (verdict + confidence + 2-sentence summary)
Recommended Action
---
Arguments For Legality        [labelled as advocacy]
Arguments Against / Key Risks [labelled as advocacy]
Political and Protest Risk
Mitigations
Open Questions
⚠ Audit Flags (HIGH severity only)
---
Disclaimer
---
Appendix: Regulatory Analysis · Precedent Analysis · Political Economy ·
          Rival Protest Simulation · Debate Transcript (all rounds)
```

Output is rendered as Markdown in the Streamlit UI and also available as a downloadable `.docx` file (via `python-docx`) that users can edit and annotate before sending to counsel.

---

## Pipeline State

`MemoContext` (`f1reg/context.py`) is a dataclass that accumulates every agent output as the pipeline progresses. It is stored in Streamlit session state and passed by reference through all phases.

| Field | Populated by |
|---|---|
| `concept` | Phase 0 |
| `regulation_hits`, `precedent_hits` | Phase 1 retrieval |
| `regulatory_text_output`, `regulatory_summary` | RegulatoryTextAgent |
| `precedent_output`, `precedent_summary` | PrecedentAgent |
| `debate_rounds` | Phase 2 (one `DebateRound` per round) |
| `political_economy_analysis` | PoliticalEconomyAgent |
| `rival_protest_analysis` | Phase 2.5 |
| `recommended_action`, `mitigations` | Phase 3 |
| `audit_findings` | Phase 4 |
| `bottom_line_verdict`, `bottom_line_summary`, etc. | Phase 5 |
| `memo_markdown` | Memo assembly |

---

## Agent Model Selection

| Agent | Model | Reason |
|---|---|---|
| TechnicalConceptAgent | `claude-sonnet-4-6` | Conversational intake; speed matters |
| RegulatoryTextAgent | `claude-sonnet-4-6` | Structured extraction from retrieved text |
| PrecedentAgent | `claude-sonnet-4-6` | Structured extraction from retrieved text |
| FIASkepticAgent | `claude-sonnet-4-6` | Argumentative prose; fast streaming |
| LiberalConstructionAgent | `claude-sonnet-4-6` | Argumentative prose; fast streaming |
| PoliticalEconomyAgent | `claude-sonnet-4-6` | Web search + prose analysis |
| RivalProtestAgent | `claude-sonnet-4-6` | Web search + prose analysis |
| ProceduralStrategyAgent | `claude-sonnet-4-6` | Structured JSON output |
| EvidenceAuditorAgent | `claude-opus-4-7` | Cross-agent reasoning requires deeper synthesis |
| BottomLineAgent | `claude-opus-4-7` | Final verdict; highest-stakes output |

Models are configurable via `F1REG_PRIMARY_MODEL` and `F1REG_SENIOR_MODEL`.

---

## Web Search

Two agents use Anthropic's built-in `web_search_20250305` tool (up to 5 searches per call): `PoliticalEconomyAgent` and `RivalProtestAgent`. Search is restricted to a fixed domain allowlist:

**Primary (authoritative):** `fia.com`, `formula1.com`, `autosport.com`, `motorsport.com`, `the-race.com`, `racefans.net`

**Insider commentary (lower reliability — agents instructed to label accordingly):** `x.com`

The domain list is defined in `f1reg/config.py` as `WEB_SEARCH_DOMAINS`.

---

## Configuration

All settings use the `F1REG_` env prefix via Pydantic `BaseSettings`. Secrets (API keys, passwords) are read from `.streamlit/secrets.toml` at runtime.

| Variable | Default | Purpose |
|---|---|---|
| `F1REG_FIARULER_API_URL` | `http://localhost:8000` | FIARulerPro `/retrieve` base URL |
| `F1REG_FIARULER_API_KEY` | *(empty)* | Bearer token for FIARulerPro auth |
| `F1REG_PRIMARY_MODEL` | `claude-sonnet-4-6` | Model for most agents |
| `F1REG_SENIOR_MODEL` | `claude-opus-4-7` | Model for Evidence Auditor and Bottom Line |
| `F1REG_DEFAULT_SEASON` | `2026` | Season assumed when user doesn't specify |
| `F1REG_REGULATION_LIMIT` | `10` | Max regulation hits per `/retrieve` call |
| `F1REG_PRECEDENT_LIMIT` | `8` | Max precedent hits per `/retrieve` call |

Streamlit secrets (`.streamlit/secrets.toml`, not in repo):

```toml
[auth]
password = "..."

[anthropic]
api_key = "sk-ant-..."

[fiaruler]
api_url = "http://localhost:8000"
api_key = "your-retrieve-api-key"
```

`api_url` and `api_key` in `[fiaruler]` take precedence over the `F1REG_*` env vars when running under Streamlit.

---

## Authentication and Session Management

**File:** `app.py`

### Authentication

Access is gated by a shared password (`APP_PASSWORD` / `secrets.toml [auth] password`). On first load, `app.py` presents a password prompt. On success, a session token is written into Streamlit session state; no user identity is recorded. This is intentionally minimal — see `docs/PRODUCTION.md` for the planned SSO upgrade path.

### Session persistence across WebSocket reconnects

Streamlit destroys session state on WebSocket disconnect (browser refresh, network drop). To allow reconnection without losing an in-progress assessment, `app.py` maintains a **server-side session store**:

- On assessment start, a UUID session ID is generated and appended to the URL as `?sid=<uuid>`.
- The `MemoContext` is stored in a module-level dict keyed by session ID, alongside a TTL timestamp.
- On page load, if a `sid` query parameter is present and the session store entry has not expired, the context is restored into `st.session_state` and the UI resumes from where it left off.
- Expired sessions (default TTL: 2 hours) are evicted on the next page load.

This means bookmarking or refreshing the URL during or after an assessment will restore the memo, provided the server process has not been restarted.

---

## Key Design Decisions

**No direct substrate import.** F1RegAdvisor calls FIARulerPro's `/retrieve` HTTP endpoint rather than importing the `substrate` Python package. This allows the two services to be deployed, versioned, and scaled independently.

**MemoContext as pipeline bus.** All agent outputs accumulate in a single dataclass passed by reference. This makes it trivial to add or reorder agents without touching the others — every agent reads whatever prior fields it needs and writes its own.

**Debate agents get summaries, not raw text.** The regulatory and precedent agents produce structured summaries that all downstream agents (debate, strategy, bottom line) consume. This keeps debate prompts concise and forces the analysis agents to do the heavy lifting of extracting meaning from the retrieved corpus.

**No orchestration framework.** `ThreadPoolExecutor` for parallelism; plain sequential calls for dependencies. LangGraph and CrewAI add abstractions that are unnecessary when the pipeline graph is fixed and well-understood.

**Streaming debate display.** Each debate agent has a `stream_*` twin that yields text chunks. The Streamlit UI streams the Skeptic's argument while the Defence's runs in a background thread, so the user sees both sides appear in near-real-time rather than waiting for both to complete.

**Verdict-first memo structure.** The most senior reader (technical director, legal counsel) gets the bottom line and recommended action before any analysis. Full debate transcript and supporting analysis are in the appendix.
