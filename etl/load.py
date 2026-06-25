"""
Phase 1 — Load

Inserts transformed records into Postgres (schema.sql tables).
Design rules:
  - Fully idempotent: every table uses INSERT ... ON CONFLICT DO UPDATE.
    No TRUNCATE — avoids FK constraint ordering issues entirely.
  - Source never hard-deletes rows (cancellations become status='Cancelled'),
    so upsert produces the same result as truncate-and-reload.
  - Appends one row to load_manifest on every run.
  - Load order respects FK constraints (parents inserted before children):
      1. room_type_lookup
      2. rate_plan_lookup
      3. market_code_lookup
      4. channel_code_lookup
      5. market_macro_group_history   (references market_code_lookup)
      6. reservations_hackathon       (references all 4 lookups)
      7. load_manifest                (audit row)
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import psycopg

SOURCE_URL = "https://otel-hackathon-data-site.vercel.app"


def load_lookup_tables(conn, transformed: dict) -> None:
    """Upsert all lookup tables in FK-safe order (parents before children)."""
    with conn.cursor() as cur:

        # 1. room_type_lookup
        cur.executemany(
            """INSERT INTO public.room_type_lookup
               (space_type, room_class, display_name, number_of_rooms)
               VALUES (%(space_type)s, %(room_class)s,
                       %(display_name)s, %(number_of_rooms)s)
               ON CONFLICT (space_type) DO UPDATE SET
                   room_class       = EXCLUDED.room_class,
                   display_name     = EXCLUDED.display_name,
                   number_of_rooms  = EXCLUDED.number_of_rooms""",
            transformed["room_type_lookup"],
        )

        # 2. rate_plan_lookup
        cur.executemany(
            """INSERT INTO public.rate_plan_lookup
               (rate_plan_code, plan_family, is_commissionable)
               VALUES (%(rate_plan_code)s, %(plan_family)s, %(is_commissionable)s)
               ON CONFLICT (rate_plan_code) DO UPDATE SET
                   plan_family       = EXCLUDED.plan_family,
                   is_commissionable = EXCLUDED.is_commissionable""",
            transformed["rate_plan_lookup"],
        )

        # 3. market_code_lookup
        cur.executemany(
            """INSERT INTO public.market_code_lookup
               (market_code, market_name, macro_group, description)
               VALUES (%(market_code)s, %(market_name)s,
                       %(macro_group)s, %(description)s)
               ON CONFLICT (market_code) DO UPDATE SET
                   market_name  = EXCLUDED.market_name,
                   macro_group  = EXCLUDED.macro_group,
                   description  = EXCLUDED.description""",
            transformed["market_code_lookup"],
        )

        # 4. channel_code_lookup
        cur.executemany(
            """INSERT INTO public.channel_code_lookup
               (channel_code, channel_name, channel_group)
               VALUES (%(channel_code)s, %(channel_name)s, %(channel_group)s)
               ON CONFLICT (channel_code) DO UPDATE SET
                   channel_name  = EXCLUDED.channel_name,
                   channel_group = EXCLUDED.channel_group""",
            transformed["channel_code_lookup"],
        )

        # 5. market_macro_group_history (depends on market_code_lookup)
        cur.executemany(
            """INSERT INTO public.market_macro_group_history
               (market_code, valid_from, valid_to, macro_group)
               VALUES (%(market_code)s, %(valid_from)s,
                       %(valid_to)s, %(macro_group)s)
               ON CONFLICT (market_code, valid_from) DO UPDATE SET
                   valid_to    = EXCLUDED.valid_to,
                   macro_group = EXCLUDED.macro_group""",
            transformed["market_macro_group_history"],
        )


def load_reservations(conn, stay_rows: list[dict]) -> int:
    """
    Upsert stay rows into reservations_hackathon.
    Conflict key: (reservation_id, stay_date).
    Returns the number of rows processed.
    """
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO public.reservations_hackathon (
                reservation_id, arrival_date, departure_date,
                stay_date, property_date,
                reservation_status, financial_status,
                create_datetime, cancellation_datetime,
                guest_country, is_block, is_walk_in,
                number_of_spaces, space_type,
                market_code, channel_code, source_name, rate_plan_code,
                daily_room_revenue_before_tax, daily_total_revenue_before_tax,
                nights, adr_room, lead_time,
                company_name, travel_agent_name
            ) VALUES (
                %(reservation_id)s, %(arrival_date)s, %(departure_date)s,
                %(stay_date)s, %(property_date)s,
                %(reservation_status)s, %(financial_status)s,
                %(create_datetime)s, %(cancellation_datetime)s,
                %(guest_country)s, %(is_block)s, %(is_walk_in)s,
                %(number_of_spaces)s, %(space_type)s,
                %(market_code)s, %(channel_code)s, %(source_name)s, %(rate_plan_code)s,
                %(daily_room_revenue_before_tax)s, %(daily_total_revenue_before_tax)s,
                %(nights)s, %(adr_room)s, %(lead_time)s,
                %(company_name)s, %(travel_agent_name)s
            )
            ON CONFLICT (reservation_id, stay_date) DO UPDATE SET
                arrival_date                   = EXCLUDED.arrival_date,
                departure_date                 = EXCLUDED.departure_date,
                property_date                  = EXCLUDED.property_date,
                reservation_status             = EXCLUDED.reservation_status,
                financial_status               = EXCLUDED.financial_status,
                create_datetime                = EXCLUDED.create_datetime,
                cancellation_datetime          = EXCLUDED.cancellation_datetime,
                guest_country                  = EXCLUDED.guest_country,
                is_block                       = EXCLUDED.is_block,
                is_walk_in                     = EXCLUDED.is_walk_in,
                number_of_spaces               = EXCLUDED.number_of_spaces,
                space_type                     = EXCLUDED.space_type,
                market_code                    = EXCLUDED.market_code,
                channel_code                   = EXCLUDED.channel_code,
                source_name                    = EXCLUDED.source_name,
                rate_plan_code                 = EXCLUDED.rate_plan_code,
                daily_room_revenue_before_tax  = EXCLUDED.daily_room_revenue_before_tax,
                daily_total_revenue_before_tax = EXCLUDED.daily_total_revenue_before_tax,
                nights                         = EXCLUDED.nights,
                adr_room                       = EXCLUDED.adr_room,
                lead_time                      = EXCLUDED.lead_time,
                company_name                   = EXCLUDED.company_name,
                travel_agent_name              = EXCLUDED.travel_agent_name""",
            stay_rows,
        )
        return len(stay_rows)


