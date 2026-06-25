"""Tool: get_otb_summary — on-the-books summary for a calendar month."""

from __future__ import annotations

import re
from datetime import date

from langchain_core.tools import tool

from ._db import get_db


@tool
def get_otb_summary(stay_month: str, exclude_cancelled: bool = True) -> dict:
    """
    On-the-books summary for a calendar month of stay dates (YYYY-MM).

    Default universe: vw_stay_night_base (Posted, non-cancelled).
    When exclude_cancelled=False, includes cancelled rows but still restricts
    to financial_status='Posted' (provisional always excluded).

    Grain notes:
      - row_count is stay-date rows, NOT reservations. A 3-night reservation = 3 rows.
      - reservation_count uses COUNT(DISTINCT reservation_id).
      - room_nights = SUM(number_of_spaces) — correct for multi-room reservations.

    Returns:
      - stay_month: echoed input
      - row_count: stay-date rows in scope
      - reservation_count: distinct reservations
      - room_nights: sum(number_of_spaces)
      - room_revenue: sum(daily_room_revenue_before_tax)
      - total_revenue: sum(daily_total_revenue_before_tax)
      - exclude_cancelled: echoed input
    """
    if not re.match(r"^\d{4}-(?:0[1-9]|1[0-2])$", stay_month):
        raise ValueError(f"stay_month must be YYYY-MM, got: {stay_month!r}")

    year, month = int(stay_month[:4]), int(stay_month[5:7])
    month_start = date(year, month, 1)
    month_end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)

    if exclude_cancelled:
        # vw_stay_night_base already enforces both OTB filters
        source = "public.vw_stay_night_base"
    else:
        # vw_all_posted keeps financial_status='Posted' but includes cancelled rows
        source = "public.vw_all_posted"

    sql = f"""
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

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"start": month_start, "end": month_end})
            row = cur.fetchone()

    return {
        "stay_month": stay_month,
        "row_count": int(row[0]),
        "reservation_count": int(row[1]),
        "room_nights": int(row[2]),
        "room_revenue": float(row[3]),
        "total_revenue": float(row[4]),
        "exclude_cancelled": exclude_cancelled,
    }
