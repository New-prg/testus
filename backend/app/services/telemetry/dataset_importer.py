from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.analytics_sensors import ANALYTICS_SENSORS, resolve_analytics_key
from app.config.rating_profile import CAR_TYPE_UNKNOWN
from app.db.models import AnalyticsSensorLink, SensorReading, Vehicle, VehicleSensor
from app.services.telemetry.provider import TelemetryProvider
from app.services.pilot_gps.normalization import first_not_empty, normalize_sensor
from app.services.ratings.metric_calculator import MetricCalculator
from app.services.ratings.rating_calculator import RatingCalculator

MAX_DATASET_SIZE_BYTES = 25 * 1024 * 1024
MAX_IMPORT_ROWS = 200_000
MAX_IMPORT_RANGE_DAYS = 366


@dataclass(frozen=True)
class DatasetImportResult:
    vehicles: int
    sensors: int
    readings: int
    metric_windows: int
    skipped_rows: int

    def as_dict(self) -> dict[str, int]:
        return {
            "vehicles": self.vehicles,
            "sensors": self.sensors,
            "readings": self.readings,
            "metric_windows": self.metric_windows,
            "skipped_rows": self.skipped_rows,
        }


DatasetProvider = TelemetryProvider


class LocalDatasetProvider(TelemetryProvider):
    """Streams local CSV, JSON, or JSONL telemetry rows for reproducible demos."""

    def __init__(self, path: str | Path, max_size_bytes: int = MAX_DATASET_SIZE_BYTES, row_limit: int = MAX_IMPORT_ROWS) -> None:
        self.path = Path(path).expanduser().resolve()
        self.max_size_bytes = max_size_bytes
        self.row_limit = row_limit
        self._validate_path()

    def _validate_path(self) -> None:
        if not self.path.exists() or not self.path.is_file():
            raise ValueError(f"Dataset file does not exist: {self.path}")
        if self.path.is_symlink():
            raise ValueError(f"Dataset symlinks are not allowed: {self.path}")
        if self.max_size_bytes >= 0 and self.path.stat().st_size > self.max_size_bytes:
            raise ValueError(f"Dataset is too large: {self.path}")

    def iter_rows(self) -> Iterable[dict[str, Any]]:
        suffix = self.path.suffix.lower()
        if suffix == ".csv":
            with self.path.open(newline="", encoding="utf-8") as file:
                for row_count, row in enumerate(csv.DictReader(file), start=1):
                    self._validate_row_count(row_count)
                    yield dict(row)
                return
        if suffix == ".jsonl":
            with self.path.open(encoding="utf-8") as file:
                row_count = 0
                for line in file:
                    if line.strip():
                        payload = json.loads(line)
                        if isinstance(payload, dict):
                            row_count += 1
                            self._validate_row_count(row_count)
                            yield payload
                return
        if suffix == ".json":
            with self.path.open(encoding="utf-8") as file:
                payload = json.load(file)
            if isinstance(payload, list):
                row_count = 0
                for row in payload:
                    if isinstance(row, dict):
                        row_count += 1
                        self._validate_row_count(row_count)
                        yield row
                return
            if isinstance(payload, dict):
                nested_rows: Any = payload.get("rows") or payload.get("data") or payload.get("records")
                if isinstance(nested_rows, list):
                    row_count = 0
                    for row in nested_rows:
                        if isinstance(row, dict):
                            row_count += 1
                            self._validate_row_count(row_count)
                            yield row
                    return
                yield payload
                return
        raise ValueError(f"Unsupported dataset format: {self.path}")

    def _validate_row_count(self, row_count: int) -> None:
        if self.row_limit >= 0 and row_count > self.row_limit:
            raise ValueError(f"Dataset contains too many rows: {row_count}")


