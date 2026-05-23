# F1RegAdvisor — System Design

## Purpose

F1RegAdvisor is a multi-agent AI system that takes a regulatory question, concept description, or new idea as input and produces a structured risk memo to help an expert (technical director, legal counsel, senior engineer) assess whether to proceed, modify, escalate, seek FIA clarification, or stop.

It is built on top of the FIARulerPro regulatory knowledge substrate, which provides hybrid retrieval over a corpus of ~3,200 FIA documents. F1RegAdvisor adds adversarial multi-agent reasoning, a structured advocacy debate, and a synthesised risk verdict.

---

## Relationship to FIARulerPro

FIARulerPro is a conservative regulatory Q&A tool — it answers "what do the rules say?" and is deliberately cautious about conclusions it cannot source.

F1RegAdvisor uses FIARulerPro's **retrieval layer** only, via its HTTP `/retrieve` endpoint, and builds its own synthesis layer with agents that are permitted to argue, advocate, and speculate — clearly labelled as such.

FIARulerPro's synthesis layer is not used by F1RegAdvisor. The two services are deployed independently; F1RegAdvisor calls FIARulerPro over the network rather than importing its Python package directly.

---

## The Risk Memo

Every run produces a structured memo with the following sections:

| # | Section | Description |
|---|---|---|
| 1 | **Relevant rule text** | Controlling clauses, definitions, appendices, and directives — what the rules literally say |
| 2 | **Relevant precedent** | Comparable decisions, enforcement history, and distinctions — how the rules have actually been applied |
| 3 | **Technical facts that matter** | Which aspects of the concept determine the legal outcome |
| 4 | **Arguments for legality** | Strongest constructor-favourable interpretation; labelled as advocacy |
| 5 | **Arguments against legality** | Strongest FIA/rival-team challenge; labelled as advocacy |
| 6 | **Political, protest, and media risk** | FIA political dynamics, rival team protest likelihood and framing, media and public reaction |
| 7 | **Mitigations** | Design changes, operating constraints, documentation strategy, testing approach, clarification path |
| 8 | **Bottom line** | Two-track assessment: *legal standing* (what the rules say, read in good faith) and *enforcement risk* (what the FIA will likely do, driven by political economy and precedent consistency). These two tracks can and often do diverge. A third field — *FIA predictability* — indicates how consistently the FIA applies rules in this area. |
| 9 | **Recommended next action** | Proceed / modify / escalate / seek clarification / prepare defence / stop |
| 10 | **Open questions** | Missing facts, stale sources, unresolved ambiguities, items requiring human review |
| A | **Appendix — Debate transcript** | Full record of the FIA Skeptic vs. Liberal Construction debate, all rounds |

---

## Agents

### Phase 0 — Intake (interactive)

**Technical Concept Agent**
- Runs before the pipeline starts, in a conversational loop with the user
- Identifies what is missing or ambiguous in the user's description
- May ask for clarification or request a document upload (design sketch, slide, internal brief)
- Produces a structured `ConceptDecomposition`: component, system, operating condition, driver input, software behaviour, aerodynamic effect, event type, test condition, visibility to rivals, cost-cap implications, and the regulatory query strings used for retrieval
- The concept decomposition is shared with every downstream agent

### Phase 1 — Evidence gathering (parallel)

**Regulatory Text Agent**
- Receives the `regulation_hits` returned from the Phase 1 HTTP retrieval call
- Answers: "What do the rules literally say — and where are they deliberately vague?"
- Does not speculate; cites sources only
- Classifies each identified ambiguity by likely FIA intent: `PRESERVED DISCRETION` (vagueness appears deliberate — an instrument of governance, not a drafting error), `DRAFTING IMPRECISION` (unintentional; a clarification request would likely be accepted), or `UNKNOWN`

