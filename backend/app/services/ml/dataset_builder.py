from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import VehicleMetricWindow, VehicleRatingWindow


class DatasetBuilder:
    feature_names = [
        "fuel_per_100km",
        "coasting_ratio",
        "optimal_rpm_ratio",
        "idle_ratio",
        "brakes_per_100km",
        "high_speed_brakes_per_100km",
        "cruise_control_ratio",
        "overspeed_ratio",
        "final_rating",
    ]

    def build(self, db: Session, limit: int = 500) -> list[dict[str, Any]]:
        metrics = db.scalars(select(VehicleMetricWindow).order_by(VehicleMetricWindow.period_start.desc()).limit(min(limit, 1000))).all()
        ratings = {
            (rating.vehicle_id, rating.period_start, rating.period_end): rating
            for rating in db.scalars(select(VehicleRatingWindow).order_by(VehicleRatingWindow.period_start.desc()).limit(min(limit, 1000))).all()
        }
        rows = []
        for metric in metrics:
            rating = ratings.get((metric.vehicle_id, metric.period_start, metric.period_end))
            rows.append(
                {
                    "vehicle_id": metric.vehicle_id,
                    "period_start": metric.period_start.isoformat(),
                    "period_end": metric.period_end.isoformat(),
                    "features": {
                        "fuel_per_100km": float(metric.fuel_per_100km or 0.0),
                        "coasting_ratio": float(metric.coasting_ratio or 0.0),
                        "optimal_rpm_ratio": float(metric.optimal_rpm_ratio or 0.0),
                        "idle_ratio": float(metric.idle_ratio or 0.0),
                        "brakes_per_100km": float(metric.brakes_per_100km or 0.0),
                        "high_speed_brakes_per_100km": float(metric.high_speed_brakes_per_100km or 0.0),
                        "cruise_control_ratio": float(metric.cruise_control_ratio or 0.0),
                        "overspeed_ratio": float(metric.overspeed_ratio or 0.0),
                        "final_rating": float(rating.final_rating if rating else 0.0),
                    },
                }
            )
        return rows
