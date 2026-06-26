"""Tool: get_otb_summary — on-the-books summary for a calendar month."""

from __future__ import annotations

import re
from datetime import date

from langchain_core.tools import tool

from ._db import get_db


@tool
def get_otb_summary(
    stay_month: str,
    exclude_cancelled: bool = True,
    breakdown: str | None = None,
) -> dict:
    """
    On-the-books summary for a calendar month of stay dates (YYYY-MM).

    Default universe: vw_stay_night_base (Posted, non-cancelled).
    When exclude_cancelled=False, includes cancelled rows but still restricts
    to financial_status='Posted' (provisional always excluded).

    breakdown (optional):
      - "room_type": group results by space_type, joining room_type_lookup for
        display_name and room_class. Returns a "breakdown_rows" list sorted by
        total_revenue desc. Each row includes space_type, display_name,
        room_class, reservation_count, room_nights, room_revenue, total_revenue,
        and adr (derived as room_revenue / room_nights, 0 when room_nights=0).
        Use this for questions about which room type is performing best/worst
        by revenue, ADR, or room nights.

    Grain notes:
      - row_count is stay-date rows, NOT reservations. A 3-night reservation = 3 rows.
      - reservation_count uses COUNT(DISTINCT reservation_id).
      - room_nights = SUM(number_of_spaces) — correct for multi-room reservations.
      - Never use adr_room directly — derive ADR as room_revenue / room_nights.

    Returns (aggregate):
      - stay_month, row_count, reservation_count, room_nights,
        room_revenue, total_revenue, exclude_cancelled
    Returns (with breakdown="room_type"), adds:
      - breakdown_rows: list of per-room-type dicts ordered by total_revenue desc
    """
    if not re.match(r"^\d{4}-(?:0[1-9]|1[0-2])$", stay_month):
        raise ValueError(f"stay_month must be YYYY-MM, got: {stay_month!r}")

    _VALID_BREAKDOWNS = {"room_type"}
    if breakdown is not None and breakdown not in _VALID_BREAKDOWNS:
        raise ValueError(f"breakdown must be one of {_VALID_BREAKDOWNS} or None, got: {breakdown!r}")

    year, month = int(stay_month[:4]), int(stay_month[5:7])
    month_start = date(year, month, 1)
    month_end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)

    source = "public.vw_stay_night_base" if exclude_cancelled else "public.vw_all_posted"

    # ── Aggregate totals (always returned) ───────────────────────────────────
    agg_sql = f"""
        SELECT
            COUNT(*)                              AS row_count,
            COUNT(DISTINCT reservation_id)        AS reservation_count,
            COALESCE(SUM(number_of_spaces), 0)    AS room_nights,
            COALESCE(SUM(daily_room_revenue_before_tax), 0.0)   AS room_revenue,
            COALESCE(SUM(daily_total_revenue_before_tax), 0.0)  AS total_revenue
        FROM {source}
        WHERE stay_date >= %(start)s
          AND stay_date <  %(end)s
    """

    result: dict = {"stay_month": stay_month, "exclude_cancelled": exclude_cancelled}

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(agg_sql, {"start": month_start, "end": month_end})
            row = cur.fetchone()
            result["row_count"] = int(row[0])
            result["reservation_count"] = int(row[1])
            result["room_nights"] = int(row[2])
            result["room_revenue"] = float(row[3])
            result["total_revenue"] = float(row[4])

            # ── Room-type breakdown ───────────────────────────────────────────
            if breakdown == "room_type":
                bd_sql = f"""
                    SELECT
                        b.space_type,
                        rt.display_name,
                        rt.room_class,
                        COUNT(DISTINCT b.reservation_id)              AS reservation_count,
                        COALESCE(SUM(b.number_of_spaces), 0)          AS room_nights,
                        COALESCE(SUM(b.daily_room_revenue_before_tax), 0.0)  AS room_revenue,
                        COALESCE(SUM(b.daily_total_revenue_before_tax), 0.0) AS total_revenue
                    FROM {source} b
                    JOIN public.room_type_lookup rt ON rt.space_type = b.space_type
                    WHERE b.stay_date >= %(start)s
                      AND b.stay_date <  %(end)s
                    GROUP BY b.space_type, rt.display_name, rt.room_class
                    ORDER BY total_revenue DESC
                """
                cur.execute(bd_sql, {"start": month_start, "end": month_end})
                rows = cur.fetchall()
                breakdown_rows = []
                for r in rows:
                    rn = int(r[4])
                    rrev = float(r[5])
                    breakdown_rows.append({
                        "space_type": r[0],
                        "display_name": r[1],
                        "room_class": r[2],
                        "reservation_count": int(r[3]),
                        "room_nights": rn,
                        "room_revenue": rrev,
                        "total_revenue": float(r[6]),
                        "adr": round(rrev / rn, 2) if rn else 0.0,
                    })
                result["breakdown_rows"] = breakdown_rows

    return result
