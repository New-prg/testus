from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import deps
from app.api.vehicles import _load_vehicles_with_analytics
from app.config.analytics_sensors import TOTAL_ANALYTICS_SENSORS
from app.db.models import MLResult, User, Vehicle
from app.db.session import get_db


router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(deps.get_fleet_access_user)])


SUMMARY_SCORE_FIELDS = {
    "fleet_rating": "rating",
    "fuel_per_100km": "fuel_score",
    "idle_ratio": "idle_score",
    "coasting_ratio": "coasting_score",
    "optimal_rpm_ratio": "optimal_rpm_score",
    "brakes_per_100km": "brakes_score",
    "high_speed_brakes_per_100km": "high_speed_brakes_score",
    "cruise_control_ratio": "cruise_control_score",
    "overspeed_ratio": "overspeed_score",
}


def _latest_dashboard_anchor_end(vehicles: list[Vehicle]) -> datetime:
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


def _window(period: str, vehicles: list[Vehicle]) -> tuple[datetime, datetime, datetime, datetime]:
    current_end = _latest_dashboard_anchor_end(vehicles)
    days = {"day": 1, "week": 7, "month": 30, "quarter": 90}.get(period, 7)
    current_start = current_end - timedelta(days=days)
    previous_start = current_start - timedelta(days=days)
    return current_start, current_end, previous_start, current_start


def _naive(value: datetime) -> datetime:
    return value.replace(tzinfo=None) if value.tzinfo is not None else value


def _average(values: list[float | None], precision: int = 2) -> float:
    available = [value for value in values if value is not None]
    return round(sum(available) / len(available), precision) if available else 0.0


def _average_or_none(values: list[float | None], precision: int = 2) -> float | None:
    available = [value for value in values if value is not None]
    return round(sum(available) / len(available), precision) if available else None


def _ratio_average(metrics: list[Any], field: str, precision: int = 4) -> float | None:
    return _average_or_none([getattr(metric, field) for metric in metrics], precision)


def _sum_present(values: list[float | None]) -> tuple[float, int]:
    available = [value for value in values if value is not None]
    return float(sum(available)), len(available)


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


def _score_summary(rows: list[dict[str, Any]]) -> dict[str, float]:
    scores = {summary_field: _average([row[score_field] for row in rows]) for summary_field, score_field in SUMMARY_SCORE_FIELDS.items()}
    scores["analytics_readiness_percent"] = round(_average([row["analytics_readiness_percent"] for row in rows], 1), 2) if rows else 0.0
    return scores


def _score_changes(current_scores: dict[str, float], previous_scores: dict[str, float]) -> dict[str, float]:
    return {field: round(current_scores[field] - previous_scores.get(field, 0.0), 2) for field in current_scores}


