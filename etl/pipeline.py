"""
Phase 1 — ETL Pipeline Entry Point

Runs the full Extract → Transform → Load sequence and writes:
  - etl/raw/list_items.json    (reservation summaries from list API)
  - etl/raw/details.json       (full detail payloads with stay_rows)
  - etl/raw/reference.json     (all 5 reference lookup tables)
  - etl/SCRAPE_MANIFEST.json   (proof of full extraction)

Skips extraction if the DB already reflects today's verified dataset.

Usage:
    python -m etl.pipeline

Environment variables:
    DATABASE_URL   — Postgres connection string
                     defaults to the local Docker DB from docker-compose.yml
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

import psycopg
from dotenv import load_dotenv

load_dotenv()

ETL_DIR = Path(__file__).parent
MANIFEST_PATH = ETL_DIR / "SCRAPE_MANIFEST.json"

_DEFAULT_DB_URL = "postgresql://hackathon:hackathon@localhost:5432/hotel_hackathon"

# Static snapshot from /verify for today's anchor date.
# Re-paste if the anchor date changes.
VERIFY_SNAPSHOT = {
    "anchor_date": "2026-06-26",
    "dataset_revision": "2026.06.12.2",
    "total_reservations": 254,
    "total_stay_rows": 528,
    "reservation_stay_status_sha256": "f4dce18ab893a3eebc978f82e8e0e4a91ddbc0439bcdeb4061293b76cd955014",
}


def _db_is_current(db_url: str) -> bool:
    """
    Return True if the DB already holds the expected data for today's anchor.
    Checks:
      1. SCRAPE_MANIFEST.json exists with the correct anchor_date + reservation count
      2. reservations_hackathon row count matches total_stay_rows from /verify
    """
    expected_anchor = VERIFY_SNAPSHOT["anchor_date"]
    expected_reservations = VERIFY_SNAPSHOT["total_reservations"]
    expected_stay_rows = VERIFY_SNAPSHOT["total_stay_rows"]

    # 1. Manifest check
    if not MANIFEST_PATH.exists():
        print("[skip-check] SCRAPE_MANIFEST.json not found — will extract.")
        return False

    manifest = json.loads(MANIFEST_PATH.read_text())
    if manifest.get("anchor_date") != expected_anchor:
        print(
            f"[skip-check] manifest anchor_date={manifest.get('anchor_date')} "
            f"!= expected {expected_anchor} — will extract."
        )
        return False
    if manifest.get("reservation_ids_count") != expected_reservations:
        print(
            f"[skip-check] manifest count={manifest.get('reservation_ids_count')} "
            f"!= expected {expected_reservations} — will extract."
        )
        return False

    # 2. DB row count check
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM public.reservations_hackathon")
                db_count = cur.fetchone()[0]
    except Exception as exc:
        print(f"[skip-check] DB query failed ({exc}) — will extract.")
        return False

    if db_count != expected_stay_rows:
        print(
            f"[skip-check] DB has {db_count} stay rows, "
            f"expected {expected_stay_rows} — will load."
        )
        return False

    print(
        f"[skip-check] DB is current "
        f"(anchor={expected_anchor}, reservations={expected_reservations}, "
        f"stay_rows={db_count}) — skipping extract + load."
    )
    return True


async def main() -> None:
    db_url = os.getenv("DATABASE_URL", _DEFAULT_DB_URL)

    print("=" * 60)
    print(f"ETL Pipeline  —  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 60)

    if _db_is_current(db_url):
        print("\n✓ Nothing to do.")
        return

    # Inject dataset_revision from verify snapshot into the raw manifest
    # so load.py can store the correct value in load_manifest (not the anchor date)

    # ── Extract ───────────────────────────────────────────────────
    print("\n── EXTRACT ──────────────────────────────────────────────")
    from etl.extract import run_extract
    raw = await run_extract()
    raw["manifest"]["dataset_revision"] = VERIFY_SNAPSHOT["dataset_revision"]

    reservation_count = len(raw["list_items"])
    stay_row_count = sum(len(d.get("stay_rows", [])) for d in raw["details"])
    print(f"\n   reservations  : {reservation_count}")
    print(f"   stay rows     : {stay_row_count}")
    print(f"   manifest sha  : {raw['manifest']['reservation_ids_sha256'][:16]}…")

    # ── Transform ─────────────────────────────────────────────────
    print("\n── TRANSFORM ────────────────────────────────────────────")
    from etl.transform import run_transform
    transformed = run_transform(raw)

    print(f"   room_type_lookup           : {len(transformed['room_type_lookup'])} rows")
    print(f"   rate_plan_lookup           : {len(transformed['rate_plan_lookup'])} rows")
    print(f"   market_code_lookup         : {len(transformed['market_code_lookup'])} rows")
    print(f"   channel_code_lookup        : {len(transformed['channel_code_lookup'])} rows")
    print(f"   market_macro_group_history : {len(transformed['market_macro_group_history'])} rows")
    print(f"   reservations_hackathon     : {len(transformed['reservations'])} rows")

    # ── Load ──────────────────────────────────────────────────────
    print("\n── LOAD ─────────────────────────────────────────────────")
    print(f"   db : {db_url}")
    from etl.load import run_load
    run_load(transformed, db_url)

    # ── Done ──────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("✓ Pipeline complete.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
