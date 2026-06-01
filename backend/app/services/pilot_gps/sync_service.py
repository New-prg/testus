from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config.analytics_sensors import ANALYTICS_SENSORS, TOTAL_ANALYTICS_SENSORS, resolve_analytics_key
from app.core.security import decrypt_secret
from app.db.models import AnalyticsSensorLink, MLResult, SensorReading, SyncLog, User, Vehicle, VehicleSensor, utcnow
from app.services.pilot_gps.client import HttpPilotGpsClient, PilotGpsClient, get_pilot_client
from app.services.pilot_gps.sensor_parser import PilotSensorParser
from app.services.pilot_gps.vehicle_parser import PilotVehicleParser
from app.services.ratings.metric_calculator import MetricCalculator
from app.services.ratings.rating_calculator import RatingCalculator


class PilotSyncService:
    def __init__(self, client: PilotGpsClient | None = None) -> None:
        self.client = client or get_pilot_client()
        self.vehicle_parser = PilotVehicleParser()
        self.sensor_parser = PilotSensorParser()

    def sync_vehicles(self, db: Session, owner: User) -> dict[str, Any]:
        log = self._start_log(db, "vehicles")
        synced = 0
        for payload in self.client.list_vehicles():
            parsed = self.vehicle_parser.parse(payload)
            vehicle = db.scalar(select(Vehicle).where(Vehicle.user_id == owner.id, Vehicle.pilot_agent_id == parsed["pilot_agent_id"]))
            if vehicle:
                for key, value in parsed.items():
                    setattr(vehicle, key, value)
            else:
                vehicle = Vehicle(user_id=owner.id, **parsed)
                db.add(vehicle)
                db.flush()
            self.ensure_sensors_and_links(db, vehicle)
            synced += 1
        self._finish_log(log, "success", {"synced": synced})
        db.commit()
        return {"synced": synced}

    def sync_sensors(self, db: Session, owner: User) -> dict[str, Any]:
        log = self._start_log(db, "sensors")
        created = 0
        for vehicle in db.scalars(select(Vehicle).where(Vehicle.user_id == owner.id)).all():
            created += self.ensure_sensors_and_links(db, vehicle)
        self._finish_log(log, "success", {"created": created})
        db.commit()
        return {"created": created}

    def sync_readings(self, db: Session, owner: User, days: int = 30) -> dict[str, Any]:
        log = self._start_log(db, "readings")
        inserted = 0
        for vehicle in db.scalars(select(Vehicle).where(Vehicle.user_id == owner.id)).all():
            if not vehicle.pilot_agent_id:
                continue
            if db.scalar(select(SensorReading.id).where(SensorReading.vehicle_id == vehicle.id).limit(1)):
                continue
            history = self.client.list_sensor_history(vehicle.pilot_agent_id, days)
            sensors_by_key = {link.analytics_key: link.sensor for link in vehicle.analytics_links if link.sensor is not None}
            for key, rows in history.items():
                sensor = sensors_by_key.get(key)
                if not sensor:
                    continue
                for row in rows:
                    parsed = self.sensor_parser.parse_reading(row)
                    db.add(SensorReading(vehicle_id=vehicle.id, sensor_id=sensor.id, **parsed))
                    inserted += 1
        self._finish_log(log, "success", {"inserted": inserted})
        db.commit()
        return {"inserted": inserted}

    def calculate_analytics(self, db: Session, owner: User, days: int = 30) -> dict[str, Any]:
        log = self._start_log(db, "analytics")
        metric_calculator = MetricCalculator()
        rating_calculator = RatingCalculator()
        windows = 0
        end = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        for vehicle in db.scalars(select(Vehicle).where(Vehicle.user_id == owner.id, Vehicle.is_active.is_(True))).all():
            for offset in range(days):
                period_start = end - timedelta(days=offset + 1)
                period_end = end - timedelta(days=offset)
                metric_window = metric_calculator.calculate_and_store(db, vehicle.id, period_start, period_end)
                rating_calculator.calculate_and_store(db, vehicle, metric_window)
                windows += 1
        self._finish_log(log, "success", {"metric_windows": windows})
        db.commit()
        return {"metric_windows": windows}

    def sync_all(self, db: Session, owner: User, days: int = 30) -> dict[str, Any]:
        return {
            "vehicles": self.sync_vehicles(db, owner),
            "sensors": self.sync_sensors(db, owner),
            "readings": self.sync_readings(db, owner, days),
            "analytics": self.calculate_analytics(db, owner, days),
        }

    def import_live_current_snapshot(self, db: Session, owner: User, replace_shared_fleet: bool = False, anonymize: bool = False) -> dict[str, Any]:
        log = self._start_log(db, "live_current_snapshot")
        vehicles_payload = self.client.list_vehicles()
        if replace_shared_fleet:
            self._clear_fleet(db, owner)
        anonymized_payloads = self._anonymize_payloads(vehicles_payload) if anonymize else vehicles_payload
        agent_ids = [str(payload.get("agentid") or payload.get("pilot_agent_id") or payload.get("id")) for payload in anonymized_payloads if payload.get("agentid") or payload.get("pilot_agent_id") or payload.get("id")]
        status_map = self.client.list_current_status(agent_ids)
        imported_vehicles = 0
        imported_sensors = 0
        imported_readings = 0
        unmapped: dict[str, list[str]] = {}

        for payload in anonymized_payloads:
            parsed = self.vehicle_parser.parse(payload)
            vehicle = db.scalar(select(Vehicle).where(Vehicle.user_id == owner.id, Vehicle.pilot_agent_id == parsed["pilot_agent_id"]))
            if vehicle:
                for key, value in parsed.items():
                    setattr(vehicle, key, value)
            else:
                vehicle = Vehicle(user_id=owner.id, **parsed)
                db.add(vehicle)
                db.flush()
            imported_vehicles += 1

            status_payload = status_map.get(str(vehicle.pilot_agent_id), {})
            sensor_count, unmapped_names = self._sync_live_vehicle_sensors(db, vehicle, payload.get("sensors", []), status_payload.get("sensors_status", payload.get("sensors_status", [])))
            reading_count = self._sync_live_vehicle_readings(db, vehicle, status_payload.get("sensors_status", payload.get("sensors_status", [])))
            imported_sensors += sensor_count
            imported_readings += reading_count
            if unmapped_names:
                unmapped[vehicle.id] = unmapped_names

        self._finish_log(log, "success", {"vehicles": imported_vehicles, "sensors": imported_sensors, "readings": imported_readings, "analytics_readiness_total": TOTAL_ANALYTICS_SENSORS, "unmapped_sensors": unmapped, "replace_shared_fleet": replace_shared_fleet, "anonymize": anonymize})
        db.commit()
        return {"vehicles": imported_vehicles, "sensors": imported_sensors, "readings": imported_readings, "unmapped_sensors": unmapped, "replace_shared_fleet": replace_shared_fleet, "anonymize": anonymize}

    @staticmethod
    def _clear_fleet(db: Session, owner: User) -> None:
        vehicle_ids = select(Vehicle.id).where(Vehicle.user_id == owner.id)
        db.execute(delete(MLResult).where(MLResult.vehicle_id.in_(vehicle_ids)))
        db.execute(delete(Vehicle).where(Vehicle.user_id == owner.id))
        db.flush()

    def sync_account_current_snapshot(self, db: Session, owner: User) -> dict[str, Any]:
        if not owner.pilot_server_address or owner.pilot_node is None or not owner.pilot_password_encrypted:
            raise ValueError("Pilot-GPS account is not configured")
        if owner.is_demo:
            return {"vehicles": 0, "sensors": 0, "readings": 0, "skipped": True}
        live_client = HttpPilotGpsClient(
            base_url=owner.pilot_server_address,
            node=owner.pilot_node,
            username=owner.login,
            password=decrypt_secret(owner.pilot_password_encrypted),
        )
        result = PilotSyncService(live_client).import_live_current_snapshot(db, owner)
        self.recalculate_account_windows(db, owner)
        return result

    def recalculate_account_windows(self, db: Session, owner: User) -> int:
        metric_calculator = MetricCalculator()
        rating_calculator = RatingCalculator()
        windows = 0
        start_at = owner.sync_started_at or utcnow()
        current = start_at.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        stop = utcnow().astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        vehicles = db.scalars(select(Vehicle).where(Vehicle.user_id == owner.id, Vehicle.is_active.is_(True))).all()
        while current < stop:
            period_end = current + timedelta(days=1)
            for vehicle in vehicles:
                metric_window = metric_calculator.calculate_and_store(db, vehicle.id, current, period_end)
                rating_calculator.calculate_and_store(db, vehicle, metric_window)
                windows += 1
            current = period_end
        db.commit()
        return windows

    def run_due_account_syncs(self, db: Session, now: datetime | None = None) -> list[dict[str, Any]]:
        now = now or utcnow()
        users = db.scalars(select(User).where(User.is_demo.is_(False), User.next_sync_at.is_not(None), User.next_sync_at <= now).order_by(User.next_sync_at.asc())).all()
        results: list[dict[str, Any]] = []
        for user in users:
            user.last_sync_started_at = now
            user.last_sync_error = None
            db.commit()
            try:
                result = self.sync_account_current_snapshot(db, user)
                finished_at = utcnow()
                user.last_sync_completed_at = finished_at
                user.next_sync_at = self._next_sync_from_anchor(user, finished_at)
                db.commit()
                results.append({"user_id": user.id, "status": "success", **result})
            except Exception as exc:
                user.last_sync_error = self._safe_sync_error(exc)
                user.next_sync_at = utcnow() + timedelta(minutes=15)
                db.commit()
                results.append({"user_id": user.id, "status": "error", "message": str(exc)})
        return results

    @staticmethod
    def _next_sync_from_anchor(owner: User, completed_at: datetime) -> datetime:
        anchor = owner.sync_started_at or completed_at
        anchor_utc = anchor.astimezone(UTC) if anchor.tzinfo else anchor.replace(tzinfo=UTC)
        completed_utc = completed_at.astimezone(UTC) if completed_at.tzinfo else completed_at.replace(tzinfo=UTC)
        next_sync = anchor_utc
        while next_sync <= completed_utc:
            next_sync += timedelta(hours=3)
        return next_sync

    @staticmethod
    def _safe_sync_error(exc: Exception) -> str:
        message = str(exc)
        lowered = message.lower()
        if any(token in lowered for token in ("authorization", "password", "token", "basic ", "bearer ")):
            return "Pilot-GPS sync failed"
        return message[:1000]

    @staticmethod
    def _anonymize_payloads(vehicles_payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ordered = sorted(
            [dict(payload) for payload in vehicles_payload],
            key=lambda payload: str(payload.get("agentid") or payload.get("pilot_agent_id") or payload.get("id") or ""),
        )
        anonymized: list[dict[str, Any]] = []
        for index, payload in enumerate(ordered, start=1):
            masked = dict(payload)
            masked["name"] = f"Vehicle {index:03d}"
            masked["vehiclenumber"] = f"ANON-{index:03d}"
            masked["plate_number"] = f"ANON-{index:03d}"
            masked["imei"] = f"IMEI-{index:03d}"
            masked["vin"] = f"VIN-{index:03d}"
            raw = dict(masked.get("raw_json") or {})
            raw["anonymized"] = True
            raw["anonymized_index"] = index
            masked["raw_json"] = raw
            anonymized.append(masked)
        return anonymized

    @staticmethod
    def ensure_sensors_and_links(db: Session, vehicle: Vehicle) -> int:
        created = 0
        existing_sensors = {sensor.sensor_type: sensor for sensor in vehicle.sensors}
        existing_links = {link.analytics_key for link in vehicle.analytics_links}
        for key, spec in ANALYTICS_SENSORS.items():
            sensor = existing_sensors.get(key)
            if not sensor:
                sensor = VehicleSensor(
                    vehicle_id=vehicle.id,
                    pilot_sensor_id=f"{vehicle.pilot_agent_id}:{key}",
                    name=spec["pilot_name"],
                    sensor_type=key,
                    unit=spec["unit"],
                    is_active=True,
                    raw_json={"analytics_key": key, "demo": vehicle.pilot_agent_id is not None and vehicle.pilot_agent_id.startswith("demo")},
                )
                db.add(sensor)
                db.flush()
                created += 1
            if key not in existing_links:
                db.add(AnalyticsSensorLink(vehicle_id=vehicle.id, sensor_id=sensor.id, analytics_key=key, is_required=spec["required"], is_active=True))
                created += 1
        db.flush()
        return created

    def _sync_live_vehicle_sensors(self, db: Session, vehicle: Vehicle, sensors_payload: list[dict[str, Any]], sensors_status_payload: list[dict[str, Any]]) -> tuple[int, list[str]]:
        merged_by_name: dict[str, dict[str, Any]] = {}
        for payload in sensors_payload:
            name = str(payload.get("name") or payload.get("description") or "")
            if name:
                merged_by_name[name] = dict(payload)
        for payload in sensors_status_payload:
            name = str(payload.get("name") or "")
            if not name:
                continue
            merged = merged_by_name.setdefault(name, {})
            merged.update(payload)

        existing_by_sensor_id = {sensor.pilot_sensor_id: sensor for sensor in vehicle.sensors if sensor.pilot_sensor_id}
        existing_by_name = {sensor.name: sensor for sensor in vehicle.sensors}
        existing_links = {link.analytics_key: link for link in vehicle.analytics_links}
        mapped_links: set[str] = set()
        created = 0
        unmapped_names: list[str] = []

        for payload in merged_by_name.values():
            analytics_key = resolve_analytics_key(str(payload.get("name") or payload.get("description") or ""))
            sensor_dict = self.sensor_parser.parse_vehicle_sensor(payload, analytics_key)
            sensor = None
            if sensor_dict["pilot_sensor_id"]:
                sensor = existing_by_sensor_id.get(sensor_dict["pilot_sensor_id"])
            if sensor is None:
                sensor = existing_by_name.get(sensor_dict["name"])
            if sensor:
                for key, value in sensor_dict.items():
                    setattr(sensor, key, value)
            else:
                sensor = VehicleSensor(vehicle_id=vehicle.id, **sensor_dict)
                db.add(sensor)
                db.flush()
                created += 1
            if analytics_key:
                link = existing_links.get(analytics_key)
                if link:
                    link.sensor_id = sensor.id
                    link.is_required = ANALYTICS_SENSORS[analytics_key]["required"]
                    link.is_active = True
                else:
                    link = AnalyticsSensorLink(vehicle_id=vehicle.id, sensor_id=sensor.id, analytics_key=analytics_key, is_required=ANALYTICS_SENSORS[analytics_key]["required"], is_active=True)
                    db.add(link)
                    existing_links[analytics_key] = link
                    created += 1
                mapped_links.add(analytics_key)
            else:
                unmapped_names.append(sensor.name)

        db.flush()
        return created, sorted(set(unmapped_names))

    def _sync_live_vehicle_readings(self, db: Session, vehicle: Vehicle, sensors_status_payload: list[dict[str, Any]]) -> int:
        sensors = db.scalars(select(VehicleSensor).where(VehicleSensor.vehicle_id == vehicle.id)).all()
        sensors_by_external_id = {sensor.pilot_sensor_id: sensor for sensor in sensors if sensor.pilot_sensor_id}
        sensors_by_name = {sensor.name: sensor for sensor in sensors}
        inserted = 0
        for payload in sensors_status_payload:
            reading = self.sensor_parser.parse_status_reading(payload)
            if reading is None:
                continue
            sensor = None
            sensor_id = str(payload.get("id")) if payload.get("id") is not None else None
            if sensor_id:
                sensor = sensors_by_external_id.get(sensor_id)
            if sensor is None:
                sensor = sensors_by_name.get(str(payload.get("name") or ""))
            if sensor is None:
                continue
            existing_reading = db.scalar(
                select(SensorReading.id)
                .where(SensorReading.vehicle_id == vehicle.id)
                .where(SensorReading.sensor_id == sensor.id)
                .where(SensorReading.timestamp == reading["timestamp"])
                .limit(1)
            )
            if existing_reading:
                continue
            db.add(SensorReading(vehicle_id=vehicle.id, sensor_id=sensor.id, **reading))
            inserted += 1
        db.flush()
        return inserted

    @staticmethod
    def _start_log(db: Session, sync_type: str) -> SyncLog:
        log = SyncLog(sync_type=sync_type, status="started")
        db.add(log)
        db.flush()
        return log

    @staticmethod
    def _finish_log(log: SyncLog, status: str, payload: dict[str, Any]) -> None:
        log.status = status
        log.finished_at = datetime.now(UTC)
        log.payload = payload
