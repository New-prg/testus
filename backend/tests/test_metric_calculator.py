from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.config.analytics_sensors import ANALYTICS_SENSORS
from app.db.models import AnalyticsSensorLink, SensorReading, Vehicle, VehicleSensor
from app.db.session import Base
from app.services.ratings.metric_calculator import MetricCalculator


def build_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def ensure_sensor(db: Session, vehicle: Vehicle, analytics_key: str) -> VehicleSensor:
    spec = ANALYTICS_SENSORS[analytics_key]
    sensor = VehicleSensor(vehicle_id=vehicle.id, pilot_sensor_id=analytics_key, name=spec["pilot_name"], sensor_type=spec["kind"], unit=spec["unit"], is_active=True)
    db.add(sensor)
    db.flush()
    db.add(AnalyticsSensorLink(vehicle_id=vehicle.id, sensor_id=sensor.id, analytics_key=analytics_key, is_required=spec["required"], is_active=True))
    db.flush()
    return sensor


def add_reading(db: Session, vehicle: Vehicle, sensor: VehicleSensor, at: datetime, value: float, speed: float | None = None) -> None:
    db.add(SensorReading(vehicle_id=vehicle.id, sensor_id=sensor.id, timestamp=at, value=value, speed=speed, raw_json={"test": True}))


def test_metric_calculator_respects_idle_grace_and_high_speed_braking() -> None:
    db = build_session()
    vehicle = Vehicle(name="Test vehicle")
    db.add(vehicle)
    db.flush()
    sensors = {key: ensure_sensor(db, vehicle, key) for key in ["distance", "fuel_consumption", "coasting", "optimal_rpm", "idle_time", "engine_work_time", "brake_pedal", "cruise_control", "overspeed", "speed"]}
    start = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
    end = start + timedelta(hours=3)

    add_reading(db, vehicle, sensors["distance"], start, 100)
    add_reading(db, vehicle, sensors["distance"], end, 220)
    add_reading(db, vehicle, sensors["fuel_consumption"], start, 20)
    add_reading(db, vehicle, sensors["fuel_consumption"], end, 44)
    add_reading(db, vehicle, sensors["coasting"], start, 0.30)
    add_reading(db, vehicle, sensors["optimal_rpm"], start, 0.60)
    add_reading(db, vehicle, sensors["idle_time"], start, 1800)
    add_reading(db, vehicle, sensors["engine_work_time"], start, 7200)
    add_reading(db, vehicle, sensors["brake_pedal"], start, 3, 80)
    add_reading(db, vehicle, sensors["cruise_control"], start, 0.12)
    add_reading(db, vehicle, sensors["overspeed"], start, 0.05)
    add_reading(db, vehicle, sensors["speed"], start, 75, 75)
    db.commit()

    result = MetricCalculator().calculate(db, vehicle.id, start, end)

    assert result.distance_km == 120
    assert result.fuel_consumed_liters == 24
    assert result.fuel_per_100km == 20
    assert result.idle_seconds == 1200
    assert result.idle_ratio == 0.1667
    assert result.brakes_per_100km == 2.5
    assert result.high_speed_brakes_per_100km == 2.5
