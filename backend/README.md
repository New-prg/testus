# Driving Efficiency Analytics Backend MVP

FastAPI backend for vehicle driving-efficiency analytics with PostgreSQL, SQLAlchemy 2.x, Alembic, JWT auth, demo data, Pilot-GPS integration boundaries, ratings, reports, and lightweight ML services.

## Run with Docker Compose

```bash
cd backend
docker compose up --build
```

The compose command runs migrations, seeds demo data when `USE_DEMO_DATA=true`, and starts the API on `http://localhost:8000`.
By default this demo seed now prefers the reduced weekly dataset mounted into the container at `/demo-dataset/telematics_reduced_long.csv`, with `sensor_profile_canonical.json` kept alongside it as the profile sidecar for the same demo source.

Demo admin account:

- Email: `admin@example.com`
- Password: `admin123`

## Local development

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
python -m app.cli seed-demo
uvicorn app.main:app --reload
```

## Important environment variables

- `DATABASE_URL` - SQLAlchemy database URL, PostgreSQL in production/compose.
- `JWT_SECRET_KEY` - required replacement for any non-demo deployment.
- `USE_DEMO_DATA` - defaults to `true`; seed flows prefer the mounted reduced local dataset and fall back to the generated demo Pilot provider when the dataset is unavailable.
- `DEMO_DATASET_PATH` - optional path to the mounted demo dataset CSV/JSON/JSONL file.
- `DEMO_SENSOR_PROFILE_PATH` - optional sidecar profile path for the same demo dataset.
- `PILOT_*_URL` - optional official Pilot-GPS URLs supplied by deployment. Credentials are intentionally not documented or hardcoded.

## Main API groups

- `/api/pilot/sync/vehicles`, `/sensors`, `/readings`, `/all`, `/logs`
- `/api/vehicles`, `/{id}`, `/{id}/sensors`, `/{id}/metrics`, `/{id}/ratings`
- `/api/dashboard/summary?period=week`, `/timeseries`, `/comparison`, `/problem-vehicles`
- `/api/reports/fleet`, `/vehicle/{id}`, `/export/csv`
- `/api/ml/recalculate` (admin only), `/model-comparison`, `/anomalies`, `/clusters`, `/forecasts`, `/explanations/{vehicle_id}`

## Dataset import

```bash
cd backend
python -m app.cli import-dataset --path ./path/to/dataset.csv
```

Supported formats: CSV, JSON, JSONL. The importer writes normalized vehicles, sensors, and readings into the existing tables and then recalculates daily metric and rating windows for the imported time range.

For the thesis demo path, `seed-demo` now uses the reduced weekly dataset by default when `/demo-dataset/telematics_reduced_long.csv` is mounted, so `docker compose up --build` and `python -m app.cli seed-demo` produce dashboard/ML statistics from the same reproducible source.

Pilot-GPS calibrated historical sensor values are still treated as an integration blocker until official endpoint semantics are confirmed; demo mode and `raw_json` preservation remain the default safe path.
