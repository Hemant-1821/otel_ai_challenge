# Phase 4 — Deployment & Submission

## What We Need Running

Three components must be live and reachable:
1. **Database** — hosted Postgres (not on laptop)
2. **Agent backend** — the Deep Agents app
3. **Frontend** — chat UI that talks to the backend

---

## Database Hosting

Options: **Supabase**, **Neon**, or **Railway** (all work with Postgres)

Steps:
1. Create hosted Postgres instance
2. Run `schema.sql` to create tables
3. Run ETL pipeline to populate from data site
4. Note: DB on your laptop won't be reachable by a deployed app

---

## What the Live URL Must Be

A web page with a **chat box** where:
- We type a revenue-manager question
- The **Deep Agent answers** in plain English with numbers
- Answer comes **from the agent reading the DB** (no hardcoded answers)
- Agent must be **live and responsive** when reviewed

---

## UI Requirements

### Show Your Work (Required)

For each question, the UI must **stream and display**:
- Which **tools** ran
- Which **skills** loaded

In Deep Agents, loading a skill is a file-read tool call — surface tool calls and you surface skills automatically.

Plain chat-only UIs without tool/skill visibility are **insufficient**.

### Recommended UI Approach

Since Deep Agents runs on **LangGraph**, the easiest path:
- Serve agent as a **LangGraph app**
- Connect **deepagents UI** or **Agent Chat UI** (ready-made, renders streaming tool calls)
- OR build small custom frontend that streams tool/skill events

Streamlit works but won't surface tool/skill detail well — avoid it.

---

## Security Requirement

Put URL behind **HTTP basic auth** or simple login screen:
- Share the URL in submission
- Send credentials **privately** via the intake channel (never in README or repo)

---

## Health Endpoint (Required)

Expose `GET /health` returning JSON:

```json
{
  "db_fingerprint": "<reservation_stay_status_sha256 from LOAD_PROOF>",
  "dataset_revision": "<from load_manifest /verify>",
  "row_hash": "<load_manifest row_hash>",
  "financial_status_posted_only_rows": "<posted_stay_rows from LOAD_PROOF aggregates>"
}
```

This is called **before chat** to confirm the live DB matches the submitted proof.

---

## Submission Requirements

Per `SUBMISSION.md`:

1. **Live agent URL** (with chat box + tool/skill visibility)
2. **Username + password** (sent privately via intake channel)
3. **Link to solution repo** (public, or private with collaborator access)

The service must stay up for **at least 7 days after submission**.

---

## Phase 4 Full Submission Checklist

### In the Repo

- [ ] `ATTESTATION.md`
- [ ] `etl/SCRAPE_MANIFEST.json`
- [ ] `etl/LOAD_PROOF.json`
- [ ] `tools/METRIC_DEFINITIONS.md`
- [ ] All 5 tools implemented
- [ ] `tests/test_tools.py` (≥10 cases)
- [ ] `tests/test_skills.py` (≥5 cases)
- [ ] `tests/test_agent.py` (≥4 cases)
- [ ] `skills/` directory (≥6 skills)
- [ ] `skills/CHALLENGE_SKILL.md` with `otel-rm-v2`
- [ ] `ARCHITECTURE.md`

### Deployment

- [ ] Database hosted and loaded by ETL (not on laptop)
- [ ] Agent deployed with streaming tool/skill UI
- [ ] `GET /health` endpoint working
- [ ] URL protected with username/password

### Submission

- [ ] Separate repo (not a fork of the brief repo)
- [ ] Submitted per `SUBMISSION.md` (URL + credentials + repo link)
- [ ] Service stays up ≥7 days after submission

---

## API Keys

Set in deployment environment — **never commit to repo**:
- `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`)
- Postgres connection string (for hosted DB)

---

## Deployment Hints

- Use **Railway** for simple all-in-one (DB + backend + frontend on same platform)
- Use **Neon** or **Supabase** for free-tier hosted Postgres
- Use **Fly.io**, **Render**, or **Railway** for agent backend
- Use **Vercel** or **Netlify** for frontend if separate

---

## Engineering Interview Prep (Phase 5 — Invitation Only)

~15-20 minutes covering:

1. **Explain one tool implementation** — walk through grain logic and cancellation handling
2. **Fix a failing `test_tools.py` case** — patch the tool (not the test) live
3. **Extend a skill with a new judgment rule** — live coding in an existing skill

**What to prepare:**
- Know exactly why each tool returns what it returns
- Be able to explain the grain of each tool's query
- Know which skills call which tools and why
- Be ready to add a threshold + recommendation to any skill
