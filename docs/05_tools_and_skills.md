# Tools, Skills & Tests Reference

## Overview

Phase 2 requires exactly **5 tools** as specified in `REQUIRED_TOOLS.md` (not yet available locally — fetch from data site or check the repo when it exists). This file captures what we know from README.

---

## Tool Design Principles

### No Raw SQL Exposed to the Model

The agent must NOT have a `run_sql(query: str)` tool. Instead:
- Each tool encodes specific business logic
- Tools enforce correct grain, cancellation exclusions, date fields, revenue fields
- Tools are tested to prove correctness

### Semantic Views (Required)

Apply these two views before implementing tools (from `sql/VIEWS.example.sql`):

- **`vw_stay_night_base`** — base view with default OTB filters applied
- **`vw_segment_stay_night`** — segmented view for market analysis

These provide the foundation so tools don't re-implement filtering logic every time.

---

## The 5 Required Tools

*(Full specs in `REQUIRED_TOOLS.md` on the challenge repo — fetch when building)*

Based on README context, the required tools include at minimum:

### `get_otb_summary`
- Returns on-the-books summary for a date range
- Must distinguish `row_count` vs `reservation_count` vs `room_nights`
- Applies default OTB filters (non-cancelled, Posted)
- Key for "What revenue is on the books by month?"

### `get_segment_mix`
- Returns breakdown of business by market segment / macro group
- Uses `market_macro_group_history` (effective-dated, not static)
- Key for "Are we too dependent on OTA?" and segment-driving questions

### `get_pickup_delta`
- Returns pickup (new bookings) in a window for future stay dates
- Uses `create_datetime` (UTC) with `Europe/London` midnight as window boundaries
- Key for "What changed in the last 7 days for future stays?"

### `get_cancellation_summary`
- Returns cancellation counts and patterns
- Must explicitly include `reservation_status = 'Cancelled'` rows
- Key for "How much business was cancelled in June?"

### `get_as_of_otb` ← HITL Required
- Point-in-time OTB rebuild as of a specific `as_of_utc` timestamp
- Uses `cancellation_datetime` to determine which cancelled rows were still active at the reference time
- **Must be gated behind Human-in-the-Loop approval** — expensive + parameter-sensitive
- Key for "What did the books look like last Thursday?"

---

## Tool Return Shape Principles

Each tool should return:
- **Reservation count** (`COUNT(DISTINCT reservation_id)`)
- **Room nights** (`SUM(number_of_spaces)`)
- **Revenue** (both room and total)
- **ADR** where relevant
- Clear labeling of what's included/excluded

---

## `tools/METRIC_DEFINITIONS.md`

This file must be committed with explicit definitions for:

| Metric | Definition to Document |
|--------|----------------------|
| Reservation count | `COUNT(DISTINCT reservation_id)` with OTB filters |
| Room nights | `SUM(number_of_spaces)` across active stay rows |
| Room revenue | `SUM(daily_room_revenue_before_tax)` |
| Total revenue | `SUM(daily_total_revenue_before_tax)` |
| ADR | `SUM(daily_room_revenue_before_tax) / SUM(number_of_spaces)` |
| OTB | Non-cancelled, Posted rows for future stay dates |
| Pickup | Reservations with `create_datetime` in booking window |

---

## Skills Structure

### Directory: `skills/`

Each skill = `SKILL.md` file with YAML frontmatter:

```markdown
---
name: skill_name
description: |
  otel-rm-v2
  Precise description of when to load this skill and what it does.
---

# Skill content here
...
```

### Minimum 6 Skills Required

Suggested skill areas (decide depth and framing yourself):