def _public_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if not key.startswith("__") and key != "vehicle"}


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
                "vehicle_id": vehicle.id,
                "plate_number": vehicle.plate_number or "—",
                "name": vehicle.name,
                "vehicle_type": vehicle.vehicle_type or "UNKNOWN",
                "imei": vehicle.imei or "—",
                "rating": round(sum(r.final_rating for r in ratings_with_data) / len(ratings_with_data), 2) if ratings_with_data else 0.0,
                "fuel_score": _average_or_none([r.fuel_score for r in ratings_with_data]),
                "idle_score": _average_or_none([r.idle_score for r in ratings_with_data]),
                "coasting_score": _average_or_none([r.coasting_score for r in ratings_with_data]),
                "optimal_rpm_score": _average_or_none([r.optimal_rpm_score for r in ratings_with_data]),
                "brakes_score": _average_or_none([r.brakes_score for r in ratings_with_data]),
                "high_speed_brakes_score": _average_or_none([r.high_speed_brakes_score for r in ratings_with_data]),
                "cruise_control_score": _average_or_none([r.cruise_control_score for r in ratings_with_data]),
                "overspeed_score": _average_or_none([r.overspeed_score for r in ratings_with_data]),
                "fuel_per_100km": fuel_per_100km or 0.0,
                "idle_ratio": idle_ratio or 0.0,
                "coasting_ratio": coasting_ratio or 0.0,
                "optimal_rpm_ratio": optimal_rpm_ratio or 0.0,
                "brakes_per_100km": brakes_per_100km or 0.0,
                "high_speed_brakes_per_100km": high_speed_brakes_per_100km or 0.0,
                "cruise_control_ratio": cruise_control_ratio or 0.0,
                "overspeed_ratio": overspeed_ratio or 0.0,
                "analytics_readiness_percent": round((readiness_active / readiness_required) * 100, 1),
                "distance_km_total": round(sum((m.distance_km or 0.0) for m in metrics_with_data), 2),
                "last_sync_at": latest_sync.isoformat() if latest_sync else None,
                "__has_metric_data": bool(metrics_with_data),
                "__has_rating_data": bool(ratings_with_data),
                "__fuel_total": round(sum((m.fuel_consumed_liters or 0.0) for m in metrics_with_data if m.fuel_consumed_liters is not None), 3),
                "__fuel_distance_total": round(sum((m.distance_km or 0.0) for m in metrics_with_data if m.fuel_consumed_liters is not None and (m.distance_km or 0.0) > 0), 3),
                "__idle_total": round(sum((m.idle_seconds or 0.0) for m in metrics_with_data if m.idle_ratio is not None), 3),
                "__engine_total": round(sum((m.engine_work_seconds or 0.0) for m in metrics_with_data if m.idle_ratio is not None), 3),
                "__brakes_weighted_total": round(sum((m.brakes_per_100km or 0.0) * (m.distance_km or 0.0) for m in metrics_with_data if m.brakes_per_100km is not None and (m.distance_km or 0.0) > 0), 3),
                "__high_speed_brakes_weighted_total": round(sum((m.high_speed_brakes_per_100km or 0.0) * (m.distance_km or 0.0) for m in metrics_with_data if m.high_speed_brakes_per_100km is not None and (m.distance_km or 0.0) > 0), 3),
                "__brakes_distance_total": round(sum((m.distance_km or 0.0) for m in metrics_with_data if ((m.brakes_per_100km is not None or m.high_speed_brakes_per_100km is not None) and (m.distance_km or 0.0) > 0)), 3),
            }
        )
    return rows


@router.get("/summary")
def summary(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(deps.get_fleet_access_user)],
    period: str = "week",
) -> dict[str, Any]:
    vehicles = _load_vehicles_with_analytics(db, current_user)
    current_start, current_end, previous_start, previous_end = _window(period, vehicles)
    rows = _aggregate_vehicle_rows(vehicles, current_start, current_end)
    previous_rows = _aggregate_vehicle_rows(vehicles, previous_start, previous_end)
    anomaly_count = len(_anomaly_vehicle_ids(db, current_user.id, current_start, current_end))
    rated_rows = [row for row in rows if row["__has_rating_data"]]
    previous_rated_rows = [row for row in previous_rows if row["__has_rating_data"]]
    fleet_rating = round(sum(row["rating"] for row in rated_rows) / len(rated_rows), 2) if rated_rows else 0.0
    previous_rating = round(sum(row["rating"] for row in previous_rated_rows) / len(previous_rated_rows), 2) if previous_rated_rows else 0.0
    metric_scores = _score_summary(rows)
    previous_metric_scores = _score_summary(previous_rows)
    fuel_total = sum(row["__fuel_total"] for row in rows)
    fuel_distance_total = sum(row["__fuel_distance_total"] for row in rows)
    idle_total = sum(row["__idle_total"] for row in rows)
    engine_total = sum(row["__engine_total"] for row in rows)
    brakes_weighted_total = sum(row["__brakes_weighted_total"] for row in rows)
    high_speed_brakes_weighted_total = sum(row["__high_speed_brakes_weighted_total"] for row in rows)
    brakes_distance_total = sum(row["__brakes_distance_total"] for row in rows)
    metric_rows = [row for row in rows if row["__has_metric_data"]]

    def summary_average(field: str, precision: int) -> float:
        available = [row[field] for row in metric_rows]
        return round(sum(available) / len(available), precision) if available else 0.0

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
        "fuel_per_100km": round((fuel_total / fuel_distance_total) * 100, 2) if fuel_distance_total > 0 else 0.0,
        "idle_ratio": round(idle_total / engine_total, 4) if engine_total > 0 else 0.0,
        "coasting_ratio": summary_average("coasting_ratio", 4),
        "optimal_rpm_ratio": summary_average("optimal_rpm_ratio", 4),
        "brakes_per_100km": round(brakes_weighted_total / brakes_distance_total, 2) if brakes_distance_total > 0 else 0.0,
        "high_speed_brakes_per_100km": round(high_speed_brakes_weighted_total / brakes_distance_total, 2) if brakes_distance_total > 0 else 0.0,
        "cruise_control_ratio": summary_average("cruise_control_ratio", 4),
        "overspeed_ratio": summary_average("overspeed_ratio", 4),
        "analytics_readiness_percent": round(sum(row["analytics_readiness_percent"] for row in rows) / len(rows), 1) if rows else 0.0,
        "anomaly_vehicles_count": anomaly_count,
    }


