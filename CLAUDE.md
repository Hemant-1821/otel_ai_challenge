# CLAUDE.md — Revenue Manager Agent Challenge

## Project Summary

Building a **Revenue Manager Agent for a Hotel GM** using LangChain Deep Agents + Postgres.
The agent reads reservation data, detects changes in future business, and delivers commercial judgment.

**Candidate:** Hemant Singh | **Started:** 24 June 2026

---

## Documentation Index

Always read the relevant doc before starting work on a phase.

| File | What's In It | Read When |
|------|-------------|-----------|
| [`docs/00_project_overview.md`](docs/00_project_overview.md) | Phase table, quick-start DB, key URLs, scoring, ATTESTATION answers, example questions | Starting any phase; understanding scope |
| [`docs/01_etl_phase1.md`](docs/01_etl_phase1.md) | Scraping strategy, Playwright, pagination, transform rules, LOAD_PROOF, SCRAPE_MANIFEST, checklist | Building or debugging ETL |
| [`docs/02_database_schema.md`](docs/02_database_schema.md) | Full schema SQL, every column explained, all lookup tables, joins reference, default OTB filters | Writing any SQL, designing tools, understanding data |
| [`docs/03_business_concepts.md`](docs/03_business_concepts.md) | Hotel RM glossary, grain rules, date field guide, revenue field guide, OTB filters, pitfalls, answer style | Designing tools/skills, writing queries, crafting agent responses |
| [`docs/04_agent_architecture.md`](docs/04_agent_architecture.md) | LangChain Deep Agents setup, all 8 building blocks, skills architecture, HITL, subagent routing, ARCHITECTURE.md requirements | Building the agent (Phases 2–3) |
| [`docs/05_tools_and_skills.md`](docs/05_tools_and_skills.md) | 5 required tools, tool design principles, semantic views, skill requirements, test requirements (test_tools, test_skills, test_agent), METRIC_DEFINITIONS.md | Implementing tools and skills (Phases 2–3) |
| [`docs/06_deploy_submit.md`](docs/06_deploy_submit.md) | Hosting options, UI requirements, /health endpoint, submission checklist, engineering interview prep | Deploying and submitting (Phase 4) |

---

## Current Status

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 0 — ATTESTATION.md | ✅ Complete | In repo |
| Phase 1 — ETL | ✅ Complete | Data in postgres, SCRAPE_MANIFEST + LOAD_PROOF written |
| Phase 2 — Tools | ✅ Complete | All 5 tools implemented, views created |
| Phase 3 — Skills + Agent | ✅ Complete | 9 skills, agent assembled and smoke-tested |
| Phase 4 — Web UI | ✅ Complete | FastAPI + login + chat UI with real-time SSE |
| Tests + ARCHITECTURE.md | ⏳ Pending | See pending section below |

---

## Critical Rules — Never Forget

### 1. Table Grain
`reservations_hackathon` = **one row per reservation × stay_date**
- `COUNT(DISTINCT reservation_id)` for reservation counts (never `COUNT(*)`)
- `SUM(number_of_spaces)` for room nights
- Never `SUM(adr_room)` — it repeats on every stay row; derive ADR as `revenue / room_nights`

### 2. Default OTB Filters
Always apply unless question says otherwise:
```sql
WHERE reservation_status != 'Cancelled'
  AND financial_status = 'Posted'
```

### 3. Date Fields
- `stay_date` → OTB, revenue, segment analysis
- `create_datetime` → pickup, pace, "what changed recently" (UTC)

### 4. Revenue Fields
- `daily_room_revenue_before_tax` → room-only questions
- `daily_total_revenue_before_tax` → broader revenue questions (default for most tools)

### 5. Macro Groups
Always join `market_macro_group_history` on `stay_date` overlap — never use the static `macro_group` column from `market_code_lookup`.

### 6. No Raw SQL Tool
Do NOT expose `run_sql(query: str)` to the model. All tools query semantic views only.

### 7. HITL Required
`get_as_of_otb` MUST be gated behind human approval via `interrupt_on` at graph level. The tool itself is a pure function — no `interrupt()` call inside the tool.

### 8. Skills Need Judgment
≥3 skills must encode thresholds + recommended actions (not just metric definitions).

---

## Architecture Decisions Made

### Semantic View Layer
Tools never query `reservations_hackathon` directly. Three views created in `sql/VIEWS.sql` and applied to DB:

| View | Filter | Used by |
|------|--------|---------|
| `vw_all_posted` | `financial_status = 'Posted'` only (includes cancelled) | `get_as_of_otb` |
| `vw_stay_night_base` | Posted + non-cancelled (default OTB) | All other tools |
| `vw_segment_stay_night` | Base + effective macro group via lateral join | `get_segment_mix` |

This is a hard rule documented in `tools/METRIC_DEFINITIONS.md`. Adding it here so it's never forgotten.

### HITL Design
HITL is implemented at the **graph level** via `interrupt_on={"get_as_of_otb": True}` in `create_deep_agent`. The tool is a pure function. This is the correct deepagents pattern — putting `interrupt()` inside a tool breaks the LangGraph state machine.

### Subagent Design
One subagent: `segment-analyst`. It handles deep segment and OTA concentration analysis.
- Gets `get_segment_mix` + `get_block_vs_transient_mix` (only these two)
- Uses the same `skills/` directory as the main agent — no duplication
- No explicit `model` key → inherits parent model (Anthropic)
- Main agent routes to it via `task()` tool when question involves segment depth

