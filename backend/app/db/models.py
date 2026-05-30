from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.rating_profile import CAR_TYPE_UNKNOWN
from app.db.session import Base


def new_uuid() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="user", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    reports: Mapped[list[Report]] = relationship(back_populates="created_by")

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_active(self) -> bool:
        return True


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    pilot_agent_id: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    imei: Mapped[str | None] = mapped_column(String(64), index=True)
    plate_number: Mapped[str | None] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    vin: Mapped[str | None] = mapped_column(String(64), index=True)
    vehicle_type: Mapped[str | None] = mapped_column(String(64))
    car_type: Mapped[str] = mapped_column(String(32), default=CAR_TYPE_UNKNOWN, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    sensors: Mapped[list[VehicleSensor]] = relationship(back_populates="vehicle", cascade="all, delete-orphan")
    analytics_links: Mapped[list[AnalyticsSensorLink]] = relationship(back_populates="vehicle", cascade="all, delete-orphan")
    readings: Mapped[list[SensorReading]] = relationship(back_populates="vehicle", cascade="all, delete-orphan")
    metric_windows: Mapped[list[VehicleMetricWindow]] = relationship(back_populates="vehicle", cascade="all, delete-orphan")
    rating_windows: Mapped[list[VehicleRatingWindow]] = relationship(back_populates="vehicle", cascade="all, delete-orphan")


class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(64))
    license_number: Mapped[str | None] = mapped_column(String(128), index=True)
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class VehicleSensor(Base):
    __tablename__ = "vehicle_sensors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False, index=True)
    pilot_sensor_id: Mapped[str | None] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sensor_type: Mapped[str] = mapped_column(String(64), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    vehicle: Mapped[Vehicle] = relationship(back_populates="sensors")
    analytics_links: Mapped[list[AnalyticsSensorLink]] = relationship(back_populates="sensor", cascade="all, delete-orphan")
    readings: Mapped[list[SensorReading]] = relationship(back_populates="sensor", cascade="all, delete-orphan")


class AnalyticsSensorLink(Base):
    __tablename__ = "analytics_sensor_links"
    __table_args__ = (UniqueConstraint("vehicle_id", "analytics_key", name="uq_vehicle_analytics_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False, index=True)
    sensor_id: Mapped[str] = mapped_column(ForeignKey("vehicle_sensors.id", ondelete="CASCADE"), nullable=False, index=True)
    analytics_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    is_required: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    vehicle: Mapped[Vehicle] = relationship(back_populates="analytics_links")
    sensor: Mapped[VehicleSensor] = relationship(back_populates="analytics_links")


class SensorReading(Base):
    __tablename__ = "sensor_readings"
    __table_args__ = (
        Index("ix_sensor_readings_vehicle_timestamp", "vehicle_id", "timestamp"),
        Index("ix_sensor_readings_sensor_timestamp", "sensor_id", "timestamp"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False)
    sensor_id: Mapped[str] = mapped_column(ForeignKey("vehicle_sensors.id", ondelete="CASCADE"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    value: Mapped[float | None] = mapped_column(Float)
    speed: Mapped[float | None] = mapped_column(Float)
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    vehicle: Mapped[Vehicle] = relationship(back_populates="readings")
    sensor: Mapped[VehicleSensor] = relationship(back_populates="readings")


class VehicleMetricWindow(Base):
    __tablename__ = "vehicle_metric_windows"
    __table_args__ = (UniqueConstraint("vehicle_id", "period_start", "period_end", name="uq_vehicle_metric_window_period"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False, index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    distance_km: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    fuel_consumed_liters: Mapped[float | None] = mapped_column(Float)
    fuel_per_100km: Mapped[float | None] = mapped_column(Float)
    coasting_ratio: Mapped[float | None] = mapped_column(Float)
    optimal_rpm_ratio: Mapped[float | None] = mapped_column(Float)
    idle_ratio: Mapped[float | None] = mapped_column(Float)
    brakes_per_100km: Mapped[float | None] = mapped_column(Float)
    high_speed_brakes_per_100km: Mapped[float | None] = mapped_column(Float)
    cruise_control_ratio: Mapped[float | None] = mapped_column(Float)
    overspeed_ratio: Mapped[float | None] = mapped_column(Float)
    engine_work_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    moving_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    idle_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    vehicle: Mapped[Vehicle] = relationship(back_populates="metric_windows")
    rating_window: Mapped[VehicleRatingWindow | None] = relationship(back_populates="metric_window")


class VehicleRatingWindow(Base):
    __tablename__ = "vehicle_rating_windows"
    __table_args__ = (UniqueConstraint("vehicle_id", "period_start", "period_end", name="uq_vehicle_rating_window_period"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False, index=True)
    metric_window_id: Mapped[str | None] = mapped_column(ForeignKey("vehicle_metric_windows.id", ondelete="SET NULL"), index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    car_type: Mapped[str] = mapped_column(String(32), nullable=False)
    final_rating: Mapped[float] = mapped_column(Float, nullable=False)
    fuel_score: Mapped[float | None] = mapped_column(Float)
    coasting_score: Mapped[float | None] = mapped_column(Float)
    optimal_rpm_score: Mapped[float | None] = mapped_column(Float)
    idle_score: Mapped[float | None] = mapped_column(Float)
    brakes_score: Mapped[float | None] = mapped_column(Float)
    high_speed_brakes_score: Mapped[float | None] = mapped_column(Float)
    cruise_control_score: Mapped[float | None] = mapped_column(Float)
    overspeed_score: Mapped[float | None] = mapped_column(Float)
    weights_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    warnings_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    positive_factors_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    negative_factors_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    vehicle: Mapped[Vehicle] = relationship(back_populates="rating_windows")
    metric_window: Mapped[VehicleMetricWindow | None] = relationship(back_populates="rating_window")

class MLResult(Base):
    __tablename__ = "ml_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    result_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    vehicle_id: Mapped[str | None] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"), index=True)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class SyncLog(Base):
    __tablename__ = "sync_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    sync_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str | None] = mapped_column(String(1000))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    report_type: Mapped[str] = mapped_column(String(64), default="fleet_summary", nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    created_by: Mapped[User | None] = relationship(back_populates="reports")