@router.get("/timeseries")
def timeseries(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(deps.get_fleet_access_user)],
    period: str = "week",
) -> list[dict[str, Any]]:
    vehicles = _load_vehicles_with_analytics(db, current_user)
    current_start, current_end, _, _ = _window(period, vehicles)
    current_start_naive = _naive(current_start)
    current_end_naive = _naive(current_end)
    readiness_by_vehicle = {
        vehicle.id: round(
            (len({link.analytics_key for link in vehicle.analytics_links if link.is_active}) / (TOTAL_ANALYTICS_SENSORS or 1)) * 100,
            1,
        )
        for vehicle in vehicles
    }
    metric_rows = [m for vehicle in vehicles for m in vehicle.metric_windows if _naive(m.period_start) >= current_start_naive and _naive(m.period_end) <= current_end_naive]
    grouped: dict[str, dict[str, Any]] = {}
    for row in metric_rows:
        if not _metric_has_data(row):
            continue
        key = row.period_start.date().isoformat()
        item = grouped.setdefault(key, {"date": key, "metric_count": 0, "rating_count": 0, "readiness_count": 0, "fuel_total": 0.0, "fuel_distance_total": 0.0, "idle_total": 0.0, "engine_total": 0.0, "coasting_ratio": 0.0, "coasting_count": 0, "optimal_rpm_ratio": 0.0, "optimal_rpm_count": 0, "brakes_weighted_total": 0.0, "high_speed_brakes_weighted_total": 0.0, "brakes_distance_total": 0.0, "high_speed_brakes_distance_total": 0.0, "cruise_control_ratio": 0.0, "cruise_control_count": 0, "overspeed_ratio": 0.0, "overspeed_count": 0, "analytics_readiness_percent": 0.0, "rating": 0.0})
        item["metric_count"] += 1
        item["readiness_count"] += 1
        item["analytics_readiness_percent"] += readiness_by_vehicle.get(row.vehicle_id, 0.0)
        if row.fuel_consumed_liters is not None and (row.distance_km or 0.0) > 0:
            item["fuel_total"] += float(row.fuel_consumed_liters or 0.0)
            item["fuel_distance_total"] += float(row.distance_km or 0.0)
        if row.idle_ratio is not None:
            item["idle_total"] += float(row.idle_seconds or 0.0)
            item["engine_total"] += float(row.engine_work_seconds or 0.0)
        coasting_sum, coasting_count = _sum_present([row.coasting_ratio])
        item["coasting_ratio"] += coasting_sum
        item["coasting_count"] += coasting_count
        optimal_sum, optimal_count = _sum_present([row.optimal_rpm_ratio])
        item["optimal_rpm_ratio"] += optimal_sum
        item["optimal_rpm_count"] += optimal_count
        if row.brakes_per_100km is not None and (row.distance_km or 0.0) > 0:
            item["brakes_weighted_total"] += float(row.brakes_per_100km or 0.0) * float(row.distance_km or 0.0)
            item["brakes_distance_total"] += float(row.distance_km or 0.0)
        if row.high_speed_brakes_per_100km is not None and (row.distance_km or 0.0) > 0:
            item["high_speed_brakes_weighted_total"] += float(row.high_speed_brakes_per_100km or 0.0) * float(row.distance_km or 0.0)
            item["high_speed_brakes_distance_total"] += float(row.distance_km or 0.0)
        cruise_sum, cruise_count = _sum_present([row.cruise_control_ratio])
        item["cruise_control_ratio"] += cruise_sum
        item["cruise_control_count"] += cruise_count
        overspeed_sum, overspeed_count = _sum_present([row.overspeed_ratio])
        item["overspeed_ratio"] += overspeed_sum
        item["overspeed_count"] += overspeed_count
    rating_rows = [r for vehicle in vehicles for r in vehicle.rating_windows if _naive(r.period_start) >= current_start_naive and _naive(r.period_end) <= current_end_naive]
    for row in rating_rows:
        if not _rating_has_data(row):
            continue
        key = row.period_start.date().isoformat()
        item = grouped.setdefault(key, {"date": key, "metric_count": 0, "rating_count": 0, "readiness_count": 0, "fuel_total": 0.0, "fuel_distance_total": 0.0, "idle_total": 0.0, "engine_total": 0.0, "coasting_ratio": 0.0, "optimal_rpm_ratio": 0.0, "brakes_weighted_total": 0.0, "high_speed_brakes_weighted_total": 0.0, "brakes_distance_total": 0.0, "cruise_control_ratio": 0.0, "overspeed_ratio": 0.0, "analytics_readiness_percent": 0.0, "rating": 0.0})
        item["rating_count"] += 1
        item["rating"] += row.final_rating
    result = []
    for key in sorted(grouped):
        item = grouped[key]
        metric_count = max(item.pop("metric_count"), 1)
        rating_count = max(item.pop("rating_count"), 1)
        readiness_count = max(item.pop("readiness_count"), 1)
        result.append(
            {
                "date": item["date"],
                "fuel_per_100km": round((item["fuel_total"] / item["fuel_distance_total"]) * 100, 4) if item["fuel_distance_total"] > 0 else 0.0,
                "idle_ratio": round(item["idle_total"] / item["engine_total"], 4) if item["engine_total"] > 0 else 0.0,
                "coasting_ratio": round(item["coasting_ratio"] / item["coasting_count"], 4) if item["coasting_count"] > 0 else 0.0,
                "optimal_rpm_ratio": round(item["optimal_rpm_ratio"] / item["optimal_rpm_count"], 4) if item["optimal_rpm_count"] > 0 else 0.0,
                "brakes_per_100km": round(item["brakes_weighted_total"] / item["brakes_distance_total"], 4) if item["brakes_distance_total"] > 0 else 0.0,
                "high_speed_brakes_per_100km": round(item["high_speed_brakes_weighted_total"] / item["high_speed_brakes_distance_total"], 4) if item["high_speed_brakes_distance_total"] > 0 else 0.0,
                "cruise_control_ratio": round(item["cruise_control_ratio"] / item["cruise_control_count"], 4) if item["cruise_control_count"] > 0 else 0.0,
                "overspeed_ratio": round(item["overspeed_ratio"] / item["overspeed_count"], 4) if item["overspeed_count"] > 0 else 0.0,
                "analytics_readiness_percent": round(item["analytics_readiness_percent"] / readiness_count, 4) if item["analytics_readiness_percent"] else 0.0,
                "rating": round(item["rating"] / rating_count, 4) if item["rating"] else 0.0,
            }
        )
    return result


