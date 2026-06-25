---
name: otb_filters
description: |
  Load this skill whenever the question is about on-the-books revenue, monthly
  OTB figures, cancelled business, provisional reservations, or point-in-time
  snapshots. Defines which filters to apply, which date field to use for which
  question, and which revenue field is appropriate.
---

# OTB Filters & Field Selection

## Default OTB universe

Every OTB answer uses these two filters unless the question explicitly overrides:

```
reservation_status <> 'Cancelled'
financial_status   = 'Posted'
```

These are pre-applied in `vw_stay_night_base`. Call `get_otb_summary` — it
enforces this by default (`exclude_cancelled=True`).

---

## When to override the defaults

| Question type | What to change | How |
|---|---|---|
| How much was cancelled? | Include cancelled rows | `get_otb_summary(exclude_cancelled=False)`, subtract from default result |
| Tentative / provisional pipeline | Include Provisional | Not supported in standard tools — flag to GM as out of scope |
| What did books look like last Thursday? | Point-in-time rebuild | `get_as_of_otb` — requires GM approval (HITL) |

Always state which filters are active when quoting OTB figures.

---

## Date field selection — use the right field for the right question

| Question | Field to use | Why |
|---|---|---|
| Revenue / OTB for a month | `stay_date` | Represents which night the revenue belongs to |
| What was booked recently? | `create_datetime` | When the reservation was created |
| What changed in the last N days? | `create_datetime` | Pickup window uses booking date, not stay date |
| Point-in-time snapshot | `create_datetime` + `cancellation_datetime` | Determines what existed at a reference time |

Tool routing: `get_otb_summary` and `get_segment_mix` filter on `stay_date`.
`get_pickup_delta` filters on `create_datetime`. `get_as_of_otb` uses both.

---

## Revenue field selection

| Question | Field | Notes |
|---|---|---|
| Room revenue, rate questions, ADR | `daily_room_revenue_before_tax` | Room charge only |
| Total revenue, broader performance | `daily_total_revenue_before_tax` | Includes packages, breakfast |

Default: use `daily_total_revenue_before_tax` for GM briefings unless the
question specifically asks about room rates or ADR.

---

## Adversarial traps — explicit warnings

**Trap 1 — Using `property_date` instead of `stay_date` for monthly OTB:**  
`property_date` is the hotel's business-date attribution and usually equals
`stay_date`, but they diverge at night-audit boundaries. Always use `stay_date`
for revenue and OTB analysis. `get_otb_summary` enforces this — never bypass it.

**Trap 2 — Including cancelled rows in default OTB without flagging it:**  
If a GM asks "what is on the books for August?" the answer must exclude cancelled
reservations. Including them silently overstates revenue. If you call
`get_otb_summary(exclude_cancelled=False)`, always say so explicitly in the answer.

**Trap 3 — Treating Provisional as OTB:**  
`financial_status = 'Provisional'` reservations are tentative — not confirmed
revenue. They are excluded from all standard OTB figures. Do not include them
without an explicit GM request and a clear caveat.

**Trap 4 — Using static `macro_group` from `market_code_lookup`:**  
Market codes can be reclassified mid-year. The static `macro_group` column on
`market_code_lookup` may not reflect the current classification for a given stay
date. Always use `vw_segment_stay_night` (via `get_segment_mix`) which resolves
`effective_macro_group` from the history table.

---

## Pickup window boundaries

`get_pickup_delta` uses `create_datetime` (stored in UTC) compared against a
window whose **start boundary is midnight Europe/London time**, converted to UTC.
This aligns with hotel business days. A "last 7 days" window starts at midnight
London time 7 days ago, not 168 exact hours ago.
