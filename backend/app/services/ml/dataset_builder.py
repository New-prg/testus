from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Vehicle, VehicleMetricWindow, VehicleRatingWindow


class FeatureBuilder:
    metric_feature_names = [
        "distance_km",
        "fuel_consumed_liters",
        "fuel_per_100km",
        "coasting_ratio",
        "optimal_rpm_ratio",
        "idle_ratio",
        "brakes_per_100km",
        "high_speed_brakes_per_100km",
        "cruise_control_ratio",
        "overspeed_ratio",
        "engine_work_seconds",
        "moving_seconds",
        "idle_seconds",
    ]
    feature_names = [*metric_feature_names]

    def build(self, db: Session, limit: int = 500, user_id: str | None = None) -> list[dict[str, Any]]:
        metrics_query = select(VehicleMetricWindow).order_by(VehicleMetricWindow.period_start.desc()).limit(min(limit, 1000))
        ratings_query = select(VehicleRatingWindow).order_by(VehicleRatingWindow.period_start.desc()).limit(min(limit, 1000))
        if user_id:
            metrics_query = metrics_query.join(Vehicle, Vehicle.id == VehicleMetricWindow.vehicle_id).where(Vehicle.user_id == user_id)
            ratings_query = ratings_query.join(Vehicle, Vehicle.id == VehicleRatingWindow.vehicle_id).where(Vehicle.user_id == user_id)
        metrics = db.scalars(metrics_query).all()
        ratings = {
            (rating.vehicle_id, rating.period_start, rating.period_end): rating
            for rating in db.scalars(ratings_query).all()
        }
        rows: list[dict[str, Any]] = []
        for metric in metrics:
            rating = ratings.get((metric.vehicle_id, metric.period_start, metric.period_end))
            features = {name: self._as_float(getattr(metric, name, None)) for name in self.metric_feature_names}
            rows.append(
                {
                    "vehicle_id": metric.vehicle_id,
                    "period_start": metric.period_start.isoformat(),
                    "period_end": metric.period_end.isoformat(),
                    "features": features,
                    "target_final_rating": float(rating.final_rating) if rating else None,
                    "baseline": {"final_rating": float(rating.final_rating) if rating else None},
                    "interpretation": {
                        "warnings": list(rating.warnings_json or []) if rating else [],
                        "positive_factors": list(rating.positive_factors_json or []) if rating else [],
                        "negative_factors": list(rating.negative_factors_json or []) if rating else [],
                    },
                }
            )
        return rows

    @staticmethod
    def _as_float(value: Any) -> float | None:
        if value is None:
            return None
        return float(value)


class DatasetBuilder(FeatureBuilder):
    """Backward-compatible alias for older callers."""