| Skill Area | Type | Notes |
|------------|------|-------|
| OTA dependency analysis | Judgment | Threshold: % of revenue from OTA; flag if > threshold; recommend direct campaign |
| Group vs transient mix | Analysis | Use `is_block`; segment interpretation |
| Cancellation pace analysis | Judgment | Acceleration detection; overbooking recommendation threshold |
| Pickup delta interpretation | Judgment | Compare pace to prior year; demand risk flags |
| ADR and revenue optimization | Judgment | Room type ADR floors; yield recommendations |
| Concentration risk | Judgment | Single-company or single-segment dominance |

### `skills/CHALLENGE_SKILL.md` (Required)

Must contain `otel-rm-v2` in the YAML `description` frontmatter. This is the skill pack identifier.

### ≥3 Skills Must Encode Judgment

Judgment = thresholds + recommended actions, not just metric definitions.

Example pattern for a judgment skill:
```markdown
## OTA Dependency Assessment

When OTA share of total revenue exceeds 35% for any 30-day window:
- Flag as HIGH concentration risk
- Quantify: "OTA is X% of July revenue vs 35% threshold"
- Recommend: "Consider direct booking promotion on brand.com; review rate parity agreement"
- Note commission cost impact (OTA commissions typically 15-20%)

When OTA share is 25-35%: MODERATE — monitor
When OTA share is <25%: HEALTHY — note in briefing
```

---

## Test Requirements

### `tests/test_tools.py` — ≥10 cases

Based on `tests/TOOL_TEST_SCENARIOS.md`. Must cover:
- Correct grain (row count vs reservation count vs room nights)
- Correct OTB filter behavior (cancelled excluded, provisional excluded)
- Correct date field usage (stay_date vs create_datetime)
- Correct revenue field (room vs total)
- Edge cases (date boundary, single-night vs multi-night, multi-room)

### `tests/test_skills.py` — ≥5 cases

Based on `tests/SKILL_TEST_SCENARIOS.md`. Must cover:
- Structural skill tests (thresholds present, tool routing defined)
- Judgment tests (correct recommendation for given data)
- Adversarial guardrails (skill doesn't hallucinate unsupported conclusions)
- Use **structure mocks and graph introspection** — NOT live LLM calls in CI

### `tests/test_agent.py` — ≥4 cases

Based on `tests/AGENT_TEST_SCENARIOS.md`. Must cover:
- **HITL on `get_as_of_otb`** — agent triggers approval before executing
- **Subagent routing** — segment-mix questions route to subagent
- **Multi-tool plans** — agent decomposes multi-part questions into ordered steps
- Use **structure mocks and graph introspection** — NOT live LLM calls in CI

---

## Semantic Layer Value

A semantic layer (views + tools with baked-in business rules) prevents these common model mistakes:

| Mistake | Prevention |
|---------|-----------|
| Counting rows instead of reservations | Tool returns `reservation_count` explicitly |
| Mixing room and total revenue | Two distinct return fields, clearly named |
| Forgetting cancelled rows | Default filter in view/tool |
| Confusing stay date and booking date | Tool parameter names force the distinction |
| Wrong macro group | Tool uses history join, not static lookup |

---

## Phase 2 Checklist

- [ ] `vw_stay_night_base` and `vw_segment_stay_night` applied
- [ ] All 5 required tools implemented
- [ ] `tools/METRIC_DEFINITIONS.md` committed
- [ ] No raw SQL string tools exposed to the model
- [ ] `tests/test_tools.py` (≥10), `tests/test_skills.py` (≥5), `tests/test_agent.py` (≥4) pass locally

## Phase 3 Checklist

- [ ] ≥6 skills in `skills/` directory
- [ ] ≥3 skills with judgment (thresholds + recommended actions)
- [ ] ≥1 skill with numeric threshold + recommended action
- [ ] `skills/CHALLENGE_SKILL.md` with `otel-rm-v2` in description frontmatter
- [ ] `ARCHITECTURE.md` committed (≤1 page, skill→tool matrix, subagent, HITL)
- [ ] `tests/test_skills.py` ≥5 passing
- [ ] `tests/test_agent.py` ≥4 passing
