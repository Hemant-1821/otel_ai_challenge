---
name: challenge_skill
description: |
  otel-rm-v2
  Load this skill to understand the full Revenue Manager Agent skill pack:
  what skills are available, which tools each skill routes to, and when each
  skill should be loaded. This is the master index for the otel-rm-v2 pack.
---

# Revenue Manager Agent — Skill Pack otel-rm-v2

## Available skills and when to load them

| Skill | Load when | Primary tool |
|---|---|---|
| `grain_rules` | Any counting, aggregation, ADR, or metric calculation question | `get_otb_summary`, `get_block_vs_transient_mix` |
| `otb_filters` | Any OTB, revenue-on-books, cancelled business, or point-in-time question | `get_otb_summary`, `get_as_of_otb` |
| `rm_answer_style` | Composing any final answer for the GM | All tools |
| `ota_concentration` | OTA dependency, segment mix, which segments are driving a month | `get_segment_mix` |
| `cancellation_pace` | Cancellation volume, cancellation rate, lost business | `get_otb_summary` |
| `pickup_interpretation` | What changed recently, pickup in last N days, booking pace | `get_pickup_delta` |
| `block_concentration` | Group vs transient, company concentration, large bookings | `get_block_vs_transient_mix` |
| `adr_yield` | ADR, room type rates, yield optimisation, rate floors | `get_otb_summary`, `get_block_vs_transient_mix` |

---

## The five required tools

| Tool | What it returns | HITL |
|---|---|---|
| `get_otb_summary(stay_month, exclude_cancelled)` | Reservation count, room nights, revenue for a month | No |
| `get_segment_mix(stay_month, macro_group)` | Segment breakdown with revenue shares | No |
| `get_pickup_delta(booking_window_days, future_stay_from)` | New bookings in a window for future stays | No |
| `get_as_of_otb(stay_month, as_of_utc)` | Point-in-time OTB rebuild | **Yes — GM approval required** |
| `get_block_vs_transient_mix(stay_month)` | Block/transient split, top companies, concentration | No |

Never query `reservations_hackathon` directly. All tools read from semantic views.

---

## Example questions and skill + tool routing

| Question | Skill | Tool |
|---|---|---|
| What revenue is on the books by month? | `otb_filters` | `get_otb_summary` |
| Which segments are driving July? | `ota_concentration` | `get_segment_mix` |
| How much of July is group business? | `block_concentration` | `get_block_vs_transient_mix` |
| Are we too dependent on OTA? | `ota_concentration` | `get_segment_mix` |
| What changed in the last 7 days? | `pickup_interpretation` | `get_pickup_delta` |
| Which room type has the highest ADR? | `adr_yield` + `grain_rules` | `get_otb_summary` |
| How much business was cancelled in June? | `cancellation_pace` | `get_otb_summary` (×2) |
| What share of future business is corporate? | `ota_concentration` | `get_segment_mix` |
| Which companies contribute most revenue? | `block_concentration` | `get_block_vs_transient_mix` |
| Is business concentrated in a few bookings? | `block_concentration` | `get_block_vs_transient_mix` |
