# Metric Definitions

## Invariant: tools must never query `reservations_hackathon` directly

All agent-facing tools must read from a semantic view in `sql/VIEWS.sql`.
Raw table access is forbidden in tool code — filters are owned by the view layer, not scattered across tools.

| View | Filters applied | Use for |
|------|----------------|---------|
| `vw_all_posted` | `financial_status = 'Posted'` | Tools that need all statuses (cancellation analysis, `exclude_cancelled=False`) |
| `vw_stay_night_base` | `+ reservation_status <> 'Cancelled'` | Default OTB tools |
| `vw_segment_stay_night` | same as base + effective macro group | Segment mix analysis |

---

## Stay rows vs reservations vs room nights

| Term | Definition |
|------|-----------|
| **Stay row** | One row in `reservations_hackathon` for a single `reservation_id × stay_date`. A 3-night reservation = 3 stay rows. |
| **Reservation count** | `COUNT(DISTINCT reservation_id)` at the filtered grain. Never use `COUNT(*)`. |
| **Room nights** | `SUM(number_of_spaces)` across stay rows. A 2-room 3-night stay = 6 room nights (3 rows × `number_of_spaces=2`). |

## Default OTB filters

Applied by `vw_stay_night_base` and all tools unless documented otherwise:

```sql
reservation_status <> 'Cancelled'
AND financial_status = 'Posted'
```

`financial_status = 'Provisional'` rows are always excluded from OTB figures. Cancelled rows are excluded by default but can be included when the tool or question explicitly requests them (e.g. `get_cancellation_summary`, `exclude_cancelled=False`).

## Pickup window boundaries

`get_pickup_delta` uses `create_datetime` (stored in UTC) for booking window filtering. Window boundaries are computed as `Europe/London` local midnight converted to UTC so that "last 7 days" aligns with how the hotel team counts pickup (London business days), not raw UTC hours.

## Effective macro group vs static macro group

`market_code_lookup.macro_group` is a static label on the market code. `effective_macro_group` (used in `vw_segment_stay_night`) resolves the correct classification for a **specific stay date** by joining `market_macro_group_history` on the overlap `valid_from <= stay_date < valid_to`. This matters when a market code is re-classified mid-year (e.g. `PROM` moved from Retail to Leisure Group for stays from a certain date). Always use `effective_macro_group` for segment mix analysis.
