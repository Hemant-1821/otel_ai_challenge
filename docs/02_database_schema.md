# Database Schema Reference

## Connection

```
postgresql://hackathon:hackathon@localhost:5432/hotel_hackathon
```

(For hosted deployment: Supabase, Neon, or Railway)

---

## Tables Overview

| Table | Rows (after full load) | Purpose |
|-------|----------------------|---------|
| `reservations_hackathon` | Reconcile with `/verify` on scrape day | Main fact table |
| `room_type_lookup` | 3 rows | Room type codes |
| `rate_plan_lookup` | 8 rows | Rate plan codes |
| `market_code_lookup` | 10 rows | Market/segment codes |
| `market_macro_group_history` | 11 rows | Effective-dated macro groups |
| `channel_code_lookup` | 4 rows | Booking channel codes |
| `load_manifest` | ≥1 per ETL run | ETL audit trail |

> **Always reconcile `reservations_hackathon` row count against `/verify`** — do not assume static counts.

---

## THE MOST IMPORTANT CONCEPT: Table Grain

### `reservations_hackathon` is ONE ROW PER `reservation_id × stay_date`

- A 3-night reservation = **3 rows**
- A reservation with 2 rooms for 3 nights = **3 rows** (not 6), but `number_of_spaces = 2`
- Counting rows ≠ counting reservations
- Room nights = `SUM(number_of_spaces)` across rows (not row count)

**Example:** Guest books 2 rooms for 3 nights
- `reservation_count` = 1
- `stay_rows` = 3
- `room_nights` = 6 (3 rows × `number_of_spaces = 2`)

---

## 1. `public.reservations_hackathon` — Main Fact Table

```sql
create table if not exists public.reservations_hackathon (
  reservation_stay_id bigint generated always as identity primary key,
  reservation_id text not null,
  arrival_date date not null,
  departure_date date not null,
  stay_date date not null,
  property_date date not null,
  reservation_status text not null,
  financial_status text not null default 'Posted'
    check (financial_status in ('Posted', 'Provisional')),
  create_datetime timestamptz not null,
  cancellation_datetime timestamptz,
  guest_country text,
  is_block boolean not null default false,
  is_walk_in boolean not null default false,
  number_of_spaces integer not null check (number_of_spaces > 0),
  space_type text not null references public.room_type_lookup(space_type),
  market_code text not null references public.market_code_lookup(market_code),
  channel_code text not null references public.channel_code_lookup(channel_code),
  source_name text not null,
  rate_plan_code text not null references public.rate_plan_lookup(rate_plan_code),
  daily_room_revenue_before_tax numeric(10,2) not null default 0,
  daily_total_revenue_before_tax numeric(10,2) not null default 0,
  nights integer not null check (nights > 0),
  adr_room numeric(10,2) not null check (adr_room >= 0),
  lead_time integer not null check (lead_time >= 0),
  company_name text,
  travel_agent_name text,
  unique (reservation_id, stay_date)
);
```

### Column Reference

| Column | Type | Notes |
|--------|------|-------|
| `reservation_stay_id` | `bigint` | PK, unique row ID |
| `reservation_id` | `text` | Reservation ID — shared across multiple rows |
| `arrival_date` | `date` | Guest check-in date |
| `departure_date` | `date` | Guest check-out date (guest stays up to, not including, this date) |
| `stay_date` | `date` | **The specific night this row represents** — most important date for OTB analysis |
| `property_date` | `date` | Hotel business date — usually = `stay_date`; may differ on night-boundary/audit rows |
| `reservation_status` | `text` | `'Reserved'` or `'Cancelled'` — **exclude Cancelled for default OTB** |
| `financial_status` | `text` | `'Posted'` or `'Provisional'` — **exclude Provisional for default OTB** |
| `create_datetime` | `timestamptz` | When reservation was created (UTC) — use for pickup/pace/"what changed recently" |
| `cancellation_datetime` | `timestamptz` | When cancelled (nullable) — use for point-in-time OTB |
| `guest_country` | `text` | Guest nationality (nullable) |
| `is_block` | `boolean` | `true` = group/block reservation — use for group vs transient mix |
| `is_walk_in` | `boolean` | `true` = walk-in booking |
| `number_of_spaces` | `integer` | Number of rooms on this reservation for that stay date |
| `space_type` | `text` | Room type code → FK to `room_type_lookup` |
| `market_code` | `text` | Market/segment code → FK to `market_code_lookup` |
| `channel_code` | `text` | Booking channel code → FK to `channel_code_lookup` |
| `source_name` | `text` | Human-readable source (e.g. `Booking.com`, `Expedia`, `Brand website`) |
| `rate_plan_code` | `text` | Rate code → FK to `rate_plan_lookup` (e.g. `BOOKBAR`, `GROUPBB`, `DLY1`, `FITBB`) |
| `daily_room_revenue_before_tax` | `numeric(10,2)` | Room revenue for this stay night — use for **room-revenue questions** |
| `daily_total_revenue_before_tax` | `numeric(10,2)` | Total revenue (room + packages/breakfast) — use for **broader revenue questions** |
| `nights` | `integer` | Length of stay — repeated on all rows of the same reservation |
| `adr_room` | `numeric(10,2)` | Room ADR for the reservation — repeated across stay rows |
| `lead_time` | `integer` | Days between booking creation and arrival |
| `company_name` | `text` | Company name, especially for corporate/group (nullable) |
| `travel_agent_name` | `text` | Travel agent name (nullable) |

