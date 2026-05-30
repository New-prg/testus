"""initial prompt-aligned schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-30
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def id_col() -> sa.Column[Any]:
    return sa.Column("id", sa.String(length=36), nullable=False)


def upgrade() -> None:
    op.create_table("users", id_col(), sa.Column("email", sa.String(255), nullable=False), sa.Column("password_hash", sa.String(255), nullable=False), sa.Column("full_name", sa.String(255)), sa.Column("role", sa.String(32), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.PrimaryKeyConstraint("id"))
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table("vehicles", id_col(), sa.Column("pilot_agent_id", sa.String(128)), sa.Column("imei", sa.String(64)), sa.Column("plate_number", sa.String(64)), sa.Column("name", sa.String(255), nullable=False), sa.Column("vin", sa.String(64)), sa.Column("vehicle_type", sa.String(64)), sa.Column("car_type", sa.String(32), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False), sa.Column("raw_json", sa.JSON()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.PrimaryKeyConstraint("id"))
    op.create_index(op.f("ix_vehicles_pilot_agent_id"), "vehicles", ["pilot_agent_id"], unique=True)
    op.create_index(op.f("ix_vehicles_imei"), "vehicles", ["imei"])
    op.create_index(op.f("ix_vehicles_plate_number"), "vehicles", ["plate_number"])
    op.create_index(op.f("ix_vehicles_vin"), "vehicles", ["vin"])
    op.create_index(op.f("ix_vehicles_car_type"), "vehicles", ["car_type"])

    op.create_table("drivers", id_col(), sa.Column("full_name", sa.String(255), nullable=False), sa.Column("phone", sa.String(64)), sa.Column("license_number", sa.String(128)), sa.Column("raw_json", sa.JSON()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.PrimaryKeyConstraint("id"))
    op.create_index(op.f("ix_drivers_license_number"), "drivers", ["license_number"])

    op.create_table("vehicle_sensors", id_col(), sa.Column("vehicle_id", sa.String(36), nullable=False), sa.Column("pilot_sensor_id", sa.String(128)), sa.Column("name", sa.String(255), nullable=False), sa.Column("sensor_type", sa.String(64), nullable=False), sa.Column("unit", sa.String(32)), sa.Column("is_active", sa.Boolean(), nullable=False), sa.Column("raw_json", sa.JSON()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"))
    op.create_index(op.f("ix_vehicle_sensors_vehicle_id"), "vehicle_sensors", ["vehicle_id"])
    op.create_index(op.f("ix_vehicle_sensors_pilot_sensor_id"), "vehicle_sensors", ["pilot_sensor_id"])

    op.create_table("analytics_sensor_links", id_col(), sa.Column("vehicle_id", sa.String(36), nullable=False), sa.Column("sensor_id", sa.String(36), nullable=False), sa.Column("analytics_key", sa.String(64), nullable=False), sa.Column("is_required", sa.Boolean(), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["sensor_id"], ["vehicle_sensors.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("vehicle_id", "analytics_key", name="uq_vehicle_analytics_key"))
    op.create_index(op.f("ix_analytics_sensor_links_vehicle_id"), "analytics_sensor_links", ["vehicle_id"])
    op.create_index(op.f("ix_analytics_sensor_links_sensor_id"), "analytics_sensor_links", ["sensor_id"])
    op.create_index(op.f("ix_analytics_sensor_links_analytics_key"), "analytics_sensor_links", ["analytics_key"])

    op.create_table("sensor_readings", id_col(), sa.Column("vehicle_id", sa.String(36), nullable=False), sa.Column("sensor_id", sa.String(36), nullable=False), sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False), sa.Column("value", sa.Float()), sa.Column("speed", sa.Float()), sa.Column("raw_json", sa.JSON()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["sensor_id"], ["vehicle_sensors.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_sensor_readings_vehicle_timestamp", "sensor_readings", ["vehicle_id", "timestamp"])
    op.create_index("ix_sensor_readings_sensor_timestamp", "sensor_readings", ["sensor_id", "timestamp"])

    op.create_table("vehicle_metric_windows", id_col(), sa.Column("vehicle_id", sa.String(36), nullable=False), sa.Column("period_start", sa.DateTime(timezone=True), nullable=False), sa.Column("period_end", sa.DateTime(timezone=True), nullable=False), sa.Column("distance_km", sa.Float(), nullable=False), sa.Column("fuel_consumed_liters", sa.Float()), sa.Column("fuel_per_100km", sa.Float()), sa.Column("coasting_ratio", sa.Float()), sa.Column("optimal_rpm_ratio", sa.Float()), sa.Column("idle_ratio", sa.Float()), sa.Column("brakes_per_100km", sa.Float()), sa.Column("high_speed_brakes_per_100km", sa.Float()), sa.Column("cruise_control_ratio", sa.Float()), sa.Column("overspeed_ratio", sa.Float()), sa.Column("engine_work_seconds", sa.Float(), nullable=False), sa.Column("moving_seconds", sa.Float(), nullable=False), sa.Column("idle_seconds", sa.Float(), nullable=False), sa.Column("raw_json", sa.JSON()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("vehicle_id", "period_start", "period_end", name="uq_vehicle_metric_window_period"))
    op.create_index(op.f("ix_vehicle_metric_windows_vehicle_id"), "vehicle_metric_windows", ["vehicle_id"])
    op.create_index(op.f("ix_vehicle_metric_windows_period_start"), "vehicle_metric_windows", ["period_start"])
    op.create_index(op.f("ix_vehicle_metric_windows_period_end"), "vehicle_metric_windows", ["period_end"])

    op.create_table("vehicle_rating_windows", id_col(), sa.Column("vehicle_id", sa.String(36), nullable=False), sa.Column("metric_window_id", sa.String(36)), sa.Column("period_start", sa.DateTime(timezone=True), nullable=False), sa.Column("period_end", sa.DateTime(timezone=True), nullable=False), sa.Column("car_type", sa.String(32), nullable=False), sa.Column("final_rating", sa.Float(), nullable=False), sa.Column("fuel_score", sa.Float()), sa.Column("coasting_score", sa.Float()), sa.Column("optimal_rpm_score", sa.Float()), sa.Column("idle_score", sa.Float()), sa.Column("brakes_score", sa.Float()), sa.Column("high_speed_brakes_score", sa.Float()), sa.Column("cruise_control_score", sa.Float()), sa.Column("overspeed_score", sa.Float()), sa.Column("weights_json", sa.JSON(), nullable=False), sa.Column("warnings_json", sa.JSON(), nullable=False), sa.Column("positive_factors_json", sa.JSON(), nullable=False), sa.Column("negative_factors_json", sa.JSON(), nullable=False), sa.Column("raw_json", sa.JSON()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["metric_window_id"], ["vehicle_metric_windows.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("vehicle_id", "period_start", "period_end", name="uq_vehicle_rating_window_period"))
    op.create_index(op.f("ix_vehicle_rating_windows_vehicle_id"), "vehicle_rating_windows", ["vehicle_id"])
    op.create_index(op.f("ix_vehicle_rating_windows_metric_window_id"), "vehicle_rating_windows", ["metric_window_id"])
    op.create_index(op.f("ix_vehicle_rating_windows_period_start"), "vehicle_rating_windows", ["period_start"])
    op.create_index(op.f("ix_vehicle_rating_windows_period_end"), "vehicle_rating_windows", ["period_end"])

    op.create_table("ml_results", id_col(), sa.Column("result_type", sa.String(64), nullable=False), sa.Column("vehicle_id", sa.String(36)), sa.Column("period_start", sa.DateTime(timezone=True)), sa.Column("period_end", sa.DateTime(timezone=True)), sa.Column("payload", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"))
    op.create_index(op.f("ix_ml_results_result_type"), "ml_results", ["result_type"])
    op.create_index(op.f("ix_ml_results_vehicle_id"), "ml_results", ["vehicle_id"])

    op.create_table("sync_logs", id_col(), sa.Column("sync_type", sa.String(64), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("message", sa.String(1000)), sa.Column("started_at", sa.DateTime(timezone=True), nullable=False), sa.Column("finished_at", sa.DateTime(timezone=True)), sa.Column("payload", sa.JSON()), sa.PrimaryKeyConstraint("id"))
    op.create_index(op.f("ix_sync_logs_sync_type"), "sync_logs", ["sync_type"])

    op.create_table("reports", id_col(), sa.Column("created_by_id", sa.String(36)), sa.Column("name", sa.String(255), nullable=False), sa.Column("report_type", sa.String(64), nullable=False), sa.Column("period_start", sa.Date(), nullable=False), sa.Column("period_end", sa.Date(), nullable=False), sa.Column("payload", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"), sa.PrimaryKeyConstraint("id"))
    op.create_index(op.f("ix_reports_created_by_id"), "reports", ["created_by_id"])


def downgrade() -> None:
    for table in ["reports", "sync_logs", "ml_results", "vehicle_rating_windows", "vehicle_metric_windows", "sensor_readings", "analytics_sensor_links", "vehicle_sensors", "drivers", "vehicles", "users"]:
        op.drop_table(table)
