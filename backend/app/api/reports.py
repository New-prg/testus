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
from app.db.models import MLResult, User, Vehicle
from app.db.session import get_db


router = APIRouter(prefix="/reports", tags=["reports"], dependencies=[Depends(deps.get_fleet_access_user)])


def _latest_report_anchor_end(vehicles: list[Vehicle]) -> datetime:
    metric_period_ends = [
        _naive(metric.period_end).replace(tzinfo=UTC)
        for vehicle in vehicles
        for metric in vehicle.metric_windows
        if metric.period_end is not None
    ]
    rating_period_ends = [
        _naive(rating.period_end).replace(tzinfo=UTC)
        for vehicle in vehicles
        for rating in vehicle.rating_windows
        if rating.period_end is not None
    ]
    reading_days = [
        _naive(reading.timestamp).replace(tzinfo=UTC).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        for vehicle in vehicles
        for reading in vehicle.readings
        if reading.timestamp is not None
    ]
    candidates = metric_period_ends + rating_period_ends + reading_days
    if candidates:
        return max(candidates)
    return datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)


def _period_dates(period: str | None, date_from: date | None, date_to: date | None, vehicles: list[Vehicle]) -> tuple[datetime, datetime, str]:
    if date_from and date_to:
        return datetime.combine(date_from, time.min, tzinfo=UTC), datetime.combine(date_to, time.max, tzinfo=UTC), period or "custom"
    end = _latest_report_anchor_end(vehicles)
    days = {"week": 7, "month": 30, "quarter": 90}.get(period or "week", 7)
    return end - timedelta(days=days), end, period or "week"


def _naive(value: datetime) -> datetime:
    return value.replace(tzinfo=None) if value.tzinfo is not None else value


def _public_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if not key.startswith("__") and key != "vehicle"}


def _average_or_none(values: list[float | None], precision: int) -> float | None:
    available = [value for value in values if value is not None]
    return round(sum(available) / len(available), precision) if available else None


def _ratio_average(metrics: list[Any], field: str, precision: int = 4) -> float | None:
    return _average_or_none([getattr(metric, field) for metric in metrics], precision)


def _weighted_distance_rate(metrics: list[Any], field: str, precision: int = 2) -> float | None:
    weighted_total = 0.0
    distance_total = 0.0
    for metric in metrics:
        value = getattr(metric, field)
        distance = metric.distance_km or 0.0
        if value is None or distance <= 0:
            continue
        weighted_total += value * distance
        distance_total += distance
    return round(weighted_total / distance_total, precision) if distance_total > 0 else None


def _fuel_rate(metrics: list[Any]) -> float | None:
    fuel_total = 0.0
    distance_total = 0.0
    for metric in metrics:
        fuel = metric.fuel_consumed_liters
        distance = metric.distance_km or 0.0
        if fuel is None or distance <= 0:
            continue
        fuel_total += fuel
        distance_total += distance
    return round((fuel_total / distance_total) * 100, 2) if distance_total > 0 else None


def _idle_rate(metrics: list[Any]) -> float | None:
    idle_total = sum(metric.idle_seconds or 0.0 for metric in metrics if metric.idle_ratio is not None)
    engine_total = sum(metric.engine_work_seconds or 0.0 for metric in metrics if metric.idle_ratio is not None)
    return round(idle_total / engine_total, 4) if engine_total > 0 else None


def _metric_has_data(metric: Any) -> bool:
    reading_counts = metric.raw_json.get("reading_counts") if isinstance(metric.raw_json, dict) else None
    if isinstance(reading_counts, dict) and any(int(count) > 0 for count in reading_counts.values()):
        return True
    return any(
        value is not None and value != 0
        for value in (
            metric.distance_km,
            metric.fuel_consumed_liters,
            metric.fuel_per_100km,
            metric.coasting_ratio,
            metric.optimal_rpm_ratio,
            metric.idle_ratio,
            metric.brakes_per_100km,
            metric.high_speed_brakes_per_100km,
            metric.cruise_control_ratio,
            metric.overspeed_ratio,
            metric.engine_work_seconds,
            metric.moving_seconds,
            metric.idle_seconds,
        )
    )


def _rating_has_data(rating: Any) -> bool:
    return any(
        value is not None
        for value in (
            rating.fuel_score,
            rating.coasting_score,
            rating.optimal_rpm_score,
            rating.idle_score,
            rating.brakes_score,
            rating.high_speed_brakes_score,
            rating.cruise_control_score,
            rating.overspeed_score,
        )
    )


