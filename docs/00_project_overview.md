# Project Overview — Revenue Manager Agent (Hotel GM)

## What We're Building

A **Revenue Manager Agent for a Hotel General Manager** that:
- Reads reservation data from Postgres (populated by our ETL)
- Uses **LangChain Deep Agents** as the agent harness
- Detects changes in future business: pickup, cancellations, segment mix, risks
- Answers natural-language questions with commercial judgment (not just dashboard reads)
- Is deployed live with a chat UI showing tool/skill calls

**Candidate:** Hemant Singh  
**Date Started:** 24 June 2026

---

## Phases At a Glance

| Phase | Deliverable | Status |
|-------|-------------|--------|
| **0** | `ATTESTATION.md` (comprehension + ETL design note) | ✅ Done |
| **1** | ETL pipeline + `etl/LOAD_PROOF.json` + `etl/SCRAPE_MANIFEST.json` | Pending |
| **2** | Required tools + `tests/test_tools.py` + `tests/test_skills.py` + `tests/test_agent.py` | Pending |
| **3** | Skills (≥6) + `ARCHITECTURE.md` | Pending |
| **4** | Live deployed agent + submission | Pending |
| **5** | Engineering interview (by invitation) | Pending |

---

## Quick-Start: Local Database

```bash
docker compose up
```

- Database: `hotel_hackathon`
- User: `hackathon`
- Password: `hackathon`
- Port: `5432`

Connection string: `postgresql://hackathon:hackathon@localhost:5432/hotel_hackathon`

> The database starts **empty** — `docker compose up` creates tables from `schema.sql` but there is **no seed data**. You must run ETL to populate it.

---

## Key URLs

- **Data site:** `https://otel-hackathon-data-site.vercel.app`
- **Reservation list:** `/reservations` (paginated, 100 per page)
- **Reservation detail:** `/reservations/<id>`
- **Reference page:** `/reference` (room types, markets, channels, rate plans, macro-group dates)
- **Verify page:** `/verify` (check your load counts)
- **LangChain Deep Agents docs:** `https://docs.langchain.com/oss/python/deepagents/overview`

---

## How Scoring Works

- Submissions reconcile with the **live data site** and the ETL you built
- Coding assistants are fine but `compute_load_fingerprint.py` is necessary (not sufficient) — internal checks run too
- You receive a "submission received" ACK only — no scores/ranks/rubric feedback
- Phase 5 engineering interview for shortlisted candidates tests:
  1. Explain one tool implementation (grain / cancellation logic)
  2. Fix a failing `test_tools.py` case by patching the tool (not the test)
  3. Extend an existing skill with a new judgment rule live

---

## Repo Files Reference

| File | Purpose |
|------|---------|
| `schema.sql` | Creates empty DB tables |
| `docker-compose.yml` | Boots local Postgres |
| `sql/VIEWS.example.sql` | Semantic view templates for Phase 2 |
| `REQUIRED_TOOLS.md` | Phase 2 tool contract (5 required tools) |
| `ARCHITECTURE.example.md` | Phase 3 architecture template |
| `ATTESTATION.example.md` | Phase 0 attestation template |
| `scripts/compute_load_fingerprint.py` | Generates `etl/LOAD_PROOF.json` after load |
| `tests/ETL_TEST_SCENARIOS.md` | Published ETL test properties |
| `tests/TOOL_TEST_SCENARIOS.md` | Published tool test properties |
| `tests/SKILL_TEST_SCENARIOS.md` | Skill test properties |
| `tests/AGENT_TEST_SCENARIOS.md` | Agent test properties |
| `etl/LOAD_PROOF.example.json` | Shape for LOAD_PROOF |
| `etl/SCRAPE_MANIFEST.example.json` | Shape for SCRAPE_MANIFEST |
| `SUBMISSION.md` | Submission instructions |

---

## Phase 0 — ATTESTATION.md (Completed)

Key answers for reference:
- **Grain:** One row per `reservation_id × stay_date`
- **Revenue columns:** `daily_room_revenue_before_tax` (room only) vs `daily_total_revenue_before_tax` (room + packages/breakfast)
- **Default OTB excludes:** `reservation_status = 'Cancelled'` AND `financial_status = 'Provisional'`
- **`stay_date`** drives monthly OTB (not `property_date`)
- **`is_block = true`** = group/block reservation
- **100 reservations per list page** on the data site
- **HITL on `get_as_of_otb`** because it's a heavy point-in-time rebuild and LLM could hallucinate parameters

---

## Example Questions the Agent Must Handle

- What revenue is on the books by month?
- Which segments are driving July?
- How much of July is group business?
- Are we too dependent on OTA?
- What changed in the last 7 days for future stays?
- Which room type is generating the highest ADR?
- How much business was cancelled in June?
- What share of our future business is corporate?
- Which companies are contributing the most revenue?
- Is our business concentrated in a few large bookings?
