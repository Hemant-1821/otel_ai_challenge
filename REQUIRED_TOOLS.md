# Required tool layer (Phase 2)

Your Revenue Manager Agent must expose a **deliberate tool surface**. Handing the
model a single `run_sql(query)` tool is an automatic fail.

Implement the five tools below with these **exact names** and semantics. How you
structure modules, types, and database access is your choice.

## Semantic views (required first)

Create and apply the views in [sql/VIEWS.example.sql](sql/VIEWS.example.sql) (or
equivalent) in your database **before** implementing tools. Document them in
`ARCHITECTURE.md`.

Required tools must read from:

- `vw_stay_night_base` — default OTB grain and filters
- `vw_segment_stay_night` — stay-night grain with stay-date-effective `macro_group`

Do **not** query `reservations_hackathon` directly from agent-facing tools.

## General rules

- Tools must **not** accept arbitrary SQL strings from the model.
- Each tool docstring must state the **grain** of every count and sum it returns.
- Default OTB filters: exclude `reservation_status = 'Cancelled'` **and**
  `financial_status = 'Provisional'` unless the tool argument or question explicitly
  includes tentative/provisional business.
- Room nights = `sum(number_of_spaces)` at stay-date grain unless documented otherwise.
- Reservation count = `count(distinct reservation_id)` at the filtered grain.
- Pickup booking windows use **Europe/London** local midnight boundaries, stored/compared in UTC.

---

## 1. `get_otb_summary`

```python
def get_otb_summary(stay_month: str, exclude_cancelled: bool = True) -> dict:
    """
    On-the-books summary for a calendar month of stay dates (YYYY-MM).

    Default universe: vw_stay_night_base (Posted, non-cancelled).

    Returns:
      - stay_month
      - row_count (stay-date rows)
      - reservation_count (distinct reservation_id)
      - room_nights (sum of number_of_spaces)
      - room_revenue (sum daily_room_revenue_before_tax)
      - total_revenue (sum daily_total_revenue_before_tax)
      - exclude_cancelled (echo input)
    """
```

**Grain note:** `row_count` is **not** reservation count. Document that in the docstring.

---

## 2. `get_segment_mix`

```python
def get_segment_mix(
    stay_month: str,
    macro_group: str | None = None,
) -> dict:
    """
  Segment mix for a stay month using vw_segment_stay_night.

  Returns a list of segments with:
    - market_code, market_name, macro_group (effective_macro_group)
    - room_nights, total_revenue
    - share_of_room_nights (0–1, denominator = all segments in scope)
    - share_of_revenue (0–1, same denominator)

  If macro_group is set, filter to that effective macro_group only.
  """
```

**Denominator:** shares must use the **same filtered population** for every segment
in the result set. State the denominator in the return payload.

---

## 3. `get_pickup_delta`

```python
def get_pickup_delta(
    booking_window_days: int,
    future_stay_from: str,
) -> dict:
    """
  Booking pace / pickup for future stays.

  booking_window_days: reservations whose create_datetime falls in the window
    [start_of_day_london(now - days), now] converted to UTC.
  future_stay_from: ISO date; only stay_date >= this date.

  Uses create_datetime for the booking window — not stay_date.

  Returns:
    - booking_window_days, future_stay_from
    - new_reservations (distinct reservation_id created in window)
    - new_room_nights (sum number_of_spaces for those stays)
    - new_total_revenue
    - by_segment (top segments by revenue with same definitions)
    """
```

---

## 4. `get_as_of_otb`

```python
def get_as_of_otb(stay_month: str, as_of_utc: str) -> dict:
    """
  Point-in-time on-the-books for stay_date month as known at as_of_utc.

  Include a stay row when:
    - create_datetime <= as_of_utc
    - and (reservation_status <> 'Cancelled' OR cancellation_datetime > as_of_utc)
    - and financial_status = 'Posted' (provisional excluded unless you document otherwise)

  Same return shape as get_otb_summary plus as_of_utc echo.
  """
```

---

## 5. `get_block_vs_transient_mix`

```python
def get_block_vs_transient_mix(stay_month: str) -> dict:
    """
  Block vs transient mix for a stay month (vw_stay_night_base).

  Returns:
    - block_room_nights, transient_room_nights
    - block_total_revenue, transient_total_revenue
    - block_share_of_room_nights, block_share_of_revenue
    - top_companies: top 3 company_name by total_revenue (null -> 'Transient')
    - top3_company_revenue_share (0–1 of month total revenue)
  """
```

---

## Tests you must ship

Add `tests/test_tools.py` with **at least ten** test cases covering the tool
scenarios in [tests/TOOL_TEST_SCENARIOS.md](tests/TOOL_TEST_SCENARIOS.md)
(scenarios 1–6, 8–12 minimum).

Add `tests/test_skills.py` with **at least five** cases covering
[tests/SKILL_TEST_SCENARIOS.md](tests/SKILL_TEST_SCENARIOS.md).

Add `tests/test_agent.py` with **at least four** cases covering
[tests/AGENT_TEST_SCENARIOS.md](tests/AGENT_TEST_SCENARIOS.md).

Tool tests must run against your loaded Postgres (or a documented test fixture DB).
Skill and agent tests may use filesystem / config mocks without LLM API calls.

---

## Submission checklist (Phase 2)

- [ ] `vw_stay_night_base` and `vw_segment_stay_night` created and documented
- [ ] Five required tools implemented with exact names
- [ ] No raw SQL string parameter on any agent-facing tool
- [ ] `tests/test_tools.py` with ≥ 10 cases covering published tool scenarios
- [ ] `tests/test_skills.py` with ≥ 5 cases covering published skill scenarios
- [ ] `tests/test_agent.py` with ≥ 4 cases covering published agent scenarios
- [ ] `tools/METRIC_DEFINITIONS.md` committed (≤ half page; see below)
- [ ] Tool module(s) importable without starting the agent server

---

## Metric definitions (required)

Add `tools/METRIC_DEFINITIONS.md` (≤ half page) defining in your own words:

- **Room nights** vs **stay rows** vs **reservations**
- Default **OTB** filters (`reservation_status`, `financial_status`, anchor date)
- **Pickup** window boundaries (`Europe/London` vs UTC storage)
- How **effective macro group** differs from static `market_code_lookup.macro_group`

This file is reviewed in Phase 2 — not optional boilerplate.
