---
name: cancellation_pace
description: |
  Load this skill for any question about cancellations, cancellation rate,
  how much business was lost, or whether cancellation pace is accelerating.
  Defines how to measure cancellation volume using available tools and when
  to recommend overbooking adjustments.
---

# Cancellation Pace

## Tool to call

There is no dedicated cancellation tool. Use `get_otb_summary` with both flag
values and subtract to derive cancellation volume:

```
get_otb_summary(stay_month, exclude_cancelled=False)  →  all_posted
get_otb_summary(stay_month, exclude_cancelled=True)   →  active_otb

cancelled_room_nights  = all_posted.room_nights  - active_otb.room_nights
cancelled_reservations = all_posted.reservation_count - active_otb.reservation_count
cancelled_revenue      = all_posted.total_revenue - active_otb.total_revenue
```

Always make two tool calls and show the delta explicitly. Do not estimate.

---

## Cancellation rate

```
cancellation_rate = cancelled_room_nights / all_posted.room_nights
```

| Cancellation rate | Signal | Action |
|---|---|---|
| > 20% of ever-booked room nights | **HIGH** — significant attrition | Review overbooking policy; consider BAR rate hold |
| 10% – 20% | **MODERATE** — within normal range | Monitor weekly; no immediate action |
| < 10% | **LOW** — strong commitment | Note positively; may indicate corporate or contract business |

---

## Cancellation revenue impact

Cancelled revenue is `all_posted.total_revenue - active_otb.total_revenue`.
Report it as a pound value and as a percentage of the total ever-booked revenue.
A high-revenue cancellation from a single company is more dangerous than many
small cancellations — cross-reference with `get_block_vs_transient_mix` to check
if the cancellations are concentrated in group business.

---

## Adversarial guardrail

Do not answer a cancellation question using only `get_otb_summary` with the
default `exclude_cancelled=True`. That returns only active business and makes
cancellations invisible. You must call it with `exclude_cancelled=False` to see
the full picture.

Do not confuse `cancellation_datetime` with `create_datetime`. Cancellation pace
is measured by when bookings were cancelled, but our standard tools use
`create_datetime` for window filtering. For a point-in-time view of what was
cancelled before a specific date, use `get_as_of_otb` (requires GM approval).

---

## Answer pattern

"In [month], [X] room nights were cancelled out of [Y] ever-booked — a [Z]%
cancellation rate. This represents £[W] in lost revenue. [If > 20%: cancellation
rate is above the 20% threshold — recommend reviewing overbooking levels for
the month.] [If group-concentrated: the cancellations appear concentrated in
group business — use get_block_vs_transient_mix to identify which accounts.]"
