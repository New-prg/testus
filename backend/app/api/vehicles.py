from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api import deps
from app.config.analytics_sensors import TOTAL_ANALYTICS_SENSORS
from app.db.models import Vehicle, VehicleMetricWindow, VehicleRatingWindow, VehicleSensor
from app.db.session import get_db
from app.schemas.rating import RatingRead
from app.schemas.vehicle import VehicleMetricRead, VehicleRead, VehicleSensorRead


router = APIRouter(prefix="/vehicles", tags=["vehicles"], dependencies=[Depends(deps.get_fleet_access_user)])


def _vehicles_with_analytics_query():
    return (
        select(Vehicle)
        .options(
            selectinload(Vehicle.metric_windows),
            selectinload(Vehicle.rating_windows),
            selectinload(Vehicle.analytics_links),
            selectinload(Vehicle.readings),
        )
        .order_by(Vehicle.name)
    )


def _load_vehicles_with_analytics(db: Session) -> list[Vehicle]:
    return list(db.scalars(_vehicles_with_analytics_query()).all())


def _load_vehicle_with_analytics(db: Session, vehicle_id: str) -> Vehicle | None:
    return db.scalar(_vehicles_with_analytics_query().where(Vehicle.id == vehicle_id))


def _vehicle_row(vehicle: Vehicle) -> dict[str, Any]:
    metrics = sorted(vehicle.metric_windows, key=lambda row: row.period_end, reverse=True)
    ratings = sorted(vehicle.rating_windows, key=lambda row: row.period_end, reverse=True)
    latest_metric = metrics[0] if metrics else None
    latest_rating = ratings[0] if ratings else None
    readiness_total = TOTAL_ANALYTICS_SENSORS or 1
    readiness_active = len({link.analytics_key for link in vehicle.analytics_links if link.is_active})
    last_sync_at = max((reading.timestamp for reading in vehicle.readings), default=None)
    return {
        "id": vehicle.id,
        "plate_number": vehicle.plate_number or "—",
        "name": vehicle.name,
        "vehicle_type": vehicle.vehicle_type or "UNKNOWN",
        "imei": vehicle.imei or "—",
        "rating": float(latest_rating.final_rating if latest_rating else 0.0),
        "fuel_per_100km": float(latest_metric.fuel_per_100km if latest_metric and latest_metric.fuel_per_100km is not None else 0.0),
        "idle_ratio": float(latest_metric.idle_ratio if latest_metric and latest_metric.idle_ratio is not None else 0.0),
        "coasting_ratio": float(latest_metric.coasting_ratio if latest_metric and latest_metric.coasting_ratio is not None else 0.0),
        "optimal_rpm_ratio": float(latest_metric.optimal_rpm_ratio if latest_metric and latest_metric.optimal_rpm_ratio is not None else 0.0),
        "brakes_per_100km": float(latest_metric.brakes_per_100km if latest_metric and latest_metric.brakes_per_100km is not None else 0.0),
        "high_speed_brakes_per_100km": float(latest_metric.high_speed_brakes_per_100km if latest_metric and latest_metric.high_speed_brakes_per_100km is not None else 0.0),
        "cruise_control_ratio": float(latest_metric.cruise_control_ratio if latest_metric and latest_metric.cruise_control_ratio is not None else 0.0),
        "overspeed_ratio": float(latest_metric.overspeed_ratio if latest_metric and latest_metric.overspeed_ratio is not None else 0.0),
        "analytics_readiness_percent": round((readiness_active / readiness_total) * 100, 1),
        "last_sync_at": last_sync_at.isoformat() if last_sync_at else None,
    }


@router.get("", response_model=list[VehicleRead])
def list_vehicles(db: Annotated[Session, Depends(get_db)]) -> list[dict[str, Any]]:
    return [_vehicle_row(vehicle) for vehicle in _load_vehicles_with_analytics(db)]


@router.get("/{vehicle_id}", response_model=VehicleRead)
def get_vehicle(vehicle_id: str, db: Annotated[Session, Depends(get_db)]) -> dict[str, Any]:
    vehicle = _load_vehicle_with_analytics(db, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Машина не найдена")
    return _vehicle_row(vehicle)


@router.get("/{vehicle_id}/sensors", response_model=list[VehicleSensorRead])
def vehicle_sensors(vehicle_id: str, db: Annotated[Session, Depends(get_db)]) -> list[VehicleSensor]:
    return list(db.scalars(select(VehicleSensor).where(VehicleSensor.vehicle_id == vehicle_id).order_by(VehicleSensor.name)).all())


@router.get("/{vehicle_id}/metrics", response_model=list[VehicleMetricRead])
def vehicle_metrics(vehicle_id: str, db: Annotated[Session, Depends(get_db)], limit: int = 100) -> list[VehicleMetricWindow]:
    return list(db.scalars(select(VehicleMetricWindow).where(VehicleMetricWindow.vehicle_id == vehicle_id).order_by(VehicleMetricWindow.period_start.desc()).limit(min(limit, 500))).all())


@router.get("/{vehicle_id}/ratings", response_model=list[RatingRead])
def vehicle_ratings(vehicle_id: str, db: Annotated[Session, Depends(get_db)], limit: int = 100) -> list[VehicleRatingWindow]:
    return list(db.scalars(select(VehicleRatingWindow).where(VehicleRatingWindow.vehicle_id == vehicle_id).order_by(VehicleRatingWindow.period_start.desc()).limit(min(limit, 500))).all())
