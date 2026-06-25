-- Semantic views for Phase 2 tools.
-- Required tools must query these views, not raw reservations_hackathon.
--
-- Apply once against the hotel_hackathon database:
--   psql postgresql://hackathon:hackathon@localhost:5432/hotel_hackathon -f sql/VIEWS.sql

-- RULE: Agent-facing tools must NEVER query reservations_hackathon directly.
-- Every tool must read from one of the views below. This keeps business-rule
-- filters (OTB, provisional exclusion) centralised and testable in one place.

-- ---------------------------------------------------------------------------
-- vw_all_posted
-- One row per reservation × stay_date with only financial_status = 'Posted'.
-- Cancellations are NOT excluded — use this when the tool needs all statuses
-- (e.g. get_otb_summary with exclude_cancelled=False, get_cancellation_summary).
-- ---------------------------------------------------------------------------
create or replace view public.vw_all_posted as
select
  r.*
from public.reservations_hackathon r
where r.financial_status = 'Posted';

-- ---------------------------------------------------------------------------
-- vw_stay_night_base
-- One row per reservation × stay_date with default OTB filters pre-applied:
--   reservation_status != 'Cancelled'  AND  financial_status = 'Posted'
-- Use for: get_otb_summary, get_pickup_delta
-- ---------------------------------------------------------------------------
create or replace view public.vw_stay_night_base as
select
  r.*
from public.reservations_hackathon r
where r.reservation_status <> 'Cancelled'
  and r.financial_status = 'Posted';

-- ---------------------------------------------------------------------------
-- vw_segment_stay_night
-- Extends vw_stay_night_base with effective macro group and market name.
-- Macro group uses market_macro_group_history (effective-dated) and falls
-- back to the static macro_group on market_code_lookup when no history row
-- covers the stay_date.
-- Use for: get_segment_mix
-- ---------------------------------------------------------------------------
create or replace view public.vw_segment_stay_night as
select
  b.*,
  coalesce(h.macro_group, m.macro_group) as effective_macro_group,
  m.market_name
from public.vw_stay_night_base b
join public.market_code_lookup m on m.market_code = b.market_code
left join lateral (
  select h.macro_group
  from public.market_macro_group_history h
  where h.market_code = b.market_code
    and b.stay_date >= h.valid_from
    and (h.valid_to is null or b.stay_date < h.valid_to)
  order by h.valid_from desc
  limit 1
) h on true;
