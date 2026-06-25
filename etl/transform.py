"""
Phase 1 — Transform

Takes raw dicts from extract.py and converts them into clean, typed records
matching schema.sql. Enforces:
  - Correct grain: one record per reservation_id × stay_date
  - Correct types: dates, numerics, booleans, timestamptz
  - Lookup table records: room types, rate plans, market codes, channels
  - market_macro_group_history rows with valid_from / valid_to
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal


# ── Lookup tables ─────────────────────────────────────────────────────────────

def transform_room_types(raw_reference: dict) -> list[dict]:
    """
    Extract room_type_lookup records from reference data.
    Schema: space_type (PK), room_class, display_name, number_of_rooms (int)
    """
    return [
        {
            "space_type": row["space_type"],
            "room_class": row["room_class"],
            "display_name": row["display_name"],
            "number_of_rooms": int(row["number_of_rooms"]),
        }
        for row in raw_reference["room_type_lookup"]
    ]


def transform_rate_plans(raw_reference: dict) -> list[dict]:
    """
    Extract rate_plan_lookup records from reference data.
    Schema: rate_plan_code (PK), plan_family, is_commissionable (bool)
    is_commissionable arrives as the string "true" or "false".
    """
    return [
        {
            "rate_plan_code": row["rate_plan_code"],
            "plan_family": row["plan_family"],
            "is_commissionable": row["is_commissionable"].strip().lower() == "true",
        }
        for row in raw_reference["rate_plan_lookup"]
    ]


def transform_market_codes(raw_reference: dict) -> list[dict]:
    """
    Extract market_code_lookup records from reference data.
    Schema: market_code (PK), market_name, macro_group, description (nullable)
    """
    return [
        {
            "market_code": row["market_code"],
            "market_name": row["market_name"],
            "macro_group": row["macro_group"],
            "description": row.get("description") or None,
        }
        for row in raw_reference["market_code_lookup"]
    ]


def transform_channel_codes(raw_reference: dict) -> list[dict]:
    """
    Extract channel_code_lookup records from reference data.
    Schema: channel_code (PK), channel_name, channel_group
    """
    return [
        {
            "channel_code": row["channel_code"],
            "channel_name": row["channel_name"],
            "channel_group": row["channel_group"],
        }
        for row in raw_reference["channel_code_lookup"]
    ]


def transform_macro_group_history(raw_reference: dict) -> list[dict]:
    """
    Extract market_macro_group_history records from reference data.
    Schema: market_code, valid_from (date), valid_to (date | NULL), macro_group
    valid_to = "—" (em dash) in the source means open-ended → NULL.
    """
    records = []
    for row in raw_reference["market_macro_group_history"]:
        valid_to_raw = row["valid_to"].strip()
        records.append(
            {
                "market_code": row["market_code"],
                "valid_from": date.fromisoformat(row["valid_from"]),
                "valid_to": None if valid_to_raw == "—" else date.fromisoformat(valid_to_raw),
                "macro_group": row["macro_group"],
            }
        )
    return records


# ── Reservations ──────────────────────────────────────────────────────────────

def transform_reservations(raw_list: list[dict], raw_details: dict[str, dict]) -> list[dict]:
    """
    Produce one record per reservation_id × stay_date (fact table grain).

    reservation-level fields repeat on every night row.
    stay-level fields (stay_date, property_date, financial_status, revenues)
    come from detail['stay_rows'] — one entry per night.

    raw_details: mapping of reservation_id → full detail dict from extract.
    cohort field from the API is intentionally dropped (not in schema).
    """
    rows: list[dict] = []

    for item in raw_list:
        rid = item["reservation_id"]
        detail = raw_details.get(rid)
        if detail is None:
            raise ValueError(f"Missing detail for reservation {rid}")

        # Fields that are the same for every night of this reservation
        res = {
            "reservation_id": detail["reservation_id"],
            "arrival_date": date.fromisoformat(detail["arrival_date"]),
            "departure_date": date.fromisoformat(detail["departure_date"]),
            "reservation_status": detail["reservation_status"],
            "create_datetime": datetime.fromisoformat(
                detail["create_datetime"].replace("Z", "+00:00")
            ),
            "cancellation_datetime": (
                datetime.fromisoformat(
                    detail["cancellation_datetime"].replace("Z", "+00:00")
                )
                if detail.get("cancellation_datetime")
                else None
            ),
            "guest_country": detail.get("guest_country") or None,
            "is_block": bool(detail["is_block"]),
            "is_walk_in": bool(detail["is_walk_in"]),
            "number_of_spaces": int(detail["number_of_spaces"]),
            "space_type": detail["space_type"],
            "market_code": detail["market_code"],
            "channel_code": detail["channel_code"],
            "source_name": detail["source_name"],
            "rate_plan_code": detail["rate_plan_code"],
            "nights": int(detail["nights"]),
            "adr_room": Decimal(str(detail["adr_room"])),
            "lead_time": int(detail["lead_time"]),
            "company_name": detail.get("company_name") or None,
            "travel_agent_name": detail.get("travel_agent_name") or None,
        }

        # One row per stay_date
        for stay in detail["stay_rows"]:
            rows.append(
                {
                    **res,
                    "stay_date": date.fromisoformat(stay["stay_date"]),
                    "property_date": date.fromisoformat(stay["property_date"]),
                    "financial_status": stay["financial_status"],
                    "daily_room_revenue_before_tax": Decimal(
                        str(stay["daily_room_revenue_before_tax"])
                    ),
                    "daily_total_revenue_before_tax": Decimal(
                        str(stay["daily_total_revenue_before_tax"])
                    ),
                }
            )

    return rows


# ── FK reconciliation ─────────────────────────────────────────────────────────
# If a code appears in reservations but is missing from the lookup table,
# insert a placeholder row rather than dropping the reservation (data loss).
# Placeholders are logged as warnings so gaps can be investigated.

def _reconcile_rate_plans(rate_plans: list[dict], reservations: list[dict]) -> list[dict]:
    known = {r["rate_plan_code"] for r in rate_plans}
    missing = {r["rate_plan_code"] for r in reservations} - known
    for code in sorted(missing):
        print(f"  [warn] rate_plan_code '{code}' not in reference — adding placeholder")
        rate_plans.append({"rate_plan_code": code, "plan_family": "Unknown", "is_commissionable": False})
    return rate_plans


def _reconcile_market_codes(market_codes: list[dict], reservations: list[dict]) -> list[dict]:
    known = {r["market_code"] for r in market_codes}
    missing = {r["market_code"] for r in reservations} - known
    for code in sorted(missing):
        print(f"  [warn] market_code '{code}' not in reference — adding placeholder")
        market_codes.append({"market_code": code, "market_name": "Unknown", "macro_group": "Unknown", "description": None})
    return market_codes


def _reconcile_channel_codes(channel_codes: list[dict], reservations: list[dict]) -> list[dict]:
    known = {r["channel_code"] for r in channel_codes}
    missing = {r["channel_code"] for r in reservations} - known
    for code in sorted(missing):
        print(f"  [warn] channel_code '{code}' not in reference — adding placeholder")
        channel_codes.append({"channel_code": code, "channel_name": "Unknown", "channel_group": "Unknown"})
    return channel_codes


# ── Entry point ───────────────────────────────────────────────────────────────

def run_transform(raw: dict) -> dict:
    """
    Entry point: take raw bundle from extract, return transformed bundle
    ready for load.py.

    Returns dict with keys:
      room_type_lookup            list[dict]
      rate_plan_lookup            list[dict]
      market_code_lookup          list[dict]
      channel_code_lookup         list[dict]
      market_macro_group_history  list[dict]
      reservations                list[dict]   (one row per reservation × stay_date)
    """
    reference = raw["reference"]

    room_types = transform_room_types(reference)
    rate_plans = transform_rate_plans(reference)
    market_codes = transform_market_codes(reference)
    channel_codes = transform_channel_codes(reference)
    macro_history = transform_macro_group_history(reference)

    details_by_id: dict[str, dict] = {d["reservation_id"]: d for d in raw["details"]}
    reservations = transform_reservations(raw["list_items"], details_by_id)

    rate_plans = _reconcile_rate_plans(rate_plans, reservations)
    market_codes = _reconcile_market_codes(market_codes, reservations)
    channel_codes = _reconcile_channel_codes(channel_codes, reservations)

    return {
        "room_type_lookup": room_types,
        "rate_plan_lookup": rate_plans,
        "market_code_lookup": market_codes,
        "channel_code_lookup": channel_codes,
        "market_macro_group_history": macro_history,
        "reservations": reservations,
        "manifest": raw["manifest"],   # passed through for load_manifest audit row
    }
