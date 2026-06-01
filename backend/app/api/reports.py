from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
import csv
import io

from app.api import deps
from app.api.vehicles import _load_vehicle_with_analytics, _load_vehicles_with_analytics
from app.config.analytics_sensors import TOTAL_ANALYTICS_SENSORS
from app.db.models import User, Vehicle
from app.db.session import get_db


router = APIRouter(prefix="/reports", tags=["reports"], dependencies=[Depends(deps.get_fleet_access_user)])


def _period_dates(period: str | None, date_from: date | None, date_to: date | None) -> tuple[datetime, datetime, str]:
    if date_from and date_to:
        return datetime.combine(date_from, time.min, tzinfo=UTC), datetime.combine(date_to, time.max, tzinfo=UTC), period or "custom"
    now = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    days = {"week": 7, "month": 30, "quarter": 90}.get(period or "week", 7)
    return now - timedelta(days=days), now, period or "week"


def _naive(value: datetime) -> datetime:
    return value.replace(tzinfo=None) if value.tzinfo is not None else value


def _vehicle_rows(vehicles: list[Vehicle], start: datetime, end: datetime) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start_naive = _naive(start)
    end_naive = _naive(end)
    for vehicle in vehicles:
        metrics = [metric for metric in vehicle.metric_windows if _naive(metric.period_start) >= start_naive and _naive(metric.period_end) <= end_naive]
        ratings = [rating for rating in vehicle.rating_windows if _naive(rating.period_start) >= start_naive and _naive(rating.period_end) <= end_naive]
        readiness_total = TOTAL_ANALYTICS_SENSORS or 1
        readiness_active = len({link.analytics_key for link in vehicle.analytics_links if link.is_active})
        last_sync_at = max((reading.timestamp for reading in vehicle.readings), default=None)
        rows.append(
            {
                "vehicle": vehicle,
                "id": vehicle.id,
                "vehicle_id": vehicle.id,
                "plate_number": vehicle.plate_number or "—",
                "name": vehicle.name,
                "vehicle_type": vehicle.vehicle_type or "UNKNOWN",
                "imei": vehicle.imei or "—",
                "rating": round(sum(rating.final_rating for rating in ratings) / len(ratings), 2) if ratings else 0.0,
                "fuel_per_100km": round(sum(metric.fuel_per_100km or 0.0 for metric in metrics) / len(metrics), 2) if metrics else 0.0,
                "idle_ratio": round(sum(metric.idle_ratio or 0.0 for metric in metrics) / len(metrics), 4) if metrics else 0.0,
                "coasting_ratio": round(sum(metric.coasting_ratio or 0.0 for metric in metrics) / len(metrics), 4) if metrics else 0.0,
                "optimal_rpm_ratio": round(sum(metric.optimal_rpm_ratio or 0.0 for metric in metrics) / len(metrics), 4) if metrics else 0.0,
                "brakes_per_100km": round(sum(metric.brakes_per_100km or 0.0 for metric in metrics) / len(metrics), 2) if metrics else 0.0,
                "high_speed_brakes_per_100km": round(sum(metric.high_speed_brakes_per_100km or 0.0 for metric in metrics) / len(metrics), 2) if metrics else 0.0,
                "cruise_control_ratio": round(sum(metric.cruise_control_ratio or 0.0 for metric in metrics) / len(metrics), 4) if metrics else 0.0,
                "overspeed_ratio": round(sum(metric.overspeed_ratio or 0.0 for metric in metrics) / len(metrics), 4) if metrics else 0.0,
                "analytics_readiness_percent": round((readiness_active / readiness_total) * 100, 1),
                "last_sync_at": last_sync_at.isoformat() if last_sync_at else None,
            }
        )
    return rows


def _conclusions(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    if not rows:
        return [{"title": "Нет данных", "text": "Недостаточно данных для формирования отчёта.", "severity": "warning"}]
    best = max(rows, key=lambda row: row["rating"])
    worst = min(rows, key=lambda row: row["rating"])
    avg_rating = sum(row["rating"] for row in rows) / len(rows)
    return [
        {"title": "Рейтинг автопарка", "text": f"Средний рейтинг за выбранный период составляет {avg_rating:.2f}.", "severity": "neutral"},
        {"title": "Лучшая машина", "text": f"{best['plate_number']} показывает лучший результат с рейтингом {best['rating']:.2f}.", "severity": "positive"},
        {"title": "Требует внимания", "text": f"{worst['plate_number']} показывает самый слабый результат с рейтингом {worst['rating']:.2f}.", "severity": "critical"},
    ]


@router.get("/fleet")
def fleet_report(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(deps.get_fleet_access_user)],
    period: str = "week",
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict[str, Any]:
    start, end, normalized_period = _period_dates(period, date_from, date_to)
    vehicles = _load_vehicles_with_analytics(db, current_user)
    rows = _vehicle_rows(vehicles, start, end)
    comparison = [{key: value for key, value in row.items() if key != "vehicle"} for row in rows]
    fleet_rating = round(sum(row["rating"] for row in comparison) / len(comparison), 2) if comparison else 0.0
    return {
        "period": normalized_period,
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": {
            "period": normalized_period,
            "vehicles_count": len(comparison),
            "fleet_rating": fleet_rating,
            "fuel_per_100km": round(sum(row["fuel_per_100km"] for row in comparison) / len(comparison), 2) if comparison else 0.0,
            "idle_ratio": round(sum(row["idle_ratio"] for row in comparison) / len(comparison), 4) if comparison else 0.0,
            "coasting_ratio": round(sum(row["coasting_ratio"] for row in comparison) / len(comparison), 4) if comparison else 0.0,
            "optimal_rpm_ratio": round(sum(row["optimal_rpm_ratio"] for row in comparison) / len(comparison), 4) if comparison else 0.0,
            "brakes_per_100km": round(sum(row["brakes_per_100km"] for row in comparison) / len(comparison), 2) if comparison else 0.0,
            "high_speed_brakes_per_100km": round(sum(row["high_speed_brakes_per_100km"] for row in comparison) / len(comparison), 2) if comparison else 0.0,
            "cruise_control_ratio": round(sum(row["cruise_control_ratio"] for row in comparison) / len(comparison), 4) if comparison else 0.0,
            "overspeed_ratio": round(sum(row["overspeed_ratio"] for row in comparison) / len(comparison), 4) if comparison else 0.0,
            "analytics_readiness_percent": round(sum(row["analytics_readiness_percent"] for row in comparison) / len(comparison), 2) if comparison else 0.0,
            "anomaly_vehicles_count": 0,
        },
        "comparison": comparison,
        "conclusions": _conclusions(comparison),
    }


