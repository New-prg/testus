from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.config.analytics_sensors import ANALYTICS_SENSORS, resolve_analytics_key_from_candidates
from app.config.rating_profile import CAR_TYPE_UNKNOWN
from app.db.models import AnalyticsSensorLink, SensorReading, User, Vehicle, VehicleSensor, new_uuid
from app.services.telemetry.provider import TelemetryProvider
from app.services.pilot_gps.normalization import first_not_empty, normalize_sensor
from app.services.ratings.metric_calculator import MetricCalculator
from app.services.ratings.rating_calculator import RatingCalculator

MAX_DATASET_SIZE_BYTES = 25 * 1024 * 1024
MAX_IMPORT_ROWS = 200_000
MAX_IMPORT_RANGE_DAYS = 366
WIDE_DATASET_SENSOR_COLUMNS: tuple[tuple[str, str], ...] = (
    ("speed", "speed_from_point"),
    ("fuel_consumption", "fuel_consumption"),
    ("distance", "distance"),
    ("engine_work_time", "engine_work_time"),
    ("idle_time", "idle_time"),
    ("brake_pedal", "brake_pedal"),
    ("overspeed", "overspeed"),
    ("coasting", "coasting"),
    ("optimal_rpm", "optimal_rpm"),
    ("cruise_control", "cruise_control"),
)


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


@dataclass
class _DatasetImportCaches:
    vehicles_by_external_id: dict[str, Vehicle]
    vehicles_by_imei: dict[str, Vehicle]
    sensors_by_key: dict[tuple[str, str], VehicleSensor]
    links_by_key: dict[tuple[str, str], AnalyticsSensorLink]


