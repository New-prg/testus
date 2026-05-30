from datetime import datetime
from typing import Any

from pydantic import BaseModel


class VehicleRead(BaseModel):
    id: str
    plate_number: str
    name: str
    vehicle_type: str
    imei: str
    rating: float
    fuel_per_100km: float
    idle_ratio: float
    coasting_ratio: float
    optimal_rpm_ratio: float
    brakes_per_100km: float
    high_speed_brakes_per_100km: float
    cruise_control_ratio: float
    overspeed_ratio: float
    analytics_readiness_percent: float
    last_sync_at: str | None


class VehicleSensorRead(BaseModel):
    id: str
    vehicle_id: str
    pilot_sensor_id: str | None
    name: str
    sensor_type: str
    unit: str | None
    is_active: bool

    model_config = {"from_attributes": True}


class SensorReadingRead(BaseModel):
    id: str
    vehicle_id: str
    sensor_id: str
    timestamp: datetime
    value: float | None
    speed: float | None
    raw_json: dict[str, Any] | None

    model_config = {"from_attributes": True}


class VehicleMetricRead(BaseModel):
    id: str
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

    model_config = {"from_attributes": True}
