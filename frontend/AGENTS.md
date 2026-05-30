# FRONTEND KNOWLEDGE BASE

## OVERVIEW
Vite/React/TypeScript frontend for auth, dashboard, vehicles, and reports. State is intentionally light: route-local state plus auth context, with typed API wrappers aligned to backend endpoints.

## STRUCTURE
```text
frontend/
├── src/
│   ├── api/          # typed backend contract wrappers
│   ├── pages/        # route-level screens
│   ├── components/   # shared layout, cards, charts, tables
│   └── index.css     # semantic classes + theme layering
├── package.json
├── tsconfig*.json
├── vite.config.js
├── tailwind.config.ts
└── Dockerfile
```

## WHERE TO LOOK
| Task | Location | Notes |
|---|---|---|
| API behavior | `src/api/` | `/api` prefixing, token handling, typed endpoints |
| Route map | `src/App.tsx` | Public auth routes + protected app routes |
| Auth state | `src/components/layout/AuthProvider.tsx` | Context replaces a global store |
| Shell/nav | `src/components/layout/AppShell.tsx` | Post-login frame |
| Dashboard page | `src/pages/DashboardPage.tsx` | Multi-endpoint analytics composition |
| Vehicles page | `src/pages/VehiclesPage.tsx` | Search/sort fleet registry |
| Reports page | `src/pages/ReportsPage.tsx` | Fleet/vehicle report and CSV export |
| Semantic styling | `src/index.css`, `tailwind.config.ts` | Project-specific tokens and component classes |

## CONVENTIONS
- Use the `src/api/` layer for backend access; do not scatter raw `fetch` calls across pages/components.
- Pages are route/domain-first; shared UI pieces live under `components/` by primitive type.
- TypeScript is strict; keep API types and page assumptions aligned with backend field names.
- Auth is context-based, not Redux/store-based.
- Vite dev/build/lint scripts in `package.json` are the frontend tooling source of truth.

## ANTI-PATTERNS
- Do not bypass `src/api/client.ts` for authenticated requests.
- Do not rename contract fields coming from backend row payloads unless backend and all page/table consumers are updated together.
- Do not assume a frontend test harness exists; there is no established first-party frontend test pattern yet.

## UNIQUE STYLES
- Styling is semantic and tokenized: `surface-card`, `primary-action`, `secondary-action`, `section-label`, plus custom color names like `signal`, `brass`, `cream`.
- Charts/tables/cards are shared primitives reused by route pages rather than being nested under feature folders.
- Error and empty states explicitly mention backend contract expectations in user-facing copy.

## COMMANDS
```bash
cd frontend
npm install
npm run dev
npm run build
npm run preview
npm run lint
```

## NOTES
- Child guides exist for `src/api` and `src/pages`; keep this file focused on app-wide frontend rules.
- No standalone frontend test runner/config was found.
