from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import deps
from app.api.vehicles import _load_vehicles_with_analytics
from app.config.analytics_sensors import TOTAL_ANALYTICS_SENSORS
from app.db.models import MLResult, Vehicle
from app.db.session import get_db


router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(deps.get_fleet_access_user)])


SUMMARY_SCORE_FIELDS = {
    "fleet_rating": "rating",
    "fuel_per_100km": "fuel_score",
    "idle_ratio": "idle_score",
    "coasting_ratio": "coasting_score",
    "optimal_rpm_ratio": "optimal_rpm_score",
    "brakes_per_100km": "brakes_score",
    "overspeed_ratio": "overspeed_score",
}


def _window(period: str) -> tuple[datetime, datetime, datetime, datetime]:
    now = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    days = {"day": 1, "week": 7, "month": 30, "quarter": 90}.get(period, 7)
    current_start = now - timedelta(days=days)
    previous_start = current_start - timedelta(days=days)
    return current_start, now, previous_start, current_start


def _naive(value: datetime) -> datetime:
    return value.replace(tzinfo=None) if value.tzinfo is not None else value


def _average(values: list[float | None], precision: int = 2) -> float:
    available = [value for value in values if value is not None]
    return round(sum(available) / len(available), precision) if available else 0.0


def _score_summary(rows: list[dict[str, Any]]) -> dict[str, float]:
    scores = {summary_field: _average([row[score_field] for row in rows]) for summary_field, score_field in SUMMARY_SCORE_FIELDS.items()}
    scores["analytics_readiness_percent"] = round(_average([row["analytics_readiness_percent"] for row in rows], 1) / 10, 2) if rows else 0.0
    return scores


def _score_changes(current_scores: dict[str, float], previous_scores: dict[str, float]) -> dict[str, float]:
    return {field: round(current_scores[field] - previous_scores.get(field, 0.0), 2) for field in current_scores}


def _aggregate_vehicle_rows(vehicles: list[Vehicle], start: datetime, end: datetime) -> list[dict[str, Any]]:
    start_naive = _naive(start)
    end_naive = _naive(end)
    rows: list[dict[str, Any]] = []
    for vehicle in vehicles:
        metrics = [m for m in vehicle.metric_windows if _naive(m.period_start) >= start_naive and _naive(m.period_end) <= end_naive]
        ratings = [r for r in vehicle.rating_windows if _naive(r.period_start) >= start_naive and _naive(r.period_end) <= end_naive]
        latest_sync = max((reading.timestamp for reading in vehicle.readings), default=None)
        readiness_required = TOTAL_ANALYTICS_SENSORS or 1
        readiness_active = len({link.analytics_key for link in vehicle.analytics_links if link.is_active})
        rows.append(
            {
                "vehicle_id": vehicle.id,
                "plate_number": vehicle.plate_number or "—",
                "name": vehicle.name,
                "vehicle_type": vehicle.vehicle_type or "UNKNOWN",
                "imei": vehicle.imei or "—",
                "rating": round(sum(r.final_rating for r in ratings) / len(ratings), 2) if ratings else 0.0,
                "fuel_score": _average([r.fuel_score for r in ratings]),
                "idle_score": _average([r.idle_score for r in ratings]),
                "coasting_score": _average([r.coasting_score for r in ratings]),
                "optimal_rpm_score": _average([r.optimal_rpm_score for r in ratings]),
                "brakes_score": _average([r.brakes_score for r in ratings]),
                "overspeed_score": _average([r.overspeed_score for r in ratings]),
                "fuel_per_100km": round(sum(m.fuel_per_100km or 0 for m in metrics) / len(metrics), 2) if metrics else 0.0,
                "idle_ratio": round(sum(m.idle_ratio or 0 for m in metrics) / len(metrics), 4) if metrics else 0.0,
                "coasting_ratio": round(sum(m.coasting_ratio or 0 for m in metrics) / len(metrics), 4) if metrics else 0.0,
                "optimal_rpm_ratio": round(sum(m.optimal_rpm_ratio or 0 for m in metrics) / len(metrics), 4) if metrics else 0.0,
                "brakes_per_100km": round(sum(m.brakes_per_100km or 0 for m in metrics) / len(metrics), 2) if metrics else 0.0,
                "high_speed_brakes_per_100km": round(sum(m.high_speed_brakes_per_100km or 0 for m in metrics) / len(metrics), 2) if metrics else 0.0,
                "cruise_control_ratio": round(sum(m.cruise_control_ratio or 0 for m in metrics) / len(metrics), 4) if metrics else 0.0,
                "overspeed_ratio": round(sum(m.overspeed_ratio or 0 for m in metrics) / len(metrics), 4) if metrics else 0.0,
                "analytics_readiness_percent": round((readiness_active / readiness_required) * 100, 1),
                "distance_km_total": round(sum(m.distance_km for m in metrics), 2),
                "last_sync_at": latest_sync.isoformat() if latest_sync else None,
            }
        )
    return rows


