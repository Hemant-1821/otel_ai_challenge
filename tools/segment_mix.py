"""Tool: get_segment_mix — segment breakdown for a calendar month."""

from __future__ import annotations

import re
from datetime import date

from langchain_core.tools import tool

from ._db import get_db


@tool
def get_segment_mix(
    stay_month: str,
    macro_group: str | None = None,
) -> dict:
    """
    Segment mix for a stay month using vw_segment_stay_night.

    Uses effective_macro_group (stay-date-effective from market_macro_group_history),
    not the static macro_group column on market_code_lookup.

    If macro_group is set, the result is filtered to that effective macro group only.
    Shares are computed over the filtered population — when macro_group is set,
    shares sum to 1.0 within that group, not across the whole hotel.

    Returns:
      - stay_month: echoed input
      - macro_group_filter: echoed filter (None = all groups)
      - denominator_room_nights: total room nights in scope (share denominator)
      - denominator_revenue: total revenue in scope (share denominator)
      - segments: list ordered by total_revenue desc, each with:
          - market_code
          - market_name
          - effective_macro_group
          - room_nights: sum(number_of_spaces)
          - total_revenue: sum(daily_total_revenue_before_tax)
          - share_of_room_nights: 0–1 of denominator_room_nights
          - share_of_revenue: 0–1 of denominator_revenue
    """
    if not re.match(r"^\d{4}-(?:0[1-9]|1[0-2])$", stay_month):
        raise ValueError(f"stay_month must be YYYY-MM, got: {stay_month!r}")

    year, month = int(stay_month[:4]), int(stay_month[5:7])
    month_start = date(year, month, 1)
    month_end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)

    params: dict = {"start": month_start, "end": month_end}
    macro_filter = ""
    if macro_group is not None:
        macro_filter = "AND effective_macro_group = %(macro_group)s"
        params["macro_group"] = macro_group

    # Window functions compute the denominator over the same filtered population,
    # so shares always sum to 1.0 within the result set.
    sql = f"""
        SELECT
            market_code,
            market_name,
            effective_macro_group,
            SUM(number_of_spaces)                                           AS room_nights,
            SUM(daily_total_revenue_before_tax)                             AS total_revenue,
            SUM(SUM(number_of_spaces))       OVER ()                        AS denom_room_nights,
            SUM(SUM(daily_total_revenue_before_tax)) OVER ()                AS denom_revenue
        FROM public.vw_segment_stay_night
        WHERE stay_date >= %(start)s
          AND stay_date <  %(end)s
          {macro_filter}
        GROUP BY market_code, market_name, effective_macro_group
        ORDER BY total_revenue DESC
    """

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    if not rows:
        return {
            "stay_month": stay_month,
            "macro_group_filter": macro_group,
            "denominator_room_nights": 0,
            "denominator_revenue": 0.0,
            "segments": [],
        }

    # column order: market_code[0], market_name[1], effective_macro_group[2],
    #               room_nights[3], total_revenue[4], denom_room_nights[5], denom_revenue[6]
    denom_rn = int(rows[0][5])
    denom_rev = float(rows[0][6])

    segments = [
        {
            "market_code": row[0],
            "market_name": row[1],
            "effective_macro_group": row[2],
            "room_nights": int(row[3]),
            "total_revenue": float(row[4]),
            "share_of_room_nights": round(int(row[3]) / denom_rn, 4) if denom_rn else 0.0,
            "share_of_revenue": round(float(row[4]) / denom_rev, 4) if denom_rev else 0.0,
        }
        for row in rows
    ]

    return {
        "stay_month": stay_month,
        "macro_group_filter": macro_group,
        "denominator_room_nights": denom_rn,
        "denominator_revenue": denom_rev,
        "segments": segments,
    }