### Indexes

```sql
idx_res_hackathon_stay_date         -- on stay_date
idx_res_hackathon_property_date     -- on property_date
idx_res_hackathon_create_datetime   -- on create_datetime
idx_res_hackathon_market_code       -- on market_code
idx_res_hackathon_channel_code      -- on channel_code
idx_res_hackathon_reservation_status -- on reservation_status
idx_res_hackathon_financial_status  -- on financial_status
```

---

## 2. `public.room_type_lookup`

```sql
create table if not exists public.room_type_lookup (
  space_type text primary key,
  room_class text not null,
  display_name text not null,
  number_of_rooms integer not null check (number_of_rooms >= 0)
);
```

| Column | Notes |
|--------|-------|
| `space_type` | PK — join key from fact table |
| `room_class` | Broad class: `Standard`, `Executive` |
| `display_name` | Human-friendly room type name |
| `number_of_rooms` | Physical rooms of this type in the hotel (for supply/mix analysis) |

**3 rows total** after full load.

---

## 3. `public.market_code_lookup`

```sql
create table if not exists public.market_code_lookup (
  market_code text primary key,
  market_name text not null,
  macro_group text not null,
  description text
);
```

| Column | Notes |
|--------|-------|
| `market_code` | PK — join key from fact table |
| `market_name` | Human-readable segment name |
| `macro_group` | Broader grouping: `Retail`, `Corporate`, `MICE`, `Leisure`, `Leisure Group` |
| `description` | Plain-English description |

### Market Codes (10 total)

| Code | Meaning |
|------|---------|
| `OTA` | Online Travel Agency |
| `BAR` | Best Available Retail |
| `PROM` | Promotional Retail |
| `FIT` | Free Independent Traveller |
| `CSR` | Corporate Negotiated |
| `CNR` | Corporate Room Nights |
| `CNI` | Conference / Incentive Group |
| `CGR` | Corporate Group |
| `EVEN` | Event Demand |
| `SMERF` | SMERF Group |

> **Warning:** Do NOT use static `macro_group` from this table alone when history rows exist. Use `market_macro_group_history` joined on `stay_date`. (e.g. `PROM` may be reclassified mid-year.)

---

## 4. `public.market_macro_group_history`

```sql
create table if not exists public.market_macro_group_history (
  market_code text not null references public.market_code_lookup(market_code),
  valid_from date not null,
  valid_to date,      -- NULL = open-ended (still active)
  macro_group text not null,
  primary key (market_code, valid_from),
  check (valid_to is null or valid_to > valid_from)
);
```

**How to join:** `stay_date` between `valid_from` (inclusive) and `valid_to` (exclusive, NULL = open):

```sql
JOIN market_macro_group_history mmgh
  ON mmgh.market_code = r.market_code
  AND r.stay_date >= mmgh.valid_from
  AND (mmgh.valid_to IS NULL OR r.stay_date < mmgh.valid_to)
```

**11 rows total** after full load.

---

## 5. `public.channel_code_lookup`

```sql
create table if not exists public.channel_code_lookup (
  channel_code text primary key,
  channel_name text not null,
  channel_group text not null
);
```

| Column | Notes |
|--------|-------|
| `channel_code` | PK — join key from fact table |
| `channel_name` | Human-readable name |
| `channel_group` | Broad group: `Digital`, `Direct`, `Offline` |

**Channel codes (4 total):** `WEB`, `REC`, `EMA`, `WAL`

---

## 6. `public.rate_plan_lookup`

```sql
create table if not exists public.rate_plan_lookup (
  rate_plan_code text primary key,
  plan_family text not null,
  is_commissionable boolean not null default false
);
```

| Column | Notes |
|--------|-------|
| `rate_plan_code` | PK — join key from fact table |
| `plan_family` | e.g. `Retail`, `Group`, `Corporate` |
| `is_commissionable` | Channel economics flag |

**8 rows total** after full load. Example codes: `BOOKBAR`, `GROUPBB`, `DLY1`, `FITBB`

---

## 7. `public.load_manifest`

```sql
create table if not exists public.load_manifest (
  load_id bigint generated always as identity primary key,
  dataset_revision text not null,
  scraped_at timestamptz not null,
  source_url text not null,
  row_hash text not null,
  created_at timestamptz not null default now()
);
```

Append one row on **every ETL run**. Used by the `/health` endpoint.

---

## Joins Reference

| Join | Condition |
|------|-----------|
| Room type | `r.space_type = rtl.space_type` |
| Rate plan | `r.rate_plan_code = rpl.rate_plan_code` |
| Market segment | `r.market_code = mcl.market_code` |
| Market macro group (effective) | `mmgh.market_code = r.market_code AND r.stay_date >= mmgh.valid_from AND (mmgh.valid_to IS NULL OR r.stay_date < mmgh.valid_to)` |
| Channel | `r.channel_code = ccl.channel_code` |

---

## Default OTB Filters (Apply to Most Queries)

```sql
WHERE reservation_status != 'Cancelled'
  AND financial_status = 'Posted'
```

Always state assumption when question is ambiguous. Cancellation questions explicitly include `reservation_status = 'Cancelled'`.