@router.get("/comparison")
def comparison(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(deps.get_fleet_access_user)],
    period: str = "week",
) -> list[dict[str, Any]]:
    vehicles = _load_vehicles_with_analytics(db, current_user)
    current_start, current_end, _, _ = _window(period, vehicles)
    return [_public_row(row) for row in sorted(_aggregate_vehicle_rows(vehicles, current_start, current_end), key=lambda row: row["rating"], reverse=True)]


@router.get("/problem-vehicles")
def problem_vehicles(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(deps.get_fleet_access_user)],
    period: str = "week",
) -> dict[str, Any]:
    vehicles = _load_vehicles_with_analytics(db, current_user)
    current_start, current_end, _, _ = _window(period, vehicles)
    all_rows = _aggregate_vehicle_rows(vehicles, current_start, current_end)
    rated_rows = [row for row in all_rows if row["__has_rating_data"]]
    unrated_rows = [row for row in all_rows if not row["__has_rating_data"]]
    rows = sorted(rated_rows, key=lambda row: row["rating"]) + sorted(unrated_rows, key=lambda row: row["name"])
    anomaly_ids = _anomaly_vehicle_ids(db, current_user.id, current_start, current_end)

    def enrich(row: dict[str, Any]) -> dict[str, Any]:
        return _public_row(row) | {
            "anomaly_flag": row["vehicle_id"] in anomaly_ids,
            "anomaly_reasons": ["Обнаружена ML-аномалия"] if row["vehicle_id"] in anomaly_ids else [],
        }

    return {"worst": [enrich(row) for row in rows[:5]], "best": [enrich(row) for row in rows[-5:]][::-1]}
