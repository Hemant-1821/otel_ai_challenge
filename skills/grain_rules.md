---
name: grain_rules
description: |
  Load this skill whenever the question involves counting reservations, room
  nights, ADR, revenue share, or any aggregation over the reservations data.
  Defines the correct grain of the fact table and the right formula for every
  summary metric. Prevents the most common counting and calculation mistakes.
---

# Grain Rules

## The single most important fact

`reservations_hackathon` is **one row per reservation × stay_date**.

A 3-night reservation = **3 rows**, all sharing the same `reservation_id`.  
A 2-room 3-night reservation = **3 rows**, each with `number_of_spaces = 2`.

`COUNT(*)` counts stay-date rows, not reservations. It is almost always the wrong answer.

---

## The three counts — correct expression for each

| What the GM is asking | Correct expression | Common mistake |
|---|---|---|
| How many reservations? | `COUNT(DISTINCT reservation_id)` | `COUNT(*)` |
| How many room nights? | `SUM(number_of_spaces)` | `COUNT(*)` or `COUNT(DISTINCT reservation_id)` |
| How many stay-date rows? | `COUNT(*)` | — (rarely the right question) |

**Worked example:** A group booking for 3 rooms over 4 nights:
- Reservations: **1**
- Stay rows: **4** (one per night)
- Room nights: **12** (4 rows × `number_of_spaces = 3`)

Tool to call: `get_otb_summary` returns all three counts (`reservation_count`,
`room_nights`, `row_count`) so you can always cross-check grain.
For room-type breakdowns, pass `breakdown="room_type"` — returns `breakdown_rows`
with per-`space_type` counts, revenue, and pre-derived ADR.

---

## Summary metric formulas

### ADR (Average Daily Rate)

```
ADR = SUM(daily_room_revenue_before_tax) / SUM(number_of_spaces)
```

`adr_room` is a **reservation-level field repeated on every stay row**. Never
`SUM(adr_room)` — it multiplies the rate by the number of nights and produces
a number that is meaningless.

### Revenue share (segment or channel)

```
share_of_revenue = segment_total_revenue / all_segments_total_revenue
```

The denominator must be the **same filtered population** as the numerator.
`get_segment_mix` returns `share_of_revenue` pre-calculated with the correct
denominator echoed in `denominator_revenue`.

### Block share

```
block_share_of_revenue = block_total_revenue / (block_total_revenue + transient_total_revenue)
```

`get_block_vs_transient_mix` returns this directly as `block_share_of_revenue`.

### Cancellation volume

Cancelled rows are excluded from `vw_stay_night_base`. To count cancellations,
call `get_otb_summary` twice — once with `exclude_cancelled=True` (default) and
once with `exclude_cancelled=False` — and subtract:

```
cancelled_room_nights = room_nights(exclude_cancelled=False) - room_nights(exclude_cancelled=True)
```

---

## Columns that repeat across stay rows — never SUM these

| Column | What it is | Trap |
|---|---|---|
| `adr_room` | Reservation-level rate | Summing multiplies by nights |
| `nights` | Length of stay | Summing gives total nights across all rows, not per reservation |
| `lead_time` | Days from booking to arrival | Same value on every row of a reservation |
| `arrival_date`, `departure_date` | Trip boundaries | Repeated identically on every stay row |

---

## Adversarial traps — explicit warnings

**Trap 1 — Counting stay rows as reservations:**  
A GM asking "how many reservations do we have for July?" must be answered with
`COUNT(DISTINCT reservation_id)`, never `COUNT(*)`. A 10-night conference block
would otherwise count as 10 reservations.

**Trap 2 — Summing `adr_room`:**  
`adr_room = 250` on a 3-night reservation produces `SUM(adr_room) = 750`.
That number is not a rate and not revenue — it is a calculation error. Always
derive ADR from the revenue and room-night sums.

**Trap 3 — Using `nights` as room nights:**  
`nights` is the length of stay of the reservation (e.g. 3). `number_of_spaces`
is how many rooms on that reservation (e.g. 2). Room nights = `SUM(number_of_spaces)`
across stay rows, not `SUM(nights)`.

---

## Quick self-check before answering any counting or metric question

1. Am I counting reservations? → `COUNT(DISTINCT reservation_id)` via `get_otb_summary`
2. Am I counting room nights? → `SUM(number_of_spaces)` via `get_otb_summary`
3. Am I calculating ADR? → `SUM(daily_room_revenue_before_tax) / SUM(number_of_spaces)`; never use `adr_room` directly
4. Am I calculating a share? → verify numerator and denominator use the same filtered population