**Precedent and Practice Agent**
- Receives the `precedent_hits` returned from the Phase 1 HTTP retrieval call (Stewards decisions, infringement notices, summonses, appeals, right-of-review outcomes)
- Answers: "How has this actually been enforced — and how consistently?"
- Notes enforcement history, distinctions from past cases, and gaps where there is no precedent
- Produces a `consistency_rating` (CONSISTENT / MIXED / CONTRADICTORY / INSUFFICIENT PRECEDENT) and `trend_direction`, and explicitly assesses what any inconsistency reveals about how the FIA actually uses the rule in practice

### Phase 2 — Adversarial debate

**Round 1 (parallel):**

**FIA Skeptic / Prosecutor Agent**
- Builds the strongest argument that the concept violates the rules, violates the intent of the rules, threatens safety, undermines competitive fairness, or should be restricted by clarification
- Permitted to argue beyond what retrieved text strictly supports, but must label inferences as such

**Liberal Construction / Defence Agent**
- Builds the strongest argument in favour of legality, engineering freedom, consistency with prior application, and the broader value of innovation and competition
- Same labelling rule for inferences

**Round 2 (parallel):**
Each agent reads the other's Round 1 and responds — specifically targeting the weakest points in the opposing argument. Neither agent sees its own Round 2 opponent's Round 2 (only Round 1).

**Round 3 (optional):**
The orchestrator decides whether genuine unresolved contention warrants a final rebuttal round. Not mandatory.

**Political Economy Agent ("James") — runs during Round 2, independently:**
- Covers six areas: (1) **FIA key actors** — names the relevant individuals (Technical Director, Race Director, WMSC figures), their known tendencies, and how current FIA leadership style affects the likely response; (2) **FIA institutional response** — approval, TD, clarification request, or wait for a protest; (3) **rival team response** — who will object and on what grounds; (4) **reactive rule change risk**; (5) **ambiguity as governance** — whether rule vagueness is a deliberate FIA tool being actively used in this area; (6) **media and paddock dynamics**
- Uses web search for current FIA personnel, recent controversies, and competitive context
- Its output is the **primary input** to the enforcement risk assessment in Phase 5 — not supplementary colour
- Named "James" in the UI

### Phase 2.5 — External challenge simulation

**Rival Protest Agent**
- Sees the full debate transcript (all rounds) before producing its output
- Simulates how a rival team would challenge the concept
- Covers: likely protest theories, technical framing they would use, which elements of the Skeptic's argument they would cite, and the media narrative they would construct
- Has access to web search

### Phase 3 — Strategy

**Procedural Strategy Agent**
- Sees all Phase 1 and Phase 2 outputs
- Recommends mitigations: design changes, operating constraints, documentation, testing strategy, clarification path
- Recommends next action: proceed / modify / escalate / seek clarification / prepare defence / stop

### Phase 4 — Quality control

**Evidence Auditor**
- Reviews the full draft memo
- Checks: conclusions supported by sources; outdated rules not mixed with current rules; public reporting not treated as authority; speculation labelled as such; cross-agent consistency
- Outputs structured findings with severity (HIGH / LOW)
- HIGH severity: triggers a single targeted revision of the implicated agent (with the critique as context); revised output replaces the original
- LOW severity: appended to the Open questions section
- Maximum one revision pass per agent — no infinite loops
- Uses a more capable model (claude-opus-4-7) for deeper cross-agent reasoning

### Phase 5 — Synthesis (orchestrator)

- Reads all agent outputs
- Produces a **two-track bottom line**: legal standing (what the rules say) and enforcement risk (what the FIA will do), which can diverge significantly
- Sets FIA predictability based on the precedent consistency rating and political economy analysis
- Assembles the final memo in section order, appending the full debate transcript
- Uses claude-opus-4-7 for the synthesis

---

## Execution Order

