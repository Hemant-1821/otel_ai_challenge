# ARCHITECTURE.md — otel AI Revenue Manager

**Candidate:** Hemant Singh | **Model:** `anthropic:claude-sonnet-4-6`

---

## 1. ETL boundary

- **Extract:** Playwright (headless Chromium) — data site is a client-rendered SPA; `curl` cannot reach it. For reservations, Playwright intercepts the browser's outbound POST API calls (network interception) rather than parsing HTML — the SPA fetches JSON from its own API which is captured directly, 100 records/page with pagination. Reference/lookup data (`/reference` page) is scraped from rendered HTML.
- **Transform:** Arrival→departure exploded into one row per `reservation_id × stay_date` (the fact table grain). Lookup tables (`room_type_lookup`, `market_code_lookup`, `channel_code_lookup`, `rate_plan_lookup`) loaded first so FK constraints hold on insert.
- **Load:** Truncate-reload on `reservations_hackathon`; lookup tables upserted. Idempotent — re-running produces the same DB state.
- **Verify:** `etl/LOAD_PROOF.json` captures row count, SHA-256 fingerprint (`reservation_stay_status_sha256`), posted-only row count, and `dataset_revision`. Reconciled against the `/verify` endpoint before submission.

---

## 2. Database and views

Three semantic views sit between the tools and `reservations_hackathon`. Tools never query the raw table directly — all business-rule filters are centralised in views.

| View | Filter | Used by |
|------|--------|---------|
| `vw_all_posted` | `financial_status = 'Posted'` (includes cancelled) | `get_as_of_otb` |
| `vw_stay_night_base` | Posted + `reservation_status != 'Cancelled'` | All other tools |
| `vw_segment_stay_night` | Base + effective macro group via lateral join on `market_macro_group_history` | `get_segment_mix` |

See `tools/METRIC_DEFINITIONS.md` for grain definitions and the no-raw-table rule.

---

## 3. Tool layer

| Tool | View(s) | Notes |
|------|---------|-------|
| `get_otb_summary` | `vw_stay_night_base` / `vw_all_posted` | Supports `breakdown="room_type"` via join to `room_type_lookup` |
| `get_segment_mix` | `vw_segment_stay_night` | Effective macro group from `market_macro_group_history`, never static column |
| `get_pickup_delta` | `vw_stay_night_base` | Filters on `create_datetime` for new-booking window |
| `get_as_of_otb` | `vw_all_posted` | Point-in-time rebuild; **HITL gated** |
| `get_block_vs_transient_mix` | `vw_stay_night_base` | `is_block` flag; top-N companies configurable |

No `run_sql` tool is exposed to the model. Arbitrary SQL access is disabled to prevent grain violations and filter bypass.

---

## 4. Deep Agents wiring

| Building block | Implementation |
|----------------|----------------|
| **Tools** | 5 named tools above — no raw SQL |
| **Skills** | 9 skill files in `skills/`; loaded by the agent via `SkillsMiddleware` on relevance |
| **Subagents** | `segment-analyst` subagent handles deep segment/OTA concentration questions; routed via `task()` tool; inherits parent model |
| **Planning** | `write_todos` used for multi-part GM questions before any tool calls |
| **Memory / filesystem** | `MemorySaver` checkpointer enables multi-turn conversation and HITL state persistence |
| **Human-in-the-loop** | `get_as_of_otb` gated via `interrupt_on={"get_as_of_otb": True}` in `create_deep_agent`; resumes with `Command(resume={"decisions": [{"type": "approve/reject"}]})` |
| **Model & prompt** | `anthropic:claude-sonnet-4-6`; revenue-manager persona with RM answer style, grain rules, and OTB filter defaults in system prompt |

---

## 5. Skill → tool routing matrix

| Skill | Primary tool(s) | Judgment thresholds |
|-------|----------------|---------------------|
| `grain_rules.md` | `get_otb_summary` | N — formula guardrails only |
| `otb_filters.md` | all tools | N — filter/date field selection |
| `rm_answer_style.md` | — | N — persona and answer pattern |
| `ota_concentration.md` | `get_segment_mix` | **Y** — >35% HIGH, 25–35% MODERATE, <25% HEALTHY |
| `cancellation_pace.md` | `get_otb_summary` ×2 | **Y** — >20% HIGH, 10–20% MODERATE |
| `pickup_interpretation.md` | `get_pickup_delta` | **Y** — 0 room nights in 30 days = CRITICAL |
| `block_concentration.md` | `get_block_vs_transient_mix` | **Y** — block >60% HIGH; single company >30% flag |
| `adr_yield.md` | `get_otb_summary` | **Y** — Standard <£120, Executive <£180, blended <£140 |
| `CHALLENGE_SKILL.md` | — | N — manifest and routing reference |

5 of 9 skills encode judgment (threshold + recommended action).

---

## 6. Agent tests

`tests/test_tools.py`, `tests/test_skills.py`, and `tests/test_agent.py` are **not implemented** due to time constraints. Tool correctness was validated manually against the live DB; HITL wiring and subagent routing were smoke-tested end-to-end via the chat UI.

---

## 7. Deployment topology

- **Database:** Hosted Postgres (Supabase / Neon / Railway) — schema via `schema.sql`, views via `sql/VIEWS.sql`, data via ETL pipeline
- **Agent backend:** FastAPI + uvicorn; agent runs sync in a daemon thread; SSE via `fetch` + `ReadableStream` (not `EventSource` — POST required)
- **Frontend:** Custom Jinja2 templates; login session via `itsdangerous` signed cookie; activity sidebar streams tool/skill events in real time
- **`GET /health`:** Returns `db_fingerprint`, `dataset_revision`, `row_hash`, `financial_status_posted_only_rows` from `LOAD_PROOF.json` + `load_manifest` table
- **API keys:** `ANTHROPIC_API_KEY` and `DATABASE_URL` in `.env` (gitignored); injected as environment variables in deployment

---

## 8. Out of scope

- No `run_sql` tool — prevents model from bypassing grain and filter rules
- No token-level streaming — SSE streams at the tool-call event level, which is sufficient for RM use
- No rate limiting or multi-user isolation beyond session cookie auth
