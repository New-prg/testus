# FRONTEND PAGES KNOWLEDGE BASE

## OVERVIEW
Route-level screens for auth, dashboard, vehicles, and reports. These files orchestrate data loading, user-facing contract copy, and composition of shared cards/charts/tables.

## WHERE TO LOOK
| Task | Location | Notes |
|---|---|---|
| Login/register | `LoginPage.tsx`, `RegisterPage.tsx` | Public auth flows |
| Dashboard | `DashboardPage.tsx` | Loads four dashboard endpoints in parallel |
| Vehicles | `VehiclesPage.tsx` | Search, sort, and fleet summary stats |
| Reports | `ReportsPage.tsx` | Fleet/vehicle mode switch, period switch, CSV export |

## CONVENTIONS
- Pages own loading/error/empty orchestration and call typed API wrappers, not raw fetch.
- Dashboard/vehicles/reports currently assume the weekly/default backend contract as the happy path.
- Contract wording in copy is deliberate; messages often explain exactly which backend endpoints or fields are missing.
- Derived view math stays small and local: search filters, averages, headline text, formatting helpers.

## ANTI-PATTERNS
- Do not duplicate endpoint-specific formatting logic across pages if it can be shared through API types or table/chart props.
- Do not replace backend field names in explanatory copy with vague labels; these pages intentionally document the contract through the UI.
- Do not add page-local fetch utilities or token handling.

## UNIQUE STYLES
- `DashboardPage.tsx` loads summary, timeseries, comparison, and problem vehicles together with `Promise.all`.
- `ReportsPage.tsx` is multi-mode: fleet vs vehicle, period switch, CSV export, and text conclusions from backend.
- `VehiclesPage.tsx` treats `plate_number` and `name` as the searchable fields by design.

## NOTES
- Shared presentation primitives live in `../components/`; keep route files focused on orchestration and narrative.