@router.get("/summary")
def summary(db: Annotated[Session, Depends(get_db)], period: str = "week") -> dict[str, Any]:
    current_start, current_end, previous_start, previous_end = _window(period)
    vehicles = _load_vehicles_with_analytics(db)
    rows = _aggregate_vehicle_rows(vehicles, current_start, current_end)
    previous_rows = _aggregate_vehicle_rows(vehicles, previous_start, previous_end)
    anomaly_count = db.query(MLResult).filter(MLResult.result_type == "anomaly").count()
    fleet_rating = round(sum(row["rating"] for row in rows) / len(rows), 2) if rows else 0.0
    previous_rating = round(sum(row["rating"] for row in previous_rows) / len(previous_rows), 2) if previous_rows else 0.0
    metric_scores = _score_summary(rows)
    previous_metric_scores = _score_summary(previous_rows)
    return {
        "period": period,
        "vehicles_count": len(rows),
        "vehicle_count": len(rows),
        "fleet_rating": fleet_rating,
        "average_rating": fleet_rating,
        "rating_change": round(fleet_rating - previous_rating, 2),
        "metric_scores": metric_scores,
        "metric_score_changes": _score_changes(metric_scores, previous_metric_scores),
        "total_distance_km": round(sum(row["distance_km_total"] for row in rows), 2),
        "fuel_per_100km": round(sum(row["fuel_per_100km"] for row in rows) / len(rows), 2) if rows else 0.0,
        "idle_ratio": round(sum(row["idle_ratio"] for row in rows) / len(rows), 4) if rows else 0.0,
        "coasting_ratio": round(sum(row["coasting_ratio"] for row in rows) / len(rows), 4) if rows else 0.0,
        "optimal_rpm_ratio": round(sum(row["optimal_rpm_ratio"] for row in rows) / len(rows), 4) if rows else 0.0,
        "brakes_per_100km": round(sum(row["brakes_per_100km"] for row in rows) / len(rows), 2) if rows else 0.0,
        "high_speed_brakes_per_100km": round(sum(row["high_speed_brakes_per_100km"] for row in rows) / len(rows), 2) if rows else 0.0,
        "cruise_control_ratio": round(sum(row["cruise_control_ratio"] for row in rows) / len(rows), 4) if rows else 0.0,
        "overspeed_ratio": round(sum(row["overspeed_ratio"] for row in rows) / len(rows), 4) if rows else 0.0,
        "analytics_readiness_percent": round(sum(row["analytics_readiness_percent"] for row in rows) / len(rows), 1) if rows else 0.0,
        "anomaly_vehicles_count": anomaly_count,
    }


@router.get("/timeseries")
def timeseries(db: Annotated[Session, Depends(get_db)], period: str = "week") -> list[dict[str, Any]]:
    current_start, current_end, _, _ = _window(period)
    vehicles = _load_vehicles_with_analytics(db)
    metric_rows = [m for vehicle in vehicles for m in vehicle.metric_windows if m.period_start >= current_start and m.period_end <= current_end]
    grouped: dict[str, dict[str, Any]] = {}
    for row in metric_rows:
        key = row.period_start.date().isoformat()
        item = grouped.setdefault(key, {"date": key, "count": 0, "fuel_per_100km": 0.0, "idle_ratio": 0.0, "coasting_ratio": 0.0, "optimal_rpm_ratio": 0.0, "brakes_per_100km": 0.0, "high_speed_brakes_per_100km": 0.0, "cruise_control_ratio": 0.0, "overspeed_ratio": 0.0, "analytics_readiness_percent": 100.0, "rating": 0.0})
        item["count"] += 1
        for field in ("fuel_per_100km", "idle_ratio", "coasting_ratio", "optimal_rpm_ratio", "brakes_per_100km", "high_speed_brakes_per_100km", "cruise_control_ratio", "overspeed_ratio"):
            item[field] += float(getattr(row, field) or 0.0)
    rating_rows = [r for vehicle in vehicles for r in vehicle.rating_windows if r.period_start >= current_start and r.period_end <= current_end]
    for row in rating_rows:
        key = row.period_start.date().isoformat()
        item = grouped.setdefault(key, {"date": key, "count": 0, "fuel_per_100km": 0.0, "idle_ratio": 0.0, "coasting_ratio": 0.0, "optimal_rpm_ratio": 0.0, "brakes_per_100km": 0.0, "high_speed_brakes_per_100km": 0.0, "cruise_control_ratio": 0.0, "overspeed_ratio": 0.0, "analytics_readiness_percent": 100.0, "rating": 0.0})
        item["rating"] += row.final_rating
    result = []
    for key in sorted(grouped):
        item = grouped[key]
        count = max(item.pop("count"), 1)
        result.append({name: round(value / count, 4) if isinstance(value, float) and name != "date" else value for name, value in item.items()})
    return result


@router.get("/comparison")
def comparison(db: Annotated[Session, Depends(get_db)], period: str = "week") -> list[dict[str, Any]]:
    current_start, current_end, _, _ = _window(period)
    vehicles = _load_vehicles_with_analytics(db)
    return sorted(_aggregate_vehicle_rows(vehicles, current_start, current_end), key=lambda row: row["rating"], reverse=True)


@router.get("/problem-vehicles")
def problem_vehicles(db: Annotated[Session, Depends(get_db)], period: str = "week") -> dict[str, Any]:
    current_start, current_end, _, _ = _window(period)
    vehicles = _load_vehicles_with_analytics(db)
    rows = sorted(_aggregate_vehicle_rows(vehicles, current_start, current_end), key=lambda row: row["rating"])
    anomaly_ids = {result.vehicle_id for result in db.scalars(select(MLResult).where(MLResult.result_type == "anomaly")).all() if result.vehicle_id}

    def enrich(row: dict[str, Any]) -> dict[str, Any]:
        return row | {
            "anomaly_flag": row["vehicle_id"] in anomaly_ids,
            "anomaly_reasons": ["Обнаружена ML-аномалия"] if row["vehicle_id"] in anomaly_ids else [],
        }

    return {"worst": [enrich(row) for row in rows[:5]], "best": [enrich(row) for row in rows[-5:]][::-1]}
