---
name: pickup_interpretation
description: |
  Load this skill for any question about what changed recently, pickup in the
  last N days, booking pace for future stays, or whether demand for a future
  month is on track. Encodes pickup pace thresholds and demand risk signals.
---

# Pickup Interpretation & Booking Pace

## Tool to call

`get_pickup_delta(booking_window_days, future_stay_from)` — returns new
reservations and room nights created in the booking window for future stays.

- `booking_window_days`: how many days back to look (e.g. 7, 14, 30)
- `future_stay_from`: only count stays from this date forward; typically set to
  today so past nights do not dilute the signal

The tool returns `window_start_utc` and `window_end_utc` — always echo these
in the answer so the GM knows the exact window being measured.

---

## Pickup pace thresholds

Pickup is assessed relative to lead time and the stay month's distance from today.

| Scenario | Signal | Action |
|---|---|---|
| New room nights in last 7 days = 0 for a stay month within 30 days | **CRITICAL** — no pace for near-term dates | Flag demand risk; recommend rate promotion or OTA rate drop |
| New room nights in last 7 days < 5 for a stay month 30–90 days out | **SLOW** — below expected pace | Monitor daily; prepare a promotional rate offer |
| New room nights in last 7 days ≥ 10 for a stay month 30–90 days out | **HEALTHY** | Note positively; consider whether to hold or open rate |
| Strong pickup concentrated in one segment only | **CONCENTRATION RISK** | Check `by_segment` — if > 60% from one segment, flag dependency |

These thresholds apply to a hotel of this inventory size. Adjust the expectation
if the stay month has a known event or group block already filling rooms.

---

## Reading the by_segment breakdown

`get_pickup_delta` returns `by_segment` ordered by `new_total_revenue`. Use this to:

1. Identify which segments are driving recent pickup
2. Flag if a single segment accounts for > 60% of pickup revenue (concentration)
3. Compare to `get_segment_mix` for the same month to see if pickup mix matches
   the current OTB mix — a divergence signals a shift in demand source

---

## Pickup window boundary note

The booking window starts at **midnight Europe/London time** on the start day,
converted to UTC. This means a "last 7 days" window for a query run at 14:00 BST
on 25 June starts at 23:00 UTC on 17 June — not exactly 168 hours ago. Always
report the `window_start_utc` value from the tool, not a calculated estimate.

---

## Adversarial guardrail

Do not set `future_stay_from` to a past date when answering a question about
future demand. Including already-elapsed stay nights in the pickup count inflates
the numbers and misrepresents pace for future business. Set `future_stay_from`
to today's date unless the question explicitly asks about historical pickup for
past stay dates.

Do not confuse pickup with OTB. Pickup measures **what was added in a window**.
OTB measures **what currently exists**. A month can have strong OTB but slow
recent pickup — that is a pace deceleration signal, not a comfort signal.

---

## Answer pattern

"In the last [N] days, [X] new reservations were added for stays from [date]
forward — [Y] room nights worth £[Z]. [If healthy: pace is on track.] [If slow:
pickup is below expected pace for this lead time — recommend [action].] The
largest source of recent pickup is [top segment] at [share]% of new revenue."
