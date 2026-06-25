---
name: ota_concentration
description: |
  Load this skill for any question about OTA dependency, segment mix, which
  segments are driving a month, or what share of revenue comes from a specific
  channel or macro group. Encodes OTA concentration thresholds and recommended
  actions for each risk level.
---

# OTA Concentration & Segment Mix

## Tool to call

`get_segment_mix(stay_month, macro_group=None)` — returns all segments with
`share_of_revenue` and `share_of_room_nights` pre-calculated against the correct
denominator. For a specific macro group (e.g. Corporate), pass `macro_group`.

For "what share is corporate?" call `get_segment_mix` without a filter and read
the Corporate rows, or call with `macro_group='Corporate'` to see only that group.

---

## OTA concentration thresholds

| OTA share of total revenue | Risk level | Action |
|---|---|---|
| > 35% | **HIGH** | Flag immediately; recommend direct-booking promotion |
| 25% – 35% | **MODERATE** | Monitor; review rate parity agreements |
| < 25% | **HEALTHY** | Note positively in briefing |

OTA commissions are typically 15–20% of room revenue. High OTA share compounds:
more revenue, more commission cost, and more rate parity pressure all at once.

**When OTA share exceeds 35%:** quantify the commission exposure
(`OTA_revenue × 0.175` as a midpoint estimate), name the specific OTA sources
from `source_name` if available, and recommend a direct-booking promotion or
BAR rate adjustment to incentivise the brand website channel.

---

## Segment mix interpretation

When answering "which segments are driving [month]?" use `get_segment_mix` and
report the top 3 segments by `share_of_revenue`. Structure the answer as:

1. Largest segment + share
2. Second segment + share
3. Any concentration risk (single segment > 40% of revenue)
4. Recommended action if risk threshold is breached

**Corporate share guidance:**  
Corporate (`CSR`, `CNR`) > 30% of revenue is healthy for a city-centre business
hotel. If corporate share drops below 20%, flag potential demand softness in the
corporate segment and recommend a rate review for negotiated accounts.

**MICE / Events guidance:**  
`CNI`, `CGR`, `EVEN` macro group represents contracted group business. A single
MICE event > 25% of a month's revenue creates concentration risk — if it cancels,
the month has a significant gap. Flag with `get_block_vs_transient_mix` for the
company-level view.

---

## Adversarial guardrail

Do not use the static `macro_group` column from `market_code_lookup` to classify
segments. Market codes are reclassified mid-year in `market_macro_group_history`.
`get_segment_mix` resolves `effective_macro_group` correctly — trust its output,
do not re-derive groupings manually.

---

## Answer pattern

"OTA is your [X]% of [month] revenue — [above/within/below] the 35% threshold.
[If above: this creates rate parity pressure and estimated £Y in commission cost.
Recommend: direct-booking promotion targeting [month].] [If below: healthy mix —
no action required.]"
