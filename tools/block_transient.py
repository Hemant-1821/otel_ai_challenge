"""Tool: get_block_vs_transient_mix — block vs transient split for a calendar month."""

from __future__ import annotations

import re
from datetime import date

from langchain_core.tools import tool

from ._db import get_db


@tool
def get_block_vs_transient_mix(stay_month: str) -> dict:
    """
    Block vs transient mix for a stay month using vw_stay_night_base.

    Block = is_block IS TRUE (group/contracted business).
    Transient = is_block IS FALSE (individual bookings).
    Shares are of the combined month total (block + transient = 1.0).

    top_companies: top 3 company_name by total_revenue across all rows in the
    month. NULL company_name is labelled 'Transient'. A single company that
    spans many reservations is correctly consolidated via GROUP BY.

    top3_company_revenue_share: combined revenue of the top 3 entries as a
    fraction of total month revenue (0–1). High values signal concentration risk.

    Returns:
      - stay_month: echoed
      - block_room_nights, transient_room_nights
      - block_total_revenue, transient_total_revenue
      - block_share_of_room_nights (0–1)
      - block_share_of_revenue (0–1)
      - top_companies: list of up to 3 dicts {company_name, total_revenue, revenue_share}
      - top3_company_revenue_share (0–1 of month total)
    """
    if not re.match(r"^\d{4}-(?:0[1-9]|1[0-2])$", stay_month):
        raise ValueError(f"stay_month must be YYYY-MM, got: {stay_month!r}")

    year, month = int(stay_month[:4]), int(stay_month[5:7])
    month_start = date(year, month, 1)
    month_end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)

    params = {"start": month_start, "end": month_end}

    # ── Query 1: block vs transient totals ───────────────────────────────────
    split_sql = """
        SELECT
            COALESCE(SUM(number_of_spaces)                 FILTER (WHERE is_block), 0)     AS block_room_nights,
            COALESCE(SUM(number_of_spaces)                 FILTER (WHERE NOT is_block), 0) AS transient_room_nights,
            COALESCE(SUM(daily_total_revenue_before_tax)   FILTER (WHERE is_block), 0.0)   AS block_total_revenue,
            COALESCE(SUM(daily_total_revenue_before_tax)   FILTER (WHERE NOT is_block), 0.0) AS transient_total_revenue,
            COALESCE(SUM(daily_total_revenue_before_tax), 0.0)                              AS total_revenue
        FROM public.vw_stay_night_base
        WHERE stay_date >= %(start)s
          AND stay_date <  %(end)s
    """

    # ── Query 2: top 3 companies by total revenue ────────────────────────────
    # NULL company_name → 'Transient' per spec.
    company_sql = """
        SELECT
            COALESCE(company_name, 'Transient')           AS company_name,
            SUM(daily_total_revenue_before_tax)            AS total_revenue
        FROM public.vw_stay_night_base
        WHERE stay_date >= %(start)s
          AND stay_date <  %(end)s
        GROUP BY COALESCE(company_name, 'Transient')
        ORDER BY total_revenue DESC
        LIMIT 3
    """

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(split_sql, params)
            split = cur.fetchone()

            cur.execute(company_sql, params)
            company_rows = cur.fetchall()

    block_rn    = int(split[0])
    transient_rn = int(split[1])
    block_rev    = float(split[2])
    transient_rev = float(split[3])
    total_rev    = float(split[4])
    total_rn     = block_rn + transient_rn

    top_companies = [
        {
            "company_name": row[0],
            "total_revenue": float(row[1]),
            "revenue_share": round(float(row[1]) / total_rev, 4) if total_rev else 0.0,
        }
        for row in company_rows
    ]

    top3_rev = sum(c["total_revenue"] for c in top_companies)

    return {
        "stay_month": stay_month,
        "block_room_nights": block_rn,
        "transient_room_nights": transient_rn,
        "block_total_revenue": block_rev,
        "transient_total_revenue": transient_rev,
        "block_share_of_room_nights": round(block_rn / total_rn, 4) if total_rn else 0.0,
        "block_share_of_revenue": round(block_rev / total_rev, 4) if total_rev else 0.0,
        "top_companies": top_companies,
        "top3_company_revenue_share": round(top3_rev / total_rev, 4) if total_rev else 0.0,
    }
