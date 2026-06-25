# Business Concepts & Domain Knowledge

## Hotel Revenue Management Glossary

| Term | Definition |
|------|-----------|
| **Reservation** | A hotel booking |
| **Stay date** | The actual night being stayed |
| **Arrival date** | Date the guest checks in |
| **Departure date** | Date the guest checks out (guest stays *up to, not including* this date) |
| **Booking date** | When the reservation was created = `create_datetime` |
| **OTB / On-the-books** | Business that currently exists for future stay dates (active, non-cancelled) |
| **ADR** | Average Daily Rate — revenue per room night |
| **Room nights** | Rooms × nights occupied (1 room for 3 nights = 3; 2 rooms for 3 nights = 6) |
| **OTA** | Online Travel Agency (Booking.com, Expedia, etc.) |
| **Direct** | Business via hotel's own website / reservations / walk-ins |
| **Group business** | Multi-room bookings for conferences, corporate groups, events — filter by `is_block = true` |
| **Transient business** | Normal individual bookings — `is_block = false` |
| **Lead time** | Days between `create_datetime` and `arrival_date` |
| **Pickup** | New reservations added in a window of time for future stay dates |
| **Booking pace** | Rate at which reservations accumulate for a future date |
| **Cancellation** | Reservation that was cancelled — `reservation_status = 'Cancelled'` |
| **Concentration risk** | Business too dependent on one segment, channel, company, or few large bookings |
| **Segment mix** | Distribution of business across market segments (OTA, Corporate, etc.) |

---

## The #1 Concept: Table Grain

`reservations_hackathon` is **ONE ROW PER RESERVATION × STAY_DATE**

| Question | Wrong approach | Right approach |
|----------|----------------|----------------|
| How many reservations? | `COUNT(*)` | `COUNT(DISTINCT reservation_id)` |
| How many room nights? | `COUNT(*)` or `COUNT(DISTINCT reservation_id)` | `SUM(number_of_spaces)` |
| Revenue for July? | `SUM(daily_room_revenue_before_tax)` on all rows | Same, but filtered to `stay_date` in July — this is correct because each row IS a stay night |

---

## Date Fields — Which to Use When

| Field | Use For | Stored As |
|-------|---------|-----------|
| `stay_date` | Revenue-on-stay, monthly OTB, segment mix by stay month | `date` |
| `create_datetime` | Pickup, booking pace, "what was booked recently", "as-of" views | `timestamptz` (UTC) |
| `property_date` | Hotel business-date attribution when it differs from `stay_date` | `date` |
| `cancellation_datetime` | Point-in-time OTB (`get_as_of_otb`) | `timestamptz`, nullable |

**Key rule:** `stay_date` is almost always what you want for revenue/OTB analysis. `create_datetime` is for pickup/pace analysis.

**Pickup windows (`get_pickup_delta`):** use `Europe/London` local midnight as window boundaries, then compare against `create_datetime` in UTC.

---

## Revenue Fields — Which to Use

| Field | Use For |
|-------|---------|
| `daily_room_revenue_before_tax` | Room-only revenue questions |
| `daily_total_revenue_before_tax` | Broader revenue questions (room + packages + breakfast effects) |

**ADR calculation:**
```sql
SUM(daily_room_revenue_before_tax) / SUM(number_of_spaces)  -- per room night
```

Or use `adr_room` (repeated on all rows of same reservation) — but be careful not to sum it.

---

## Default OTB Filters

**Always apply these unless the question explicitly asks otherwise:**

```sql
WHERE reservation_status != 'Cancelled'   -- exclude cancelled
  AND financial_status = 'Posted'          -- exclude provisional
```

**When NOT to apply:**
- Cancellation analysis: include `reservation_status = 'Cancelled'`
- Tentative/provisional analysis: include `financial_status = 'Provisional'`
- Always state your assumption when a question is ambiguous

---

## Market Macro Groups

Use `market_macro_group_history` (NOT the static `macro_group` column in `market_code_lookup`) for correct effective-dated grouping:

```sql
JOIN market_macro_group_history mmgh
  ON mmgh.market_code = r.market_code
  AND r.stay_date >= mmgh.valid_from
  AND (mmgh.valid_to IS NULL OR r.stay_date < mmgh.valid_to)
```

Why: `PROM` and other codes may be **reclassified mid-year** — the history table captures this correctly.

---

## Group vs Transient

| Type | How to Identify |
|------|----------------|
| Group/Block | `is_block = true` |
| Transient | `is_block = false` |

Group business often includes `CGR` (Corporate Group), `CNI` (Conference/Incentive), `SMERF`, `EVEN` market codes.

---

## OTA vs Direct

| Type | Common Sources | Market Codes |
|------|---------------|--------------|
| OTA | Booking.com, Expedia | `OTA` |
| Direct | Brand website, CRO, walk-ins | `BAR`, `FIT`, `CSR` |

OTA dependency risk: what % of future revenue comes from OTA? High concentration = rate parity pressure, commission cost risk.

---

## Common Pitfalls Summary

1. **Rows ≠ Reservations:** always `COUNT(DISTINCT reservation_id)` for reservation counts
2. **Rooms × Nights:** `SUM(number_of_spaces)` for room nights (a reservation can cover multiple rooms)
3. **Cancelled bookings:** exclude `reservation_status = 'Cancelled'` by default
4. **Wrong date field:** use `stay_date` for OTB/revenue, `create_datetime` for pickup/pace
5. **Wrong revenue field:** `daily_room_revenue_before_tax` vs `daily_total_revenue_before_tax`
6. **Static macro_group:** use `market_macro_group_history` join, not `market_code_lookup.macro_group`
7. **`adr_room` is repeated:** don't `SUM(adr_room)` — it's the same value repeated across a reservation's stay rows

---

## Answer Style — What a Good Answer Looks Like

A good answer from the agent is **not** raw SQL output or a data dump. It should:

- Sound like a **sharp revenue manager in a morning briefing**
- Name the top drivers and quantify them
- Highlight risks or opportunities
- Compare to context (prior period, thresholds, benchmarks)
- Mention assumptions or caveats
- Recommend an action

**Weak answer:** "OTA revenue is £45,230 for July."

**Strong answer:** "OTA is your largest segment for July at £45,230 (38% of July revenue), up from 31% last year. This concentration above 35% creates rate parity pressure — Booking.com and Expedia may push back on rate increases. I'd recommend reviewing your BAR rate strategy and running a direct-booking promotion to shift the mix before peak season."

---

## Business Definitions to Standardize

Define these explicitly in your tools/skills (do not improvise per query):

| Metric | Definition |
|--------|-----------|
| Reservation count | `COUNT(DISTINCT reservation_id)` where `reservation_status != 'Cancelled'` AND `financial_status = 'Posted'` |
| Room nights | `SUM(number_of_spaces)` across active stay rows |
| Revenue | `SUM(daily_total_revenue_before_tax)` for total; `SUM(daily_room_revenue_before_tax)` for room only |
| ADR | `SUM(daily_room_revenue_before_tax) / SUM(number_of_spaces)` |
| OTB | Active reservations for future `stay_date` (non-cancelled, Posted) |
| Pickup | New reservations created within a booking window for future stay dates |

---

## Final Advice for Building Tools/Skills

1. Decide: is this question about **stay date** or **booking date**?
2. Be explicit: are cancelled reservations **included or excluded**?
3. Use clear, consistent business definitions — not improvised SQL
4. Return answers in **plain English**, not raw query output
5. When there is ambiguity, **state your assumption**