@dataclass(frozen=True)
class _QueuedReading:
    vehicle_id: str
    sensor_id: str
    timestamp: datetime
    value: float | None
    speed: float | None
    raw_json: Any


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
    READING_BATCH_SIZE = 10_000
    EXISTING_READING_LOOKUP_CHUNK_SIZE = 500

    def import_path(self, db: Session, path: str | Path, owner: User) -> dict[str, int]:
        result = self.import_provider(db, LocalDatasetProvider(path), owner)
        return result.as_dict()

    def import_provider(self, db: Session, provider: DatasetProvider, owner: User) -> DatasetImportResult:
        caches = self._build_caches(db, owner)
        imported_vehicle_ids: set[str] = set()
        created_sensors = 0
        inserted_readings = 0
        skipped_rows = 0
        min_timestamp: datetime | None = None
        max_timestamp: datetime | None = None
        processed_rows = 0
        queued_readings: list[_QueuedReading] = []
        has_pending_entities = False

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
                vehicle, vehicle_created = self._upsert_vehicle(db, owner, normalized, caches)
                sensor, created, sensor_pending = self._upsert_sensor(db, vehicle, normalized, caches)
                created_sensors += int(created)
                has_pending_entities = has_pending_entities or vehicle_created or sensor_pending
                queued_readings.append(
                    _QueuedReading(
                        vehicle_id=vehicle.id,
                        sensor_id=sensor.id,
                        timestamp=normalized["timestamp"],
                        value=normalized["value"],
                        speed=normalized.get("speed"),
                        raw_json=normalized["raw_json"],
                    )
                )
                if len(queued_readings) >= self.READING_BATCH_SIZE:
                    inserted_readings += self._flush_reading_batch(db, queued_readings, has_pending_entities)
                    queued_readings.clear()
                    has_pending_entities = False
                imported_vehicle_ids.add(vehicle.id)
                timestamp = normalized["timestamp"]
                min_timestamp = timestamp if min_timestamp is None else min(min_timestamp, timestamp)
                max_timestamp = timestamp if max_timestamp is None else max(max_timestamp, timestamp)

        if queued_readings:
            inserted_readings += self._flush_reading_batch(db, queued_readings, has_pending_entities)

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
        if self._looks_like_wide_telematics_row(row):
            return self._expand_wide_telematics_row(row)
        return [row]

    def _expand_wide_telematics_row(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        expanded_wide_rows: list[dict[str, Any]] = []
        for analytics_key, source_column in WIDE_DATASET_SENSOR_COLUMNS:
            value = row.get(source_column)
            if value in (None, ""):
                continue
            expanded_wide_rows.append(
                {
                    **row,
                    "analytics_key": analytics_key,
                    "canonical_feature": analytics_key,
                    "local_sensor_id": f"wide:{analytics_key}",
                    "sensor_name": ANALYTICS_SENSORS[analytics_key]["pilot_name"],
                    "unit": ANALYTICS_SENSORS[analytics_key]["unit"],
                    "value": value,
                }
            )
        return expanded_wide_rows

    @staticmethod
    def _looks_like_wide_telematics_row(row: dict[str, Any]) -> bool:
        if first_not_empty(row.get("value"), row.get("hum_value"), row.get("dig_value"), row.get("raw_value"), row.get("last_raw_value")) not in (None, ""):
            return False
        if first_not_empty(row.get("analytics_key"), row.get("canonical_feature"), row.get("sensor_id"), row.get("local_sensor_id"), row.get("sensor_name"), row.get("name"), row.get("fieldname")) not in (None, ""):
            return False
        return any(row.get(source_column) not in (None, "") for _, source_column in WIDE_DATASET_SENSOR_COLUMNS)

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
        analytics_key = resolve_analytics_key_from_candidates(
            row.get("analytics_key"),
            row.get("canonical_feature"),
            sensor_payload.get("analytics_key"),
            row.get("sensor_key"),
            row.get("fieldname"),
            sensor_payload.get("fieldname"),
            sensor_name,
        )
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

    def _upsert_vehicle(self, db: Session, owner: User, row: dict[str, Any], caches: _DatasetImportCaches) -> tuple[Vehicle, bool]:
        external_id = row["pilot_agent_id"]
        imei = str(row["imei"]) if row.get("imei") else None
        vehicle = caches.vehicles_by_external_id.get(external_id)
        if vehicle is None and imei:
            vehicle = caches.vehicles_by_imei.get(imei)
        created = False
        if vehicle is None:
            vehicle = Vehicle(
                id=new_uuid(),
                user_id=owner.id,
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
            caches.vehicles_by_external_id[external_id] = vehicle
            if imei:
                caches.vehicles_by_imei[imei] = vehicle
            created = True
        else:
            vehicle.name = row["name"] or vehicle.name
            vehicle.plate_number = row.get("plate_number") or vehicle.plate_number
            vehicle.imei = row.get("imei") or vehicle.imei
            vehicle.vin = row.get("vin") or vehicle.vin
            vehicle.vehicle_type = row.get("vehicle_type") or vehicle.vehicle_type
            vehicle.car_type = row.get("car_type") or vehicle.car_type
            caches.vehicles_by_external_id.setdefault(external_id, vehicle)
            if imei:
                caches.vehicles_by_imei[imei] = vehicle
        return vehicle, created

    def _upsert_sensor(self, db: Session, vehicle: Vehicle, row: dict[str, Any], caches: _DatasetImportCaches) -> tuple[VehicleSensor, bool, bool]:
        normalized_sensor = normalize_sensor({"id": row["sensor_id"], "name": row["sensor_name"], "type": row.get("analytics_key"), "raw_value": row["value"]})
        external_id = normalized_sensor["tag_id"] if normalized_sensor else row["sensor_id"]
        sensor_key = (vehicle.id, external_id)
        sensor = caches.sensors_by_key.get(sensor_key)
        created = False
        pending = False
        if sensor is None:
            sensor = VehicleSensor(
                id=new_uuid(),
                vehicle_id=vehicle.id,
                pilot_sensor_id=external_id,
                name=row["sensor_name"],
                sensor_type=str(row.get("analytics_key") or "dataset_sensor"),
                unit=row.get("unit"),
                is_active=True,
                raw_json={"provider": "local_dataset", "analytics_key": row.get("analytics_key")},
            )
            db.add(sensor)
            caches.sensors_by_key[sensor_key] = sensor
            created = True
            pending = True
        if row.get("analytics_key"):
            analytics_key = str(row["analytics_key"])
            link_key = (vehicle.id, analytics_key)
            existing_link = caches.links_by_key.get(link_key)
            if existing_link is None:
                spec = ANALYTICS_SENSORS[analytics_key]
                existing_link = AnalyticsSensorLink(
                    id=new_uuid(),
                    vehicle_id=vehicle.id,
                    sensor_id=sensor.id,
                    analytics_key=analytics_key,
                    is_required=spec["required"],
                    is_active=True,
                )
                db.add(existing_link)
                caches.links_by_key[link_key] = existing_link
                created = True
                pending = True
            elif existing_link.sensor_id != sensor.id:
                existing_link.sensor_id = sensor.id
                existing_link.is_active = True
        return sensor, created, pending

    def _flush_reading_batch(self, db: Session, queued_readings: list[_QueuedReading], has_pending_entities: bool) -> int:
        if not queued_readings:
            return 0
        if has_pending_entities:
            db.flush()

        deduped_rows: dict[tuple[str, str, datetime], _QueuedReading] = {}
        for reading in queued_readings:
            deduped_rows.setdefault(self._reading_key(reading.vehicle_id, reading.sensor_id, reading.timestamp), reading)

        if not deduped_rows:
            return 0

        existing_keys = self._load_existing_reading_keys(db, list(deduped_rows.keys()))
        insert_rows = [
            {
                "id": new_uuid(),
                "vehicle_id": reading.vehicle_id,
                "sensor_id": reading.sensor_id,
                "timestamp": reading.timestamp,
                "value": reading.value,
                "speed": reading.speed,
                "raw_json": reading.raw_json,
            }
            for key, reading in deduped_rows.items()
            if key not in existing_keys
        ]
        if not insert_rows:
            return 0

        db.execute(insert(SensorReading), insert_rows)
        return len(insert_rows)

    def _load_existing_reading_keys(self, db: Session, keys: list[tuple[str, str, datetime]]) -> set[tuple[str, str, datetime]]:
        existing_keys: set[tuple[str, str, datetime]] = set()
        dialect_name = db.get_bind().dialect.name
        timestamps_by_sensor: dict[str, set[datetime]] = {}
        for _, sensor_id, timestamp in keys:
            timestamps_by_sensor.setdefault(sensor_id, set()).add(timestamp)

        for sensor_id, timestamps in timestamps_by_sensor.items():
            ordered_timestamps = sorted(timestamps)
            for offset in range(0, len(ordered_timestamps), self.EXISTING_READING_LOOKUP_CHUNK_SIZE):
                chunk = ordered_timestamps[offset : offset + self.EXISTING_READING_LOOKUP_CHUNK_SIZE]
                comparable_chunk = [timestamp.replace(tzinfo=None) for timestamp in chunk] if dialect_name == "sqlite" else chunk
                rows = db.execute(
                    select(SensorReading.vehicle_id, SensorReading.sensor_id, SensorReading.timestamp)
                    .where(SensorReading.sensor_id == sensor_id)
                    .where(SensorReading.timestamp.in_(comparable_chunk))
                ).all()
                existing_keys.update(
                    self._reading_key(vehicle_id, existing_sensor_id, timestamp)
                    for vehicle_id, existing_sensor_id, timestamp in rows
                )
        return existing_keys

    @staticmethod
    def _reading_key(vehicle_id: str, sensor_id: str, timestamp: datetime) -> tuple[str, str, datetime]:
        normalized_timestamp = timestamp.astimezone(UTC).replace(tzinfo=None) if timestamp.tzinfo else timestamp
        return vehicle_id, sensor_id, normalized_timestamp

    def _build_caches(self, db: Session, owner: User) -> _DatasetImportCaches:
        vehicles = db.scalars(select(Vehicle).where(Vehicle.user_id == owner.id)).all()
        sensors = db.scalars(select(VehicleSensor).join(Vehicle, Vehicle.id == VehicleSensor.vehicle_id).where(Vehicle.user_id == owner.id)).all()
        links = db.scalars(select(AnalyticsSensorLink).join(Vehicle, Vehicle.id == AnalyticsSensorLink.vehicle_id).where(Vehicle.user_id == owner.id)).all()
        return _DatasetImportCaches(
            vehicles_by_external_id={vehicle.pilot_agent_id: vehicle for vehicle in vehicles if vehicle.pilot_agent_id},
            vehicles_by_imei={vehicle.imei: vehicle for vehicle in vehicles if vehicle.imei},
            sensors_by_key={(sensor.vehicle_id, sensor.pilot_sensor_id): sensor for sensor in sensors if sensor.pilot_sensor_id},
            links_by_key={(link.vehicle_id, link.analytics_key): link for link in links},
        )

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