@router.get("/vehicle/{vehicle_id}")
def vehicle_report(
    vehicle_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(deps.get_fleet_access_user)],
    period: str = "week",
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict[str, Any]:
    start, end, normalized_period = _period_dates(period, date_from, date_to)
    vehicle = _load_vehicle_with_analytics(db, current_user, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Машина не найдена")
    scoped_rows = _vehicle_rows([vehicle], start, end)
    summary = next((row for row in scoped_rows if row["id"] == vehicle.id), None)
    if summary is None:
        summary = {"id": vehicle.id, "vehicle_id": vehicle.id, "plate_number": vehicle.plate_number or "—", "name": vehicle.name, "vehicle_type": vehicle.vehicle_type or "UNKNOWN", "imei": vehicle.imei or "—", "rating": 0.0, "fuel_per_100km": 0.0, "idle_ratio": 0.0, "coasting_ratio": 0.0, "optimal_rpm_ratio": 0.0, "brakes_per_100km": 0.0, "high_speed_brakes_per_100km": 0.0, "cruise_control_ratio": 0.0, "overspeed_ratio": 0.0, "analytics_readiness_percent": 0.0, "last_sync_at": None}
    rating_by_window = {(rating.period_start, rating.period_end): rating.final_rating for rating in vehicle.rating_windows}
    timeseries = [
        {
            "date": metric.period_start.date().isoformat(),
            "rating": rating_by_window.get((metric.period_start, metric.period_end), 0.0),
            "fuel_per_100km": metric.fuel_per_100km or 0.0,
            "idle_ratio": metric.idle_ratio or 0.0,
            "coasting_ratio": metric.coasting_ratio or 0.0,
            "optimal_rpm_ratio": metric.optimal_rpm_ratio or 0.0,
            "brakes_per_100km": metric.brakes_per_100km or 0.0,
            "high_speed_brakes_per_100km": metric.high_speed_brakes_per_100km or 0.0,
            "cruise_control_ratio": metric.cruise_control_ratio or 0.0,
            "overspeed_ratio": metric.overspeed_ratio or 0.0,
            "analytics_readiness_percent": summary["analytics_readiness_percent"],
        }
        for metric in sorted(vehicle.metric_windows, key=lambda row: row.period_start)
        if _naive(metric.period_start) >= _naive(start) and _naive(metric.period_end) <= _naive(end)
    ]
    return {
        "period": normalized_period,
        "generated_at": datetime.now(UTC).isoformat(),
        "vehicle": {"id": vehicle.id, "plate_number": summary["plate_number"], "name": summary["name"]},
        "summary": {"vehicle_id": vehicle.id, **summary},
        "timeseries": timeseries,
        "conclusions": _conclusions([{**summary, "vehicle_id": vehicle.id}]),
    }


@router.get("/export/csv")
def export_csv(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(deps.get_fleet_access_user)],
    period: str = "week",
    object_type: str = Query(default="fleet"),
    vehicle_id: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> Response:
    start, end, _ = _period_dates(period, date_from, date_to)
    if object_type == "vehicle" and vehicle_id:
        vehicle = _load_vehicle_with_analytics(db, current_user, vehicle_id)
        rows = _vehicle_rows([vehicle], start, end) if vehicle else []
    else:
        rows = _vehicle_rows(_load_vehicles_with_analytics(db, current_user), start, end)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["plate_number", "name", "vehicle_type", "rating", "fuel_per_100km", "idle_ratio", "coasting_ratio", "optimal_rpm_ratio", "brakes_per_100km", "high_speed_brakes_per_100km", "cruise_control_ratio", "overspeed_ratio", "analytics_readiness_percent", "last_sync_at"])
    for row in rows:
        writer.writerow([row["plate_number"], row["name"], row["vehicle_type"], row["rating"], row["fuel_per_100km"], row["idle_ratio"], row["coasting_ratio"], row["optimal_rpm_ratio"], row["brakes_per_100km"], row["high_speed_brakes_per_100km"], row["cruise_control_ratio"], row["overspeed_ratio"], row["analytics_readiness_percent"], row["last_sync_at"] or ""])
    return Response(buffer.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=fleet_report.csv"})
