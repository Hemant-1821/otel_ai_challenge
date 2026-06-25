"""Tool: get_as_of_otb — point-in-time OTB rebuild.

HITL is NOT implemented inside this tool.  It is enforced by a dedicated
approval node in the agent graph (agent/graph.py) that intercepts any call
to this tool and fires interrupt() before the tool executes.  This keeps the
tool a pure function: testable without a compiled graph, callable from scripts,
and free of control-flow concerns.

Why HITL is required at all:
  - Parameters (as_of_utc, stay_month) are easy for the LLM to hallucinate.
  - A wrong as_of_utc silently produces plausible-looking wrong numbers.
  - The GM should confirm the reference timestamp before an expensive rebuild.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone

from langchain_core.tools import tool

from ._db import get_db

HITL_TOOLS = {"get_as_of_otb"}  # consumed by agent/graph.py approval node


def _parse_as_of_utc(as_of_utc: str) -> datetime:
    """Parse ISO timestamp and normalise to a UTC-aware datetime."""
    # Accept: "2026-06-20T10:00:00Z", "...+00:00", or naive (assumed UTC)
    s = as_of_utc.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        raise ValueError(
            f"as_of_utc must be ISO 8601 (e.g. 2026-06-20T10:00:00Z), got: {as_of_utc!r}"
        )
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@tool
def get_as_of_otb(stay_month: str, as_of_utc: str) -> dict:
    """
    Point-in-time on-the-books for a stay_date month as known at as_of_utc.

    A stay row is included when ALL of:
      - create_datetime  <= as_of_utc  (reservation existed at reference time)
      - reservation_status <> 'Cancelled' OR cancellation_datetime > as_of_utc
        (not yet cancelled at reference time)
      - financial_status = 'Posted'  (provisional always excluded)

    Reads from vw_all_posted so financial_status = 'Posted' is enforced by the
    view; point-in-time filters are applied as bound query parameters.

    Returns same shape as get_otb_summary plus:
      - as_of_utc: echoed (normalised to UTC ISO string)
    """
    if not re.match(r"^\d{4}-(?:0[1-9]|1[0-2])$", stay_month):
        raise ValueError(f"stay_month must be YYYY-MM, got: {stay_month!r}")

    as_of_dt = _parse_as_of_utc(as_of_utc)

    year, month = int(stay_month[:4]), int(stay_month[5:7])
    month_start = date(year, month, 1)
    month_end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)

    sql = """
        SELECT
            COUNT(*)                                                AS row_count,
            COUNT(DISTINCT reservation_id)                          AS reservation_count,
            COALESCE(SUM(number_of_spaces), 0)                      AS room_nights,
            COALESCE(SUM(daily_room_revenue_before_tax), 0.0)       AS room_revenue,
            COALESCE(SUM(daily_total_revenue_before_tax), 0.0)      AS total_revenue
        FROM public.vw_all_posted
        WHERE stay_date        >= %(start)s
          AND stay_date         < %(end)s
          AND create_datetime  <= %(as_of)s
          AND (
                reservation_status <> 'Cancelled'
                OR cancellation_datetime > %(as_of)s
              )
    """

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"start": month_start, "end": month_end, "as_of": as_of_dt})
            row = cur.fetchone()

    return {
        "stay_month": stay_month,
        "as_of_utc": as_of_dt.isoformat(),
        "row_count": int(row[0]),
        "reservation_count": int(row[1]),
        "room_nights": int(row[2]),
        "room_revenue": float(row[3]),
        "total_revenue": float(row[4]),
        "exclude_cancelled": True,
    }
