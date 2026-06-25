# CLAUDE.md — Revenue Manager Agent Challenge

## Project Summary

Building a **Revenue Manager Agent for a Hotel GM** using LangChain Deep Agents + Postgres.
The agent reads reservation data, detects changes in future business, and delivers commercial judgment.

**Candidate:** Hemant Singh | **Started:** 24 June 2026

---

## Documentation Index

Always read the relevant doc before starting work on a phase. These files chunk the README into topic-focused references.

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
| Phase 1 — ETL | Not started | |
| Phase 2 — Tools | Not started | |
| Phase 3 — Skills | Not started | |
| Phase 4 — Deploy | Not started | |

---

## Critical Rules — Never Forget

### 1. Table Grain
`reservations_hackathon` = **one row per reservation × stay_date**
- `COUNT(DISTINCT reservation_id)` for reservation counts (never COUNT(*))
- `SUM(number_of_spaces)` for room nights

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
- `daily_total_revenue_before_tax` → broader revenue questions

### 5. Macro Groups
Always join `market_macro_group_history` on `stay_date` overlap (not static `macro_group` from `market_code_lookup`)

### 6. No Raw SQL Tool
Do NOT expose `run_sql(query: str)` to the model. Build specific tools with business logic baked in.

### 7. HITL Required
`get_as_of_otb` MUST be gated behind human approval. Tests must prove this.

### 8. Skills Need Judgment
≥3 skills must encode thresholds + recommended actions (not just metric definitions).

---

## Key File Paths

```
schema.sql                          -- DB table definitions
docs/00_project_overview.md         -- Phase overview + URLs
docs/01_etl_phase1.md               -- ETL guide
docs/02_database_schema.md          -- Schema reference
docs/03_business_concepts.md        -- Domain + pitfalls
docs/04_agent_architecture.md       -- Deep Agents guide
docs/05_tools_and_skills.md         -- Tools + skills spec
docs/06_deploy_submit.md            -- Deploy + submit
etl/SCRAPE_MANIFEST.json            -- (to create)
etl/LOAD_PROOF.json                 -- (to create)
tools/METRIC_DEFINITIONS.md         -- (to create)
skills/CHALLENGE_SKILL.md           -- (to create, must have otel-rm-v2)
ARCHITECTURE.md                     -- (to create)
tests/test_etl.py                   -- (to create, ≥3 cases)
tests/test_tools.py                 -- (to create, ≥10 cases)
tests/test_skills.py                -- (to create, ≥5 cases)
tests/test_agent.py                 -- (to create, ≥4 cases)
```

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
# Set ANTHROPIC_API_KEY + DB connection string
```

Docs: https://docs.langchain.com/oss/python/deepagents/overview
