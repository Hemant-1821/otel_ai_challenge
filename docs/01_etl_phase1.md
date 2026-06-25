# Phase 1 — ETL Pipeline (Scrape → Load)

## Core Principle

There is **no seed file** or CSV download. The reservation dataset lives on a public website rendered as HTML. We must build a scraper that extracts it and loads it into Postgres. This is deliberate — they want to see real ingestion engineering.

---

## Data Site Details

**URL:** `https://otel-hackathon-data-site.vercel.app`

### Pages to Scrape

| Page | URL Pattern | What to Get |
|------|-------------|-------------|
| Reservation list | `/reservations` | Paginated, **100 per page** — reservation IDs + basic fields |
| Reservation detail | `/reservations/<id>` | Per-night stay rows, `financial_status`, `property_date`, fields not on list view |
| Reference page | `/reference` | Room types, markets, channels, **rate plans**, macro-group effective dates |
| Verify page | `/verify` | Check your load counts after ETL |

### Critical: Client-Rendered Pages

- Pages are **client-rendered** (JavaScript) — `curl` returns an empty shell
- Must use a **real browser** — **Playwright is the expected choice**
- Must wait for content to render before scraping
- Must follow pagination through all list pages
- Must drill into each reservation's detail page

---

## ETL Steps

### 1. Extract (Scrape)
- Drive Playwright browser to the data site
- Paginate through `/reservations` list (100 per page) — capture all reservation IDs
- For each reservation, visit `/reservations/<id>` for per-night rows and detail-only fields
- Scrape `/reference` for all lookup table data and macro-group effective dates
- Check site footer for **dataset changelog** if scrape predates a deploy

### 2. Transform
- Parse HTML into clean, typed records matching `schema.sql`
- **Fact table grain:** one row per `reservation_id × stay_date` (not per reservation)
- Enforce correct types (dates, numerics, booleans, timestamptz)
- Build lookup table records: room types, rate plans, market codes, channels
- Build `market_macro_group_history` rows with `valid_from` / `valid_to` dates

### 3. Load
- Insert into Postgres tables
- Make load **idempotent** — truncate-and-reload OR upsert so re-runs don't create duplicates
- Append a row to `load_manifest` on **every run**: `dataset_revision`, `scraped_at`, `source_url`, `row_hash`

---

## Anchor Date — Critical

The data site regenerates from **today's date** (the anchor date):
- Row counts and OTB aggregates **shift when the anchor changes**
- **Scrape and reconcile against `/verify` on the same calendar day you load and submit**
- Re-run ETL on demand if you wipe the DB or need a fresh load
- We care that the pipeline is **correct, idempotent, and reproducible** for a given anchor date

---

## What Scores Well

- Robust scraper: handles pagination, list→detail drill-in, waits for rendered content, doesn't silently drop rows
- Verification step: check row counts and aggregates against `/verify` after loading
- Idempotency: anyone can run from scratch and get the same DB
- Clean separation of extract / transform / load with correct grain enforcement
- Tests covering edge cases (last page, single-night vs multi-night reservations, etc.)

---

## Phase 1 Deliverables

### `etl/SCRAPE_MANIFEST.json`

After scraping, commit a manifest proving you captured the full reservation list.

Required shape:
```json
{
  "anchor_date": "YYYY-MM-DD",
  "pages_scraped": 3,
  "reservation_ids_count": 254,
  "reservation_ids_sha256": "<sha256 of sorted reservation_id lines, one ID per line>"
}
```

- `reservation_ids_sha256` must match `count(distinct reservation_id)` in DB
- Must match `total_reservations` on `/verify`

### `etl/LOAD_PROOF.json`

Generate after ETL using the provided script:

```bash
pip install 'psycopg[binary]'
python scripts/compute_load_fingerprint.py --output etl/LOAD_PROOF.json

# Optional cross-check against manifest:
python scripts/compute_load_fingerprint.py \
  --manifest etl/SCRAPE_MANIFEST.json \
  --output etl/LOAD_PROOF.json
```

- Must match your hosted DB and the `/verify` page
- See `etl/LOAD_PROOF.example.json` for shape

---

## Phase 1 Checklist

- [ ] Playwright (or equivalent) scraper with pagination + list→detail drill-in
- [ ] Idempotent load into `schema.sql` shape
- [ ] `load_manifest` populated on every ETL run
- [ ] `etl/SCRAPE_MANIFEST.json` committed
- [ ] `etl/LOAD_PROOF.json` committed
- [ ] `tests/test_etl.py` with ≥3 cases covering published ETL scenarios (`tests/ETL_TEST_SCENARIOS.md`)
- [ ] Row counts reconciled with `/verify`

---

## Notes on Frequency

- Once per build is fine — no daily cron needed
- Book is stable within a calendar day
- Re-run if DB is wiped or you need a fresh load
- Reconcile against `/verify` on the **same day** you submit

---

## load_manifest Table (populated on every ETL run)

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
