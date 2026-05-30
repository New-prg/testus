# API blockers and integration risks

## Pilot-GPS calibrated sensor history

Public research confirms official/public Pilot-GPS capability areas for vehicles, status, movement history, reports, distance, notifications, fuel consumption, and CRIT object list/history/details. It does **not** conclusively confirm a stable official endpoint for historical calibrated per-sensor values required for high-confidence fuel, acceleration, and engine-state analytics.

Because of that uncertainty, this backend deliberately implements a provider boundary:

- Demo mode is the default through `USE_DEMO_DATA=true`.
- External Pilot-GPS data is preserved in `raw_json` on vehicles and telemetry rows.
- HTTP provider URLs are deployment configuration values rather than hardcoded guessed endpoints.
- Unsupported sensor-history certainty remains a blocker until official Pilot-GPS documentation or support confirms exact endpoints, request parameters, units, and retention guarantees.

## MVP impact

The analytics and ratings are production-shaped but demo-data-backed by default. The backend now supports live import of vehicles, sensor metadata, and current sensor snapshots through confirmed `cmd=list` and `cmd=status&agents=...` endpoints, but calibrated historical per-sensor import remains blocked. Before using live Pilot-GPS data for reliable driver scoring, verify official sensor history semantics and map raw fields into the internal telemetry schema.
