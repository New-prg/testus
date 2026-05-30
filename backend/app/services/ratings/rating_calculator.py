from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, cast

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config.rating_profile import CAR_TYPE_UNKNOWN, RATING_WEIGHTS
from app.db.models import Vehicle, VehicleMetricWindow, VehicleRatingWindow
from app.services.ratings.metric_calculator import MetricWindowResult
from app.services.ratings.rating_explainer import RatingExplainer
from app.services.ratings.threshold_resolver import ThresholdResolver

RATING_VALUE_MAP = {
    "coasting": "coasting_ratio",
    "fuel": "fuel_per_100km",
    "optimal_rpm": "optimal_rpm_ratio",
    "idle": "idle_ratio",
    "braking": "brakes_per_100km",
    "anticipation": "high_speed_brakes_per_100km",
    "cruise_control": "cruise_control_ratio",
    "overspeed": "overspeed_ratio",
}


@dataclass(frozen=True)
class RatingResult:
    vehicle_id: str
    period_start: datetime
    period_end: datetime
    car_type: str
    metric_scores: dict[str, float | None]
    renormalized_weights: dict[str, float]
    final_rating: float
    warnings: list[str]
    positive_factors: list[str]
    negative_factors: list[str]
    explanation_json: dict[str, Any]


def score_by_threshold(value: float, threshold: Mapping[str, object]) -> float:
    direction = str(threshold["direction"])
    raw_thresholds = cast(dict[int, int | float], threshold["score_thresholds"])
    score_thresholds = {int(score): float(limit) for score, limit in raw_thresholds.items()}
    if direction == "higher_is_better":
        eligible = [score for score, limit in score_thresholds.items() if value >= limit]
    else:
        eligible = [score for score, limit in score_thresholds.items() if value <= limit]
    return float(max(eligible)) if eligible else 1.0


class RatingCalculator:
    def __init__(self, weights: dict[str, float] | None = None, resolver: ThresholdResolver | None = None) -> None:
        self.weights = weights or RATING_WEIGHTS
        self.resolver = resolver or ThresholdResolver()
        self.explainer = RatingExplainer()

    def calculate(self, metric: MetricWindowResult | VehicleMetricWindow, car_type: str | None = None) -> RatingResult:
        normalized_car_type = (car_type or CAR_TYPE_UNKNOWN).upper()
        thresholds = self.resolver.profile_for(normalized_car_type)
        metric_values = self._metric_values(metric)
        metric_scores = {
            name: score_by_threshold(value, thresholds[name]) if value is not None else None
            for name, value in metric_values.items()
        }
        renormalized_weights = self._renormalized_weights(metric_scores)
        final_rating = round(sum((metric_scores[name] or 0.0) * weight for name, weight in renormalized_weights.items()), 2) if renormalized_weights else 1.0
        warnings, positive, negative = self.explainer.explain(metric_scores)
        explanation_json = {
            "warnings": warnings,
            "positive_factors": positive,
            "negative_factors": negative,
            "renormalized_weights": renormalized_weights,
            "metric_values": metric_values,
        }
        return RatingResult(
            vehicle_id=metric.vehicle_id,
            period_start=metric.period_start,
            period_end=metric.period_end,
            car_type=normalized_car_type,
            metric_scores=metric_scores,
            renormalized_weights=renormalized_weights,
            final_rating=max(1.0, min(10.0, final_rating)),
            warnings=warnings,
            positive_factors=positive,
            negative_factors=negative,
            explanation_json=explanation_json,
        )

    def calculate_and_store(self, db: Session, vehicle: Vehicle, metric: MetricWindowResult | VehicleMetricWindow) -> VehicleRatingWindow:
        result = self.calculate(metric, vehicle.car_type)
        db.execute(
            delete(VehicleRatingWindow).where(
                VehicleRatingWindow.vehicle_id == vehicle.id,
                VehicleRatingWindow.period_start == metric.period_start,
                VehicleRatingWindow.period_end == metric.period_end,
            )
        )
        metric_window_id = metric.id if isinstance(metric, VehicleMetricWindow) else None
        rating = VehicleRatingWindow(
            vehicle_id=result.vehicle_id,
            metric_window_id=metric_window_id,
            period_start=result.period_start,
            period_end=result.period_end,
            car_type=result.car_type,
            final_rating=result.final_rating,
            coasting_score=result.metric_scores["coasting"],
            fuel_score=result.metric_scores["fuel"],
            optimal_rpm_score=result.metric_scores["optimal_rpm"],
            idle_score=result.metric_scores["idle"],
            brakes_score=result.metric_scores["braking"],
            high_speed_brakes_score=result.metric_scores["anticipation"],
            cruise_control_score=result.metric_scores["cruise_control"],
            overspeed_score=result.metric_scores["overspeed"],
            weights_json=result.renormalized_weights,
            warnings_json=result.warnings,
            positive_factors_json=result.positive_factors,
            negative_factors_json=result.negative_factors,
            raw_json=result.explanation_json,
        )
        db.add(rating)
        db.flush()
        return rating

    def _renormalized_weights(self, metric_scores: dict[str, float | None]) -> dict[str, float]:
        available = {name: weight for name, weight in self.weights.items() if metric_scores.get(name) is not None and weight > 0}
        total = sum(available.values())
        return {name: round(weight / total, 6) for name, weight in available.items()} if total else {}

    @staticmethod
    def _metric_values(metric: MetricWindowResult | VehicleMetricWindow) -> dict[str, float | None]:
        values: dict[str, float | None] = {}
        for rating_key, model_attr in RATING_VALUE_MAP.items():
            value = getattr(metric, model_attr)
            values[rating_key] = round(value * 100, 3) if value is not None and model_attr.endswith("_ratio") else value
        return values
