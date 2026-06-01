from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config.analytics_sensors import (
    BRAKE_PEDAL_SENSOR,
    COASTING_SENSOR,
    CRUISE_CONTROL_SENSOR,
    DISTANCE_SENSOR,
    ENGINE_WORK_TIME_SENSOR,
    FUEL_SENSOR,
    HIGH_SPEED_BRAKING_THRESHOLD_KMH,
    IDLE_GRACE_SECONDS,
    IDLE_TIME_SENSOR,
    OPTIMAL_RPM_SENSOR,
    OVERSPEED_SENSOR,
    SPEED_SENSOR,
)
from app.db.models import AnalyticsSensorLink, SensorReading, VehicleMetricWindow, VehicleSensor


@dataclass(frozen=True)
class MetricWindowResult:
    vehicle_id: str
    period_start: datetime
    period_end: datetime
    distance_km: float
    fuel_consumed_liters: float | None
    fuel_per_100km: float | None
    coasting_ratio: float | None
    optimal_rpm_ratio: float | None
    idle_ratio: float | None
    brakes_per_100km: float | None
    high_speed_brakes_per_100km: float | None
    cruise_control_ratio: float | None
    overspeed_ratio: float | None
    engine_work_seconds: float
    moving_seconds: float
    idle_seconds: float
    raw_json: dict[str, Any]

    def to_model_dict(self) -> dict[str, Any]:
        return asdict(self)


class MetricCalculator:
    def calculate(self, db: Session, vehicle_id: str, period_start: datetime, period_end: datetime) -> MetricWindowResult:
        readings = self._readings_by_key(db, vehicle_id, period_start, period_end)
        distance_rows = readings.get(DISTANCE_SENSOR, [])
        fuel_rows = readings.get(FUEL_SENSOR, [])
        speed_rows = readings.get(SPEED_SENSOR, [])
        idle_rows = readings.get(IDLE_TIME_SENSOR, [])
        engine_rows = readings.get(ENGINE_WORK_TIME_SENSOR, [])
        brake_rows = readings.get(BRAKE_PEDAL_SENSOR, [])

        distance_km = round(self._counter_delta(distance_rows), 3)
        fuel_consumed_liters = round(self._counter_delta(fuel_rows), 3) if fuel_rows else None
        engine_work_seconds = round(sum((row.value or 0.0) for row in engine_rows), 3)
        moving_seconds = round(sum(self._interval_seconds(speed_rows, idx, period_end) for idx, row in enumerate(speed_rows) if (row.value or 0.0) > 3), 3)
        raw_idle_seconds = sum((row.value or 0.0) for row in idle_rows)
        idle_seconds = round(max(0.0, raw_idle_seconds - IDLE_GRACE_SECONDS), 3)
        fuel_per_100km = round((fuel_consumed_liters / distance_km) * 100, 3) if fuel_consumed_liters is not None and distance_km > 0 else None
        brake_count = sum(int(row.value or 0.0) for row in brake_rows)
        high_speed_brake_count = sum(int(row.value or 0.0) for row in brake_rows if (row.speed or 0.0) >= HIGH_SPEED_BRAKING_THRESHOLD_KMH)

        return MetricWindowResult(
            vehicle_id=vehicle_id,
            period_start=period_start,
            period_end=period_end,
            distance_km=distance_km,
            fuel_consumed_liters=fuel_consumed_liters,
            fuel_per_100km=fuel_per_100km,
            coasting_ratio=self._ratio(readings.get(COASTING_SENSOR, [])),
            optimal_rpm_ratio=self._ratio(readings.get(OPTIMAL_RPM_SENSOR, [])),
            idle_ratio=round(idle_seconds / engine_work_seconds, 4) if engine_work_seconds > 0 else None,
            brakes_per_100km=round((brake_count / distance_km) * 100, 3) if distance_km > 0 else None,
            high_speed_brakes_per_100km=round((high_speed_brake_count / distance_km) * 100, 3) if distance_km > 0 else None,
            cruise_control_ratio=self._ratio(readings.get(CRUISE_CONTROL_SENSOR, [])),
            overspeed_ratio=self._ratio(readings.get(OVERSPEED_SENSOR, [])),
            engine_work_seconds=engine_work_seconds,
            moving_seconds=moving_seconds,
            idle_seconds=idle_seconds,
            raw_json={"reading_counts": {key: len(value) for key, value in readings.items()}},
        )

    def calculate_and_store(self, db: Session, vehicle_id: str, period_start: datetime, period_end: datetime) -> VehicleMetricWindow:
        result = self.calculate(db, vehicle_id, period_start, period_end)
        db.execute(delete(VehicleMetricWindow).where(VehicleMetricWindow.vehicle_id == vehicle_id, VehicleMetricWindow.period_start == period_start, VehicleMetricWindow.period_end == period_end))
        window = VehicleMetricWindow(**result.to_model_dict())
        db.add(window)
        db.flush()
        return window

    @staticmethod
    def _readings_by_key(db: Session, vehicle_id: str, period_start: datetime, period_end: datetime) -> dict[str, list[SensorReading]]:
        rows = db.execute(
            select(SensorReading, AnalyticsSensorLink.analytics_key)
            .join(VehicleSensor, SensorReading.sensor_id == VehicleSensor.id)
            .join(AnalyticsSensorLink, AnalyticsSensorLink.sensor_id == VehicleSensor.id)
            .where(SensorReading.vehicle_id == vehicle_id)
            .where(SensorReading.timestamp >= period_start)
            .where(SensorReading.timestamp <= period_end)
            .where(AnalyticsSensorLink.is_active.is_(True))
            .order_by(AnalyticsSensorLink.analytics_key, SensorReading.timestamp)
        ).all()
        grouped: dict[str, list[SensorReading]] = {}
        for reading, key in rows:
            grouped.setdefault(key, []).append(reading)
        return grouped

    @staticmethod
    def _counter_delta(rows: list[SensorReading]) -> float:
        if len(rows) < 2:
            return 0.0
        total = 0.0
        previous = rows[0].value or 0.0
        for row in rows[1:]:
            current = row.value or 0.0
            delta = current - previous
            if delta > 0:
                total += delta
            previous = current
        return total

    @staticmethod
    def _ratio(rows: list[SensorReading]) -> float | None:
        if not rows:
            return None
        values = [row.value or 0.0 for row in rows]
        max_value = max(values)
        average = sum(values) / len(values)
        return round(average / 100 if max_value > 1 else average, 4)

    @staticmethod
    def _interval_seconds(rows: list[SensorReading], index: int, period_end: datetime) -> float:
        current = rows[index]
        next_row = rows[index + 1] if index + 1 < len(rows) else None
        end = next_row.timestamp if next_row else period_end
        return max(0.0, (end.replace(tzinfo=None) - current.timestamp.replace(tzinfo=None)).total_seconds())
