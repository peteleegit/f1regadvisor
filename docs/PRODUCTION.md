# F1RegAdvisor — Production Readiness

This document describes what the current system is, what it is not, and what would need to change to turn it into a production-grade application.

---

## What the Current System Is

The deployed system is a **functional alpha prototype** on a Railway hobby plan. It runs as one of two services in the same Railway project as FIARulerPro:

- **fiaruler-pro** — the regulatory knowledge substrate (FastAPI + Streamlit)
- **f1regadvisor** — this service (Streamlit only)

It is deliberately minimal:

- Single Streamlit process; no background workers.
- No database — memo state lives only in Streamlit session state and is lost on page refresh or process restart.
- Single shared password for all users.
- No rate limiting on Claude API calls.
- No error recovery — if any agent fails, the assessment stops.
- No audit trail beyond what Railway logs.

---

## Authentication and Access Control

**Current:** Single shared password (`APP_PASSWORD`) checked in `app.py`. No session expiry, no user identity, no record of who ran which assessment.

**Production change:**
- Replace the password gate with individual accounts — SSO via Azure AD is the appropriate choice for an internal tool.
- Use `msal` (already available) to implement a device-code or redirect flow.
- Add a `user_id` to the memo context so assessments are attributable.
- Log each assessment to a database keyed by user, concept, season, and timestamp.

---

## Memo Persistence

**Current:** The `MemoContext` lives exclusively in Streamlit session state. Refreshing the browser, restarting the service, or running a new assessment discards all prior work. There is no way to retrieve a past memo.

**Production change:**
- Persist `MemoContext` to a database (PostgreSQL or SQLite on a volume) after each completed assessment.
- Store the assembled `memo_markdown` and the full structured context as a JSON blob.
- Add a memo history sidebar so users can retrieve past assessments.
- Consider a unique `assessment_id` (UUID) in the URL so memos are shareable by link.

---

## Cost Control and Rate Limiting

**Current:** Each assessment makes approximately 12–14 Claude API calls:
- 1 TCA call per intake turn (1–4 turns)
- 2 Phase 1 agent calls (Sonnet)
- 4–6 Phase 2 debate calls (Sonnet)
- 1 Round 3 oracle call (Sonnet)
- 1–2 web search calls — Political Economy + Rival Protest (Sonnet)
- 1 Phase 3 call (Sonnet)
- 1 Phase 4 call (Opus)
- 1 Phase 5 call (Opus)

Two of these are `claude-opus-4-7`, which costs roughly 15× more than Sonnet per token. A single full assessment consumes approximately $0.50–$2.00 of API budget depending on concept complexity.

**Production changes:**
- Track `input_tokens + output_tokens` per user per day and alert or throttle when daily spend exceeds a threshold.
- Consider caching Phase 1 results for identical `(regulatory_queries, season)` tuples — repeated assessments of the same concept need not re-run retrieval or the analysis agents.
- Optionally expose model selection to power users (e.g. Sonnet-only mode for faster, cheaper exploratory assessments).

---

## Error Recovery

**Current:** If any agent raises an exception, `app.py` shows an error and calls `st.stop()`. The partial assessment is lost.

**Production change:**
- Save `MemoContext` to the database after each phase completes, not only at the end. This enables resuming a failed assessment.
- Add per-agent retry with exponential back-off for transient Claude API errors (rate limits, service interruptions).
- Distinguish recoverable errors (API timeout → retry) from unrecoverable ones (malformed concept → show message, allow the user to restart Phase 0).

---

## Agent Quality

**Current:** All agent system prompts and output schemas are fixed in code. There is no feedback loop between assessment outcomes and prompt quality.

**Production improvements:**
- Add a thumbs-up / thumbs-down rating at the bottom of each completed memo, logged to the memo database. Use ratings to identify which concepts produce poor-quality assessments.
- The Evidence Auditor currently only flags issues — it does not trigger re-runs of implicated agents. The original design called for a targeted revision pass; implementing this would improve memo accuracy for HIGH-severity findings.
- The domain allowlist for web search (`WEB_SEARCH_DOMAINS`) is hardcoded. Make it configurable, and consider adding FIA press releases and official technical directive archives.

---

## Deployment and Infrastructure

### CI/CD

**Current:** F1RegAdvisor auto-deploys from GitHub (`main` branch) via Railway's GitHub integration. No test gate runs before deploy.

**Production change:**
- Add a GitHub Actions workflow that runs `pytest` on every pull request before merge.
- Tag releases and deploy only from tagged commits to the production Railway service.

### Horizontal Scaling

The current architecture is single-instance. Because all state is in Streamlit session state, horizontal scaling is not straightforward.

**Production change:**
- Move session state to a shared store (Redis or a database) keyed by session ID.
- This allows multiple Streamlit instances behind a load balancer.
- Note: Streamlit's WebSocket model still requires sticky sessions at the load balancer.

### Replacing Streamlit

Streamlit works well for a small internal audience but has limitations at scale:

- No native support for background job processing (assessment takes 3–6 minutes; a page refresh interrupts it).
- Global reruns on every widget interaction.
- Limited embedding in other applications.

**Long-term option:** Move assessment execution to a background worker (Celery + Redis), expose a REST API (`POST /assess`), and replace the Streamlit UI with a standard frontend (React, Vue). The pipeline itself (`phase1.py`, `phase2.py`, `phase345.py`) has no Streamlit dependency and can be called from any Python backend.

---

## Summary Checklist

| Item | Current | Production |
|---|---|---|
| Authentication | Shared password | SSO / Azure AD |
| Memo persistence | In-memory only (lost on refresh) | Database (PostgreSQL) |
| Cost tracking | None | Per-user daily token budget |
| Error recovery | Stop on any failure | Per-phase persistence + retry |
| Agent revision loop | Evidence Auditor flags only | Re-run implicated agents on HIGH findings |
| CI/CD | GitHub auto-deploy (no test gate) | GitHub Actions PR check + tagged release deploy |
| Scaling | Single Streamlit instance | Background worker + REST API |
| Frontend | Streamlit | Optional: custom frontend |
