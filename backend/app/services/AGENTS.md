# BACKEND SERVICES KNOWLEDGE BASE

## OVERVIEW
Domain logic layer for ratings, Pilot-GPS integration, ML feature/model work, and an underused reports service. Most business behavior that matters to analytics correctness lives here.

## WHERE TO LOOK
| Task | Location | Notes |
|---|---|---|
| Sync orchestration | `pilot_gps/sync_service.py` | Vehicles, sensors, readings, analytics chain |
| Provider client/parsers | `pilot_gps/` | Demo/live client split + payload parsing |
| Metric calculation | `ratings/metric_calculator.py` | Builds metric windows |
| Final rating logic | `ratings/rating_calculator.py` | Threshold scoring + weight renormalization |
| Rating explanations | `ratings/rating_explainer.py` | Warning/positive/negative factors |
| ML dataset | `ml/dataset_builder.py` | Feature rows from metrics + ratings |
| ML models | `ml/anomaly_service.py`, `ml/clustering_service.py` | Derived anomaly/cluster outputs |
| Reports service | `reports/report_service.py` | Present but not the primary API path today |

## CONVENTIONS
- Keep provider integration concerns inside `pilot_gps/`; route modules should call orchestration, not parse provider payloads themselves.
- Preserve the shared metric vocabulary across ratings, ML, dashboard, reports, and frontend clients.
- Rating logic assumes per-window alignment between metric windows and rating windows.
- `RatingCalculator` renormalizes weights when metrics are missing; missing-data behavior is a real business rule.
- Ratings and sync services write/store derived rows, while some ML helpers primarily build transient outputs that are later persisted by callers. Check the specific service before assuming persistence behavior.

## ANTI-PATTERNS
- Do not guess undocumented live Pilot-GPS behavior to “complete” the provider path.
- Do not change metric names or threshold direction semantics without tracing all downstream consumers.
- Do not assume `reports/report_service.py` is authoritative just because it exists; verify active call sites first.

## UNIQUE STYLES
- `PilotSyncService.sync_all()` is the backend orchestration spine: sync raw entities, then derive analytics.
- Rating output includes explanation JSON, warnings, positive factors, and negative factors, not just a score.
- ML feature rows embed `final_rating` alongside raw metric features.

## NOTES
- If a change touches `ratings/` or `pilot_gps/`, inspect dashboard/reports/frontend consumers too.