```
Phase 0     Technical Concept Agent (interactive; may run multiple turns)
               │
               ▼
Phase 1     Regulatory Text Agent ──┐  (parallel)
            Precedent Agent ────────┘
               │
               ▼
Phase 2     Skeptic Round 1 ────────┐  (parallel)
            Defence Round 1 ────────┤
            Political Economy ──────┘
               │
               ▼
Phase 2     Skeptic Round 2 ────────┐  (parallel; each reads opponent Round 1)
            Defence Round 2 ────────┘
               │
               ▼
Phase 2     Round 3 (optional — orchestrator decides)
               │
               ▼
Phase 2.5   Rival Protest Agent (sees full debate transcript)
               │
               ▼
Phase 3     Procedural Strategy Agent
               │
               ▼
Phase 4     Evidence Auditor (+ targeted revisions if needed)
               │
               ▼
Phase 5     Bottom line synthesis → final memo assembly
```

Wall-clock estimate: **3–6 minutes** (most phases are parallel; sequential depth is five levels).

---

## Technical Decisions

### Orchestration
Raw Anthropic async SDK (`anthropic.AsyncAnthropic`) + `asyncio.gather()` for parallel phases. No framework (not LangGraph, not CrewAI). The pipeline is well-defined enough that a framework adds abstraction without payoff.

### Interface
Streamlit with `st.chat_message` / `st.chat_input` for Phase 0 (the Technical Concept Agent is conversational). Progress display shows phase completion as each stage finishes and streams the debate transcript live. The final memo renders as Markdown in Streamlit with a Word document download button.

### Word document generation
`python-docx` — the assembled `memo_markdown` is rendered into a structured `.docx` file, served via `st.download_button`. Users can edit and annotate the document before sending to counsel.

### FIARulerPro substrate connection
HTTP POST to the FIARulerPro `/retrieve` endpoint via `httpx`:
```
POST {F1REG_FIARULER_API_URL}/retrieve
Authorization: Bearer {F1REG_FIARULER_API_KEY}
```
F1RegAdvisor has no dependency on the FIARulerPro Python package. The two services are deployed independently; locally, FIARulerPro must be running before starting F1RegAdvisor. On Railway, both run as separate services in the same project and communicate over the private network.

The `/retrieve` response returns deduplicated, ranked `regulation_hits` and `precedent_hits`. Agents do not receive raw text from FIARulerPro's synthesis layer.

### Models

| Agent | Model |
|---|---|
| Technical Concept, Regulatory Text, Precedent, Skeptic, Defence, Rival Protest, Political Economy, Procedural Strategy | `claude-sonnet-4-6` |
| Evidence Auditor, Bottom line synthesis | `claude-opus-4-7` |

### Web search
Anthropic built-in `web_search_20250305` tool. Restricted to credible domains:

**Primary (press and official):**
`fia.com`, `formula1.com`, `autosport.com`, `motorsport.com`, `the-race.com`, `racefans.net`

**Insider commentary (lower reliability — label accordingly):**
`x.com`

### Shared state
A `MemoContext` dataclass accumulates agent outputs as the pipeline progresses. Every agent receives the full context and writes its output into it. This is the single source of truth for the pipeline run.

### Season default
If the user does not specify a season, assume the current season (2026 at time of writing; read from config so it can be updated without code changes).

### Deployment
Deployed on Railway as a separate service in the same project as FIARulerPro. The Dockerfile builds the image; `start.sh` generates `.streamlit/secrets.toml` from Railway environment variables at container start. Services communicate over Railway's private network. See `docs/SETUP.md` for full deployment instructions.

---

## Deferred / Future Work

- Email delivery option (background processing + Word attachment via SendGrid or similar) — relevant if memo generation time exceeds ~5 minutes in practice
- Memo versioning / history (store past memos for a given concept; track how the risk assessment changes as regulations evolve)
- Batch mode (assess a set of concepts overnight, produce a report)
- Integration with FIARulerPro's query log for shared feedback tracking
- Fine-grained source filtering (e.g. restrict retrieval to specific document types for a given question)

> **Note:** Railway deployment and basic password authentication are both implemented. See `docs/SETUP.md` and `docs/PRODUCTION.md` for current state and planned production improvements (SSO, memo persistence, error recovery).
