---
name: adr_yield
description: |
  Load this skill for any question about ADR, average daily rate, which room
  type is performing best or worst on rate, whether rates are holding, or any
  rate optimisation recommendation.
---

# ADR & Yield Optimisation

## Tool to call

`get_otb_summary(stay_month)` returns overall room revenue and room nights.
Derive ADR as:

```
ADR = room_revenue / room_nights
    = get_otb_summary.room_revenue / get_otb_summary.room_nights
```

**For room-type breakdown** (best/worst room type by ADR or revenue):

```
get_otb_summary(stay_month, breakdown="room_type")
```

Returns `breakdown_rows` — one entry per `space_type` with `display_name`,
`room_class`, `room_nights`, `room_revenue`, `total_revenue`, and `adr`
(pre-derived as `room_revenue / room_nights`). Sorted by `total_revenue` desc.
Use `adr` from each row to rank room types; compare against the floor thresholds
in the table below. Never use `get_segment_mix` for room-type ADR questions —
segments are market codes, not room types.

For group vs transient ADR comparison: call `get_block_vs_transient_mix` for
revenue and room nights, then derive ADR for each:

```
block_adr     = block_total_revenue / block_room_nights
transient_adr = transient_total_revenue / transient_room_nights
```

---

## ADR floor thresholds

| Room class | ADR floor | Signal if below | Action |
|---|---|---|---|
| Standard | £120 | Rate is below cost-recovery threshold | Close discounted OTA rates; hold BAR |
| Executive | £180 | Executive premium not being captured | Review upgrade pricing; restrict low-rate availability |
| Overall blended | £140 | Blended rate too low given mix | Audit segment ADR; identify which segment is diluting the average |

These floors are reference points — adjust if the GM provides property-specific
benchmarks. Flag when ADR is below floor; do not silently pass over it.

---

## Group ADR discount assessment

Group/block ADR is typically 10–25% below transient BAR ADR for a city property.

| Group ADR vs transient ADR | Signal | Action |
|---|---|---|
| Group ADR < 70% of transient ADR | **Over-discounted** | Review group rate agreements; consider raising minimum group rate |
| Group ADR 75% – 90% of transient ADR | **Normal** — acceptable group discount | No action; note the discount level |
| Group ADR > 90% of transient ADR | **Excellent** | Group is close to rack rate; positive signal |

---

## Yield interpretation

High occupancy with low ADR is a yield problem — the hotel is full but leaving
revenue on the table. Signals:

- `room_nights` is high but `room_revenue / room_nights` is below floor
- OTA share is high (OTA negotiated rates are typically lower than BAR)
- Group share is high with a deep discount

Recommendation pattern: "Occupancy is strong but blended ADR of £[X] is below
the £[floor] floor. OTA and group mix are diluting the rate. Recommend closing
discounted OTA availability for [month] and holding BAR at £[target]."

---

## Adversarial guardrail

Never `SUM(adr_room)` or average `adr_room` directly across rows. `adr_room` is
a reservation-level field repeated on every stay-date row — summing or averaging
it produces a nonsense figure that is weighted by length of stay, not by room
nights. Always derive ADR from `room_revenue / room_nights` using the tool output.

---

## Answer pattern

"Blended ADR for [month] is £[X] ([room_revenue] ÷ [room_nights] room nights).
[If below floor: this is below the £[floor] floor — [action].] Group ADR is
£[Y] vs transient ADR of £[Z] — a [%] discount. [Assessment and recommendation.]"