class DatasetImporter:
    def import_path(self, db: Session, path: str | Path) -> dict[str, int]:
        result = self.import_provider(db, LocalDatasetProvider(path))
        return result.as_dict()

    def import_provider(self, db: Session, provider: DatasetProvider) -> DatasetImportResult:
        imported_vehicle_ids: set[str] = set()
        created_sensors = 0
        inserted_readings = 0
        skipped_rows = 0
        min_timestamp: datetime | None = None
        max_timestamp: datetime | None = None
        flush_interval = 5_000
        processed_rows = 0

        for raw_row in provider.iter_rows():
            processed_rows += 1
            if processed_rows % 50_000 == 0:
                print(f"[seed-demo] Processed {processed_rows} source rows, inserted {inserted_readings} readings", flush=True)
            expanded_rows = self._expand_row(raw_row)
            if not expanded_rows:
                skipped_rows += 1
                continue
            for row in expanded_rows:
                normalized = self._normalize_row(row)
                if normalized is None:
                    skipped_rows += 1
                    continue
                vehicle = self._upsert_vehicle(db, normalized)
                sensor, created = self._upsert_sensor(db, vehicle, normalized)
                created_sensors += int(created)
                if self._insert_reading(db, vehicle, sensor, normalized):
                    inserted_readings += 1
                    if inserted_readings % flush_interval == 0:
                        db.flush()
                        db.expunge_all()
                imported_vehicle_ids.add(vehicle.id)
                timestamp = normalized["timestamp"]
                min_timestamp = timestamp if min_timestamp is None else min(min_timestamp, timestamp)
                max_timestamp = timestamp if max_timestamp is None else max(max_timestamp, timestamp)

        db.flush()
        metric_windows = self._derive_metrics_and_ratings(db, imported_vehicle_ids, min_timestamp, max_timestamp)
        db.commit()
        print(
            f"[seed-demo] Import complete: vehicles={len(imported_vehicle_ids)} sensors={created_sensors} readings={inserted_readings} metric_windows={metric_windows} skipped_rows={skipped_rows}",
            flush=True,
        )
        return DatasetImportResult(
            vehicles=len(imported_vehicle_ids),
            sensors=created_sensors,
            readings=inserted_readings,
            metric_windows=metric_windows,
            skipped_rows=skipped_rows,
        )

    def _expand_row(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        if row.get("record_type") == "sensor_day_chunk" and isinstance(row.get("sensor_data"), list):
            raw_vehicle = row.get("vehicle")
            raw_sensor = row.get("sensor")
            vehicle: dict[str, Any] = raw_vehicle if isinstance(raw_vehicle, dict) else {}
            sensor: dict[str, Any] = raw_sensor if isinstance(raw_sensor, dict) else {}
            expanded: list[dict[str, Any]] = []
            sensor_data = row["sensor_data"]
            for point in sensor_data:
                if not isinstance(point, dict):
                    continue
                expanded.append({**vehicle, **point, "sensor": sensor, "vehicle": vehicle})
            return expanded
        return [row]

    def _normalize_row(self, row: dict[str, Any]) -> dict[str, Any] | None:
        raw_vehicle = row.get("vehicle")
        raw_sensor = row.get("sensor")
        vehicle_payload: dict[str, Any] = raw_vehicle if isinstance(raw_vehicle, dict) else row
        sensor_payload: dict[str, Any] = raw_sensor if isinstance(raw_sensor, dict) else row
        timestamp = self._parse_timestamp(first_not_empty(row.get("timestamp"), row.get("recorded_at"), row.get("time"), row.get("unixtimestamp"), row.get("change_ts")))
        value = self._parse_float(first_not_empty(row.get("value"), row.get("hum_value"), row.get("dig_value"), row.get("raw_value"), row.get("last_raw_value")))
        if timestamp is None or value is None:
            return None
        sensor_name = str(first_not_empty(sensor_payload.get("name"), row.get("sensor_name"), row.get("name"), row.get("fieldname"), "") or "")
        analytics_key = first_not_empty(row.get("analytics_key"), row.get("canonical_feature"), sensor_payload.get("analytics_key"), row.get("sensor_key"), row.get("fieldname"))
        analytics_key = str(analytics_key) if analytics_key in ANALYTICS_SENSORS else resolve_analytics_key(sensor_name)
        sensor_id = first_not_empty(sensor_payload.get("id"), sensor_payload.get("sensor_id"), sensor_payload.get("tag_id"), row.get("sensor_id"), row.get("local_sensor_id"))
        return {
            "pilot_agent_id": str(first_not_empty(vehicle_payload.get("pilot_agent_id"), vehicle_payload.get("vehicle_agentid"), vehicle_payload.get("agentid"), vehicle_payload.get("agent_id"), vehicle_payload.get("vehicle_id"), vehicle_payload.get("vehicle_key"), vehicle_payload.get("imei"), vehicle_payload.get("plate_number"), vehicle_payload.get("vehiclenumber"), "local-dataset")),
            "imei": first_not_empty(vehicle_payload.get("imei"), vehicle_payload.get("uniqid"), vehicle_payload.get("unique_id")),
            "plate_number": first_not_empty(vehicle_payload.get("plate_number"), vehicle_payload.get("vehiclenumber"), vehicle_payload.get("number")),
            "name": str(first_not_empty(vehicle_payload.get("name"), vehicle_payload.get("title"), vehicle_payload.get("vehiclenumber"), vehicle_payload.get("plate_number"), "Dataset vehicle")),
            "vin": vehicle_payload.get("vin"),
            "vehicle_type": first_not_empty(vehicle_payload.get("vehicle_type"), vehicle_payload.get("type")),
            "car_type": str(first_not_empty(vehicle_payload.get("car_type"), CAR_TYPE_UNKNOWN)).upper(),
            "sensor_id": str(sensor_id) if sensor_id is not None else str(analytics_key or sensor_name or "dataset_sensor"),
            "sensor_name": sensor_name or str(analytics_key or "Dataset sensor"),
            "analytics_key": analytics_key,
            "unit": first_not_empty(sensor_payload.get("unit"), sensor_payload.get("measure_unit")),
            "timestamp": timestamp,
            "value": value,
            "speed": self._parse_float(first_not_empty(row.get("speed"), row.get("speed_kmh"), row.get("speed_from_point"))),
            "raw_json": self._json_safe(row),
        }

    def _upsert_vehicle(self, db: Session, row: dict[str, Any]) -> Vehicle:
        external_id = row["pilot_agent_id"]
        vehicle = db.scalar(select(Vehicle).where(Vehicle.pilot_agent_id == external_id))
        if vehicle is None and row.get("imei"):
            vehicle = db.scalar(select(Vehicle).where(Vehicle.imei == row["imei"]))
        if vehicle is None:
            vehicle = Vehicle(
                pilot_agent_id=external_id,
                imei=row.get("imei"),
                plate_number=row.get("plate_number"),
                name=row["name"],
                vin=row.get("vin"),
                vehicle_type=row.get("vehicle_type"),
                car_type=row["car_type"],
                is_active=True,
                raw_json={"provider": "local_dataset"},
            )
            db.add(vehicle)
            db.flush()
        else:
            vehicle.name = row["name"] or vehicle.name
            vehicle.plate_number = row.get("plate_number") or vehicle.plate_number
            vehicle.imei = row.get("imei") or vehicle.imei
            vehicle.vin = row.get("vin") or vehicle.vin
            vehicle.vehicle_type = row.get("vehicle_type") or vehicle.vehicle_type
            vehicle.car_type = row.get("car_type") or vehicle.car_type
        return vehicle

    def _upsert_sensor(self, db: Session, vehicle: Vehicle, row: dict[str, Any]) -> tuple[VehicleSensor, bool]:
        normalized_sensor = normalize_sensor({"id": row["sensor_id"], "name": row["sensor_name"], "type": row.get("analytics_key"), "raw_value": row["value"]})
        external_id = normalized_sensor["tag_id"] if normalized_sensor else row["sensor_id"]
        sensor = db.scalar(select(VehicleSensor).where(VehicleSensor.vehicle_id == vehicle.id, VehicleSensor.pilot_sensor_id == external_id))
        created = False
        if sensor is None:
            sensor = VehicleSensor(
                vehicle_id=vehicle.id,
                pilot_sensor_id=external_id,
                name=row["sensor_name"],
                sensor_type=str(row.get("analytics_key") or "dataset_sensor"),
                unit=row.get("unit"),
                is_active=True,
                raw_json={"provider": "local_dataset", "analytics_key": row.get("analytics_key")},
            )
            db.add(sensor)
            db.flush()
            created = True
        if row.get("analytics_key"):
            existing_link = db.scalar(select(AnalyticsSensorLink).where(AnalyticsSensorLink.vehicle_id == vehicle.id, AnalyticsSensorLink.analytics_key == row["analytics_key"]))
            if existing_link is None:
                spec = ANALYTICS_SENSORS[row["analytics_key"]]
                db.add(AnalyticsSensorLink(vehicle_id=vehicle.id, sensor_id=sensor.id, analytics_key=row["analytics_key"], is_required=spec["required"], is_active=True))
                db.flush()
                created = True
            elif existing_link.sensor_id != sensor.id:
                existing_link.sensor_id = sensor.id
                existing_link.is_active = True
                db.flush()
        return sensor, created

    def _insert_reading(self, db: Session, vehicle: Vehicle, sensor: VehicleSensor, row: dict[str, Any]) -> bool:
        exists = db.scalar(
            select(SensorReading.id)
            .where(SensorReading.vehicle_id == vehicle.id)
            .where(SensorReading.sensor_id == sensor.id)
            .where(SensorReading.timestamp == row["timestamp"])
            .limit(1)
        )
        if exists:
            return False
        db.add(SensorReading(vehicle_id=vehicle.id, sensor_id=sensor.id, timestamp=row["timestamp"], value=row["value"], speed=row.get("speed"), raw_json=row["raw_json"]))
        return True

    def _derive_metrics_and_ratings(self, db: Session, vehicle_ids: set[str], min_timestamp: datetime | None, max_timestamp: datetime | None) -> int:
        if not vehicle_ids or min_timestamp is None or max_timestamp is None:
            return 0
        metric_calculator = MetricCalculator()
        rating_calculator = RatingCalculator()
        start = min_timestamp.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        stop = max_timestamp.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        if (stop - start).days > MAX_IMPORT_RANGE_DAYS:
            raise ValueError("Dataset time range is too large for a single import")
        windows = 0
        current = start
        vehicles = db.scalars(select(Vehicle).where(Vehicle.id.in_(vehicle_ids))).all()
        while current < stop:
            period_end = current + timedelta(days=1)
            for vehicle in vehicles:
                metric_window = metric_calculator.calculate_and_store(db, vehicle.id, current, period_end)
                rating_calculator.calculate_and_store(db, vehicle, metric_window)
                windows += 1
            current = period_end
        return windows

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)
        if value in (None, ""):
            return None
        if isinstance(value, int | float) or (isinstance(value, str) and value.isdigit()):
            return datetime.fromtimestamp(int(value), tz=UTC)
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return None

    @staticmethod
    def _parse_float(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(str(value).replace(",", "."))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(key): DatasetImporter._json_safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [DatasetImporter._json_safe(item) for item in value]
        return value
