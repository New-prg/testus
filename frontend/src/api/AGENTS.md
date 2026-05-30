# FRONTEND API KNOWLEDGE BASE

## OVERVIEW
Typed contract layer for backend communication. Owns token persistence, `/api` prefix normalization, error parsing, and per-feature request/response types.

## WHERE TO LOOK
| Task | Location | Notes |
|---|---|---|
| Shared fetch logic | `client.ts` | Token key, auth header, JSON/body handling, 401 cleanup |
| Auth endpoints | `auth.ts` | Login/register/me wrappers |
| Dashboard endpoints | `dashboard.ts` | Summary, timeseries, comparison, problem vehicles |
| Vehicles endpoints | `vehicles.ts` | Fleet list/detail |
| Reports endpoints | `reports.ts` | Fleet report, vehicle report, CSV export |

## CONVENTIONS
- All requests should go through `apiFetch` or `apiFetchBlob`.
- Paths passed to the client can omit `/api`; `normalizePath()` adds it.
- Keep TypeScript types mirror-shaped to backend payloads, including snake_case keys.
- `apiFetch()` clears the stored token on 401 responses; code paths using `apiFetchBlob()` should not assume the same cleanup happens automatically.
- Reuse types across modules when the backend does, e.g. reports importing dashboard summary/timeseries/comparison types.

## ANTI-PATTERNS
- Do not camelCase backend response fields in this layer.
- Do not duplicate token storage or header assembly in pages/components.
- Do not silently change report/dashboard type coupling without checking page consumers.

## UNIQUE STYLES
- `reports.ts` intentionally reuses dashboard and vehicle types instead of defining isolated report-only copies.
- CSV export is a first-class API path via `apiFetchBlob`, not an afterthought.

## NOTES
- This layer is the frontend/backend contract seam; drift here usually breaks pages immediately.