def _compute_row_hash(stay_rows: list[dict]) -> str:
    """SHA-256 of sorted reservation_id|stay_date pairs."""
    pairs = sorted(
        f"{r['reservation_id']}|{r['stay_date'].isoformat()}" for r in stay_rows
    )
    return hashlib.sha256("\n".join(pairs).encode()).hexdigest()


def append_load_manifest(
    conn,
    dataset_revision: str,
    scraped_at: str,
    source_url: str,
    row_hash: str,
) -> None:
    """Append one audit row to load_manifest."""
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO public.load_manifest
               (dataset_revision, scraped_at, source_url, row_hash)
               VALUES (%s, %s, %s, %s)""",
            (dataset_revision, scraped_at, source_url, row_hash),
        )


def run_load(transformed: dict, db_url: str) -> None:
    """
    Entry point: load all transformed data in a single transaction.
    Rolls back everything on any error.
    """
    stay_rows = transformed["reservations"]
    anchor_date = transformed["manifest"]["anchor_date"]

    with psycopg.connect(db_url) as conn:
        load_lookup_tables(conn, transformed)
        print(
            f"[load] lookups upserted"
            f"  room_types={len(transformed['room_type_lookup'])}"
            f"  rate_plans={len(transformed['rate_plan_lookup'])}"
            f"  markets={len(transformed['market_code_lookup'])}"
            f"  channels={len(transformed['channel_code_lookup'])}"
            f"  macro_history={len(transformed['market_macro_group_history'])}"
        )

        n = load_reservations(conn, stay_rows)
        print(f"[load] reservations_hackathon: {n} rows upserted")

        row_hash = _compute_row_hash(stay_rows)
        append_load_manifest(
            conn,
            dataset_revision=anchor_date,
            scraped_at=datetime.now(timezone.utc).isoformat(),
            source_url=SOURCE_URL,
            row_hash=row_hash,
        )
        print(f"[load] load_manifest appended  row_hash={row_hash[:16]}…")