def _anomaly_vehicle_ids(db: Session, user_id: str, start: datetime, end: datetime) -> set[str]:
    rows = db.execute(
        select(MLResult.vehicle_id)
        .join(Vehicle, Vehicle.id == MLResult.vehicle_id)
        .where(MLResult.result_type == "anomaly", Vehicle.user_id == user_id)
        .where(MLResult.vehicle_id.is_not(None))
        .where(MLResult.period_start >= start)
        .where(MLResult.period_end <= end)
    ).all()
    return {vehicle_id for (vehicle_id,) in rows if vehicle_id}


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
        metrics_with_data = [metric for metric in metrics if _metric_has_data(metric)]
        ratings_with_data = [rating for rating in ratings if _rating_has_data(rating)]
        fuel_per_100km = _fuel_rate(metrics_with_data)
        idle_ratio = _idle_rate(metrics_with_data)
        coasting_ratio = _ratio_average(metrics_with_data, "coasting_ratio")
        optimal_rpm_ratio = _ratio_average(metrics_with_data, "optimal_rpm_ratio")
        brakes_per_100km = _weighted_distance_rate(metrics_with_data, "brakes_per_100km")
        high_speed_brakes_per_100km = _weighted_distance_rate(metrics_with_data, "high_speed_brakes_per_100km")
        cruise_control_ratio = _ratio_average(metrics_with_data, "cruise_control_ratio")
        overspeed_ratio = _ratio_average(metrics_with_data, "overspeed_ratio")
        rows.append(
            {
                "vehicle": vehicle,
                "id": vehicle.id,
                "vehicle_id": vehicle.id,
                "plate_number": vehicle.plate_number or "—",
                "name": vehicle.name,
                "vehicle_type": vehicle.vehicle_type or "UNKNOWN",
                "imei": vehicle.imei or "—",
                "rating": round(sum(rating.final_rating for rating in ratings_with_data) / len(ratings_with_data), 2) if ratings_with_data else 0.0,
                "fuel_per_100km": fuel_per_100km or 0.0,
                "idle_ratio": idle_ratio or 0.0,
                "coasting_ratio": coasting_ratio or 0.0,
                "optimal_rpm_ratio": optimal_rpm_ratio or 0.0,
                "brakes_per_100km": brakes_per_100km or 0.0,
                "high_speed_brakes_per_100km": high_speed_brakes_per_100km or 0.0,
                "cruise_control_ratio": cruise_control_ratio or 0.0,
                "overspeed_ratio": overspeed_ratio or 0.0,
                "analytics_readiness_percent": round((readiness_active / readiness_total) * 100, 1),
                "last_sync_at": last_sync_at.isoformat() if last_sync_at else None,
                "__has_metric_data": bool(metrics_with_data),
                "__has_rating_data": bool(ratings_with_data),
                "__fuel_total": round(sum((metric.fuel_consumed_liters or 0.0) for metric in metrics_with_data if metric.fuel_consumed_liters is not None), 3),
                "__fuel_distance_total": round(sum((metric.distance_km or 0.0) for metric in metrics_with_data if metric.fuel_consumed_liters is not None and (metric.distance_km or 0.0) > 0), 3),
                "__idle_total": round(sum((metric.idle_seconds or 0.0) for metric in metrics_with_data if metric.idle_ratio is not None), 3),
                "__engine_total": round(sum((metric.engine_work_seconds or 0.0) for metric in metrics_with_data if metric.idle_ratio is not None), 3),
                "__brakes_weighted_total": round(sum((metric.brakes_per_100km or 0.0) * (metric.distance_km or 0.0) for metric in metrics_with_data if metric.brakes_per_100km is not None and (metric.distance_km or 0.0) > 0), 3),
                "__high_speed_brakes_weighted_total": round(sum((metric.high_speed_brakes_per_100km or 0.0) * (metric.distance_km or 0.0) for metric in metrics_with_data if metric.high_speed_brakes_per_100km is not None and (metric.distance_km or 0.0) > 0), 3),
                "__brakes_distance_total": round(sum((metric.distance_km or 0.0) for metric in metrics_with_data if ((metric.brakes_per_100km is not None or metric.high_speed_brakes_per_100km is not None) and (metric.distance_km or 0.0) > 0)), 3),
            }
        )
    return rows


