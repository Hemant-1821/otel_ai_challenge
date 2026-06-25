---
name: block_concentration
description: |
  Load this skill for any question about group vs transient mix, which companies
  are contributing the most revenue, whether business is concentrated in a few
  large bookings, or how dependent a month is on group business.
---

# Block / Group Concentration

## Tool to call

`get_block_vs_transient_mix(stay_month)` — returns the block/transient split,
`top_companies` (top 3 by revenue with NULL company mapped to 'Transient'), and
`top3_company_revenue_share` (combined share of month total revenue).

---

## Block share thresholds

| `block_share_of_revenue` | Signal | Action |
|---|---|---|
| > 60% | **HIGH group dependency** | One cancellation can materially damage the month; review contract attrition clauses |
| 40% – 60% | **BALANCED** — healthy group anchor | Monitor group attrition; no immediate action |
| < 40% | **TRANSIENT-DOMINANT** | Good rate flexibility, lower cancellation risk; consider whether to open group rates |

---

## Company concentration thresholds

`top3_company_revenue_share` measures how much of the month's total revenue sits
with the top 3 accounts (including 'Transient' as one entry).

| `top3_company_revenue_share` | Signal | Action |
|---|---|---|
| > 70% | **CRITICAL** concentration | Single-account risk; verify contract terms and attrition protection |
| 50% – 70% | **HIGH** | Flag in briefing; check if largest account has cancellation flexibility |
| < 50% | **DIVERSIFIED** | Healthy spread; note positively |

If a single company (excluding 'Transient') exceeds **30% of month revenue**,
flag it by name and recommend checking the contract attrition clause. A group
that size walking would leave a gap that transient pickup may not cover in time.

---

## Group vs transient interpretation

Group business (`is_block = true`) typically has:
- Higher room nights per reservation (multi-room blocks)
- Lower ADR than transient BAR rates (negotiated rates)
- Higher commitment risk (one cancellation = many room nights lost)

Transient business (`is_block = false`) typically has:
- Higher ADR
- Greater flexibility (no block commitment, but also no guarantee)

A high `block_share_of_room_nights` with a lower `block_share_of_revenue` than
expected signals the group business is coming in at a discount — worth flagging
alongside the ADR comparison.

---

## Adversarial guardrail

`top_companies` maps `NULL company_name` to 'Transient' — this represents all
individual bookings with no company attached. Do not interpret 'Transient' as a
single company. It is the aggregate of all non-corporate, non-group bookings. If
'Transient' is the top entry by revenue, that is a healthy sign of retail demand,
not a concentration risk.

---

## Answer pattern

"[Month] is [X]% group revenue and [Y]% transient. [If block > 60%: high group
dependency — the month is anchored by a small number of accounts.] The top
account contributes [Z]% of the month's revenue. [If single company > 30%: this
is above the 30% single-account threshold — recommend verifying the attrition
clause on that contract.] Top 3 accounts combined control [W]% of the month."
