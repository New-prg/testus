# Driving analytics MVP

FastAPI + React MVP for driving efficiency analytics with demo Pilot-GPS provider, PostgreSQL storage, rating windows, ML anomalies/clusters, dashboard, vehicles, and reports.

## Stack

- Backend: Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, scikit-learn
- Frontend: React, TypeScript, Vite, TailwindCSS, Recharts
- Infra: Docker, Docker Compose

## Run

```bash
cp .env.example .env
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- Swagger: http://localhost:8000/docs
- PostgreSQL: localhost:5432

## Demo access

- email: `admin@example.com`
- password: `admin123`

## Seed

```bash
docker compose exec backend python -m app.db.seed
```

## Migrations

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend alembic downgrade -1
```

## Rating methodology

- Profile: `INSTANCE_2`
- Final rating is calculated from 8 weighted metrics with weight renormalization when some metrics are missing.
- `score_by_threshold` rule: for `higher_is_better`, the service picks the highest score whose threshold is `<= value`; for `lower_is_better`, it picks the highest score whose threshold is `>= value`.

## Pilot-GPS integration

- Demo mode is enabled by default with `USE_DEMO_DATA=true`.
- Live integration uses only official/publicly documented Pilot-GPS areas for vehicle listing and current sensor status; historical calibrated sensor import remains an extension point.
- Raw external data is preserved in JSON fields.

### Live current snapshot import

To import real Pilot-GPS vehicles, sensor metadata, and current sensor snapshots into the same database used by the demo/admin UI:

```bash
docker compose exec backend env USE_DEMO_DATA=false \
  PILOT_GPS_BASE_URL=https://pilot-gps.example \
  PILOT_GPS_NODE=1 \
  PILOT_GPS_USERNAME=your_login \
  PILOT_GPS_PASSWORD=your_password \
  python -m app.cli import-pilot-current
```

This import populates real vehicles, sensors, and current readings so they are visible under `admin@example.com`. It does not invent historical sensor data, so analytics/rating history remains partial until confirmed history endpoints or repeated snapshots are available.

To replace the current shared demo fleet with real Pilot-GPS vehicles and anonymize visible identifiers:

```bash
docker compose exec backend env \
  USE_DEMO_DATA=false \
  PILOT_GPS_BASE_URL=https://pilot-gps.example \
  PILOT_GPS_NODE=1 \
  PILOT_GPS_USERNAME=your_login \
  PILOT_GPS_PASSWORD=your_password \
  python -m app.cli import-pilot-current --replace-shared-fleet --anonymize
```

This keeps the same admin/demo access path, but replaces the shared fleet dataset with real Pilot-GPS vehicles while masking user-visible identifiers such as plate number, name, IMEI, and VIN.

## API endpoints

- Auth: `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`
- Pilot sync: `POST /api/pilot/sync/vehicles`, `POST /api/pilot/sync/sensors`, `POST /api/pilot/sync/readings`, `POST /api/pilot/sync/current?replace_shared_fleet=true&anonymize=true`, `POST /api/pilot/sync/all`, `GET /api/pilot/sync/logs`
- Vehicles: `GET /api/vehicles`, `GET /api/vehicles/{id}`, `GET /api/vehicles/{id}/sensors`, `GET /api/vehicles/{id}/metrics`, `GET /api/vehicles/{id}/ratings`
- Dashboard: `GET /api/dashboard/summary`, `GET /api/dashboard/timeseries`, `GET /api/dashboard/comparison`, `GET /api/dashboard/problem-vehicles`
- Reports: `GET /api/reports/fleet`, `GET /api/reports/vehicle/{id}`, `GET /api/reports/export/csv`
- ML: `POST /api/ml/recalculate`, `GET /api/ml/anomalies`, `GET /api/ml/clusters`

## Known limitations

- Live historical calibrated sensor values from official Pilot-GPS public docs remain partially undocumented.
- Demo provider is the default source for a guaranteed thesis demo flow.
- PDF export is intentionally omitted in MVP scope.

## API blockers

See `backend/API_BLOCKERS.md`.