def _conclusions(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    if not rows or not any(row.get("__has_metric_data") or row.get("__has_rating_data") for row in rows):
        return [{"title": "Нет данных", "text": "Недостаточно данных для формирования отчёта.", "severity": "warning"}]
    rated_rows = [row for row in rows if row.get("__has_rating_data")]
    best = max(rated_rows, key=lambda row: row["rating"]) if rated_rows else rows[0]
    worst = min(rated_rows, key=lambda row: row["rating"]) if rated_rows else rows[0]
    avg_rating = sum(row["rating"] for row in rated_rows) / len(rated_rows) if rated_rows else 0.0
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
    vehicles = _load_vehicles_with_analytics(db, current_user)
    start, end, normalized_period = _period_dates(period, date_from, date_to, vehicles)
    rows = _vehicle_rows(vehicles, start, end)
    comparison = [_public_row(row) for row in rows]
    fleet_rating = round(sum(row["rating"] for row in rows if row["__has_rating_data"]) / len([row for row in rows if row["__has_rating_data"]]), 2) if any(row["__has_rating_data"] for row in rows) else 0.0
    fuel_total = sum(row["__fuel_total"] for row in rows)
    fuel_distance_total = sum(row["__fuel_distance_total"] for row in rows)
    idle_total = sum(row["__idle_total"] for row in rows)
    engine_total = sum(row["__engine_total"] for row in rows)
    brakes_weighted_total = sum(row["__brakes_weighted_total"] for row in rows)
    high_speed_brakes_weighted_total = sum(row["__high_speed_brakes_weighted_total"] for row in rows)
    brakes_distance_total = sum(row["__brakes_distance_total"] for row in rows)
    metric_rows = [row for row in rows if row["__has_metric_data"]]
    anomaly_count = len(_anomaly_vehicle_ids(db, current_user.id, start, end))
    def summary_average(field: str, precision: int) -> float:
        available = [row[field] for row in metric_rows]
        return round(sum(available) / len(available), precision) if available else 0.0

    return {
        "period": normalized_period,
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": {
            "period": normalized_period,
            "vehicles_count": len(comparison),
            "fleet_rating": fleet_rating,
            "fuel_per_100km": round((fuel_total / fuel_distance_total) * 100, 2) if fuel_distance_total > 0 else 0.0,
            "idle_ratio": round(idle_total / engine_total, 4) if engine_total > 0 else 0.0,
            "coasting_ratio": summary_average("coasting_ratio", 4),
            "optimal_rpm_ratio": summary_average("optimal_rpm_ratio", 4),
            "brakes_per_100km": round(brakes_weighted_total / brakes_distance_total, 2) if brakes_distance_total > 0 else 0.0,
            "high_speed_brakes_per_100km": round(high_speed_brakes_weighted_total / brakes_distance_total, 2) if brakes_distance_total > 0 else 0.0,
            "cruise_control_ratio": summary_average("cruise_control_ratio", 4),
            "overspeed_ratio": summary_average("overspeed_ratio", 4),
            "analytics_readiness_percent": round(sum(row["analytics_readiness_percent"] for row in comparison) / len(comparison), 2) if comparison else 0.0,
            "anomaly_vehicles_count": anomaly_count,
        },
        "comparison": comparison,
        "conclusions": _conclusions(rows),
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
    vehicle = _load_vehicle_with_analytics(db, current_user, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Машина не найдена")
    start, end, normalized_period = _period_dates(period, date_from, date_to, [vehicle])
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
        "summary": {"vehicle_id": vehicle.id, **_public_row(summary)},
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
    if object_type == "vehicle" and vehicle_id:
        vehicle = _load_vehicle_with_analytics(db, current_user, vehicle_id)
        start, end, _ = _period_dates(period, date_from, date_to, [vehicle] if vehicle else [])
        rows = _vehicle_rows([vehicle], start, end) if vehicle else []
    else:
        vehicles = _load_vehicles_with_analytics(db, current_user)
        start, end, _ = _period_dates(period, date_from, date_to, vehicles)
        rows = _vehicle_rows(vehicles, start, end)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["plate_number", "name", "vehicle_type", "rating", "fuel_per_100km", "idle_ratio", "coasting_ratio", "optimal_rpm_ratio", "brakes_per_100km", "high_speed_brakes_per_100km", "cruise_control_ratio", "overspeed_ratio", "analytics_readiness_percent", "last_sync_at"])
    for row in rows:
        writer.writerow([row["plate_number"], row["name"], row["vehicle_type"], row["rating"], row["fuel_per_100km"], row["idle_ratio"], row["coasting_ratio"], row["optimal_rpm_ratio"], row["brakes_per_100km"], row["high_speed_brakes_per_100km"], row["cruise_control_ratio"], row["overspeed_ratio"], row["analytics_readiness_percent"], row["last_sync_at"] or ""])
    return Response(buffer.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=fleet_report.csv"})
