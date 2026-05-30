# BACKEND API KNOWLEDGE BASE

## OVERVIEW
Feature-scoped FastAPI routers for auth, vehicles, dashboard, reports, Pilot sync, and ML. This layer owns HTTP contract shape, query params, auth dependencies, and many hand-built response dictionaries.

## WHERE TO LOOK
| Task | Location | Notes |
|---|---|---|
| Auth endpoints | `auth.py` | `/auth/register`, `/auth/login`, `/auth/me` |
| Vehicle registry/detail | `vehicles.py` | Canonical latest-metric vehicle row |
| Fleet dashboard | `dashboard.py` | Summary, timeseries, comparison, problem vehicles |
| Reports/export | `reports.py` | Fleet report, vehicle report, CSV export |
| Sync triggers | `pilot_sync.py` | Vehicle/sensor/reading/all sync endpoints |
| ML endpoints | `ml.py` | Recalculate, anomalies, clusters |
| Shared auth deps | `deps.py` | `get_current_user`, DB/session dependencies |

## CONVENTIONS
- Every router declares its own prefix/tags; `app/main.py` mounts them under the common API prefix.
- Protected resources use router-level `Depends(get_current_user)` when the whole module requires auth.
- Vehicle/dashboard/report payloads are built manually as dicts; preserve existing field names and numeric rounding.
- `/dashboard` and `/reports` both use period-based querying, but they are not identical: dashboard supports `day/week/month/quarter`, while reports currently use `week/month/quarter` plus optional explicit date ranges. Keep shared behavior aligned without inventing unsupported periods.
- `vehicles.py` is the canonical source for the latest vehicle row shape; reusing or mirroring it is safer than inventing a new view model.

## ANTI-PATTERNS
- Do not rename or casually reshape contract fields like `analytics_readiness_percent`, `fuel_per_100km`, `high_speed_brakes_per_100km`, or `last_sync_at`; frontend pages and tables depend on them.
- Do not bypass auth dependency patterns for convenience on protected endpoints.
- Do not duplicate slightly different period/window helpers unless endpoint semantics truly differ.

## UNIQUE STYLES
- `dashboard.py` aggregates from ORM relations in Python rather than pushing all analytics into SQL.
- `reports.py` keeps reporting logic inline, including conclusions and CSV generation.
- `auth.py` is intentionally minimal: register/login/me and token issuance only.

## NOTES
- This directory is about HTTP contracts, not rating formulas or Pilot provider internals; those live in `../services/`.