### Skills Architecture
9 skill files, each scoped to one concept (if you'd need "and" in the name, split it):

| Skill file | Purpose | Tools it routes to |
|------------|---------|-------------------|
| `grain_rules.md` | Table grain traps, metric formulas, adversarial warnings | `get_otb_summary` |
| `otb_filters.md` | Default OTB filters, date field selection, revenue field selection | all tools |
| `rm_answer_style.md` | RM persona, weak vs strong answer patterns, GM language mapping | — |
| `ota_concentration.md` | OTA >35% HIGH, 25–35% MODERATE, <25% HEALTHY | `get_segment_mix` |
| `cancellation_pace.md` | >20% HIGH, 10–20% MODERATE; pace interpretation | `get_otb_summary` ×2 |
| `pickup_interpretation.md` | 0 room nights within 30 days = CRITICAL | `get_pickup_delta` |
| `block_concentration.md` | Block >60% HIGH dependency, single company >30% flag | `get_block_vs_transient_mix` |
| `adr_yield.md` | Standard floor £120, Executive £180, blended £140 | `get_otb_summary` |
| `CHALLENGE_SKILL.md` | otel-rm-v2 manifest, full skill→tool routing matrix | — |

### Model
Single provider: **`anthropic:claude-sonnet-4-6`** for both main agent and subagent.
- Passed as a model string to `create_deep_agent`
- Subagent inherits by not specifying a `model` key in its dict
- API key: `ANTHROPIC_API_KEY` in `.env`

### recursion_limit
Passed per-invocation as `config={"recursion_limit": 15, ...}` — NOT as a `create_deep_agent` parameter. This is a LangGraph runtime config, not an agent config.

### Web UI
FastAPI + raw Jinja2 `Environment` (not Starlette's `Jinja2Templates`).
- Starlette's wrapper adds `url_for` to `env.globals`, causing Jinja2's LRU cache to build a `(name, dict)` tuple as cache key — unhashable in Python 3.14. Fixed by using `Environment` directly.
- SSE via `fetch` + `ReadableStream` (not `EventSource` — EventSource only supports GET)
- Sync agent runs in a daemon thread; callbacks post to `asyncio.Queue` via `run_coroutine_threadsafe`

---

## Key File Paths

```
schema.sql                          -- DB table definitions
sql/VIEWS.sql                       -- 3 semantic views (applied to DB)
tools/_db.py                        -- shared DB connection (reads DATABASE_URL from env)
tools/otb_summary.py                -- get_otb_summary
tools/segment_mix.py                -- get_segment_mix
tools/pickup_delta.py               -- get_pickup_delta
tools/as_of_otb.py                  -- get_as_of_otb (HITL gated)
tools/block_transient.py            -- get_block_vs_transient_mix
tools/METRIC_DEFINITIONS.md         -- view routing table, no-raw-table rule
skills/                             -- 9 skill files (see table above)
agent/agent.py                      -- create_deep_agent assembly point
agent/subagents.py                  -- segment-analyst subagent definition
agent/prompts.py                    -- SYSTEM_PROMPT
agent/__init__.py                   -- exports agent
server/app.py                       -- FastAPI app, SSE endpoint, auth routes
server/auth.py                      -- itsdangerous session cookie helpers
server/templates/login.html         -- login page (OTel green theme)
server/templates/chat.html          -- chat UI with Agent Reasoning panel
tmp_test_agent.py                   -- smoke test (NOT committed, delete after testing)
ARCHITECTURE.md                     -- (to create)
tests/test_tools.py                 -- (to create, ≥10 cases)
tests/test_skills.py                -- (to create, ≥5 cases)
tests/test_agent.py                 -- (to create, ≥4 cases)
```

---

## Environment Variables (all in `.env`, gitignored)

```
ANTHROPIC_API_KEY=sk-ant-...        -- main LLM provider
DATABASE_URL=postgresql://hackathon:hackathon@localhost:5432/hotel_hackathon
CHAT_USERNAME=admin
CHAT_PASSWORD=otelrm2026
SESSION_SECRET=otel-rm-secret-change-for-prod
```

---

## How to Run

```bash
# Start DB
docker-compose up -d

# Start web server
venv/bin/uvicorn server.app:app --reload --port 8000

# Smoke test agent directly (CLI)
venv/bin/python3 tmp_test_agent.py
```

Web UI login: `admin` / `otelrm2026`

---

## Pending Work

| Item | Requirement |
|------|-------------|
| `ARCHITECTURE.md` | ≤1 page: skill→tool routing matrix, subagent routing, HITL |
| `tests/test_tools.py` | ≥10 cases — direct tool calls against real DB |
| `tests/test_skills.py` | ≥5 cases — file structure, YAML frontmatter, threshold presence |
| `tests/test_agent.py` | ≥4 cases — graph structure, HITL wiring, subagent registration |
| Submission checklist | See `docs/06_deploy_submit.md` |

---

## Data Site

- List: `https://otel-hackathon-data-site.vercel.app/reservations` (100/page, client-rendered)
- Detail: `https://otel-hackathon-data-site.vercel.app/reservations/<id>`
- Reference: `https://otel-hackathon-data-site.vercel.app/reference`
- Verify: `https://otel-hackathon-data-site.vercel.app/verify`

**Must use Playwright** — pages are client-rendered, curl won't work.

---

## Deep Agents Install

```bash
pip install -qU deepagents langchain-anthropic
```

Docs: https://docs.langchain.com/oss/python/deepagents/overview
