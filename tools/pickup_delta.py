"""Tool: get_pickup_delta — booking pace for future stays."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from langchain_core.tools import tool

from ._db import get_db

_LONDON = ZoneInfo("Europe/London")


def _window_bounds(booking_window_days: int) -> tuple[datetime, datetime]:
    """
    Return (window_start_utc, window_end_utc).

    Start = midnight London time on (today_london - booking_window_days).
    End   = now UTC.

    Example: booking_window_days=7, now=2026-06-25 14:00 BST (UTC+1)
      → start = 2026-06-18 00:00 BST = 2026-06-17 23:00 UTC
      → end   = 2026-06-25 13:00 UTC
    """
    now_utc = datetime.now(timezone.utc)
    now_london = now_utc.astimezone(_LONDON)
    past_london = now_london - timedelta(days=booking_window_days)
    start_london = past_london.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_london.astimezone(timezone.utc), now_utc


@tool
def get_pickup_delta(
    booking_window_days: int,
    future_stay_from: str,
) -> dict:
    """
    Booking pace / pickup for future stays.

    booking_window_days: look at reservations whose create_datetime falls in
      [start_of_day_london(today - days), now], boundaries converted to UTC.
      Uses London midnight so the window aligns with hotel business days.

    future_stay_from: ISO date (YYYY-MM-DD); only stay_date >= this date.
      Prevents already-past nights from diluting the pickup signal.

    Uses create_datetime for the booking window — not stay_date.
    Reads from vw_stay_night_base (OTB filters applied) for the main count,
    and vw_segment_stay_night for the by_segment breakdown.

    Returns:
      - booking_window_days: echoed
      - future_stay_from: echoed
      - window_start_utc: ISO timestamp — actual UTC lower bound used
      - window_end_utc: ISO timestamp — actual UTC upper bound (now)
      - new_reservations: count(distinct reservation_id) created in window
      - new_room_nights: sum(number_of_spaces) for matching stay rows
      - new_total_revenue: sum(daily_total_revenue_before_tax)
      - by_segment: all segments ordered by new_total_revenue desc, each with:
          market_code, market_name, effective_macro_group,
          new_reservations, new_room_nights, new_total_revenue
    """
    if not isinstance(booking_window_days, int) or booking_window_days < 1:
        raise ValueError(f"booking_window_days must be a positive integer, got: {booking_window_days!r}")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", future_stay_from):
        raise ValueError(f"future_stay_from must be YYYY-MM-DD, got: {future_stay_from!r}")

    stay_from = date.fromisoformat(future_stay_from)
    window_start, window_end = _window_bounds(booking_window_days)

    params = {
        "stay_from": stay_from,
        "w_start": window_start,
        "w_end": window_end,
    }

    summary_sql = """
        SELECT
            COUNT(DISTINCT reservation_id)                          AS new_reservations,
            COALESCE(SUM(number_of_spaces), 0)                      AS new_room_nights,
            COALESCE(SUM(daily_total_revenue_before_tax), 0.0)      AS new_total_revenue
        FROM public.vw_stay_night_base
        WHERE stay_date      >= %(stay_from)s
          AND create_datetime >= %(w_start)s
          AND create_datetime <  %(w_end)s
    """

    segment_sql = """
        SELECT
            market_code,
            market_name,
            effective_macro_group,
            COUNT(DISTINCT reservation_id)                          AS new_reservations,
            COALESCE(SUM(number_of_spaces), 0)                      AS new_room_nights,
            COALESCE(SUM(daily_total_revenue_before_tax), 0.0)      AS new_total_revenue
        FROM public.vw_segment_stay_night
        WHERE stay_date      >= %(stay_from)s
          AND create_datetime >= %(w_start)s
          AND create_datetime <  %(w_end)s
        GROUP BY market_code, market_name, effective_macro_group
        ORDER BY new_total_revenue DESC
    """

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(summary_sql, params)
            summary_row = cur.fetchone()

            cur.execute(segment_sql, params)
            segment_rows = cur.fetchall()

    by_segment = [
        {
            "market_code": row[0],
            "market_name": row[1],
            "effective_macro_group": row[2],
            "new_reservations": int(row[3]),
            "new_room_nights": int(row[4]),
            "new_total_revenue": float(row[5]),
        }
        for row in segment_rows
    ]

    return {
        "booking_window_days": booking_window_days,
        "future_stay_from": future_stay_from,
        "window_start_utc": window_start.isoformat(),
        "window_end_utc": window_end.isoformat(),
        "new_reservations": int(summary_row[0]),
        "new_room_nights": int(summary_row[1]),
        "new_total_revenue": float(summary_row[2]),
        "by_segment": by_segment,
    }
