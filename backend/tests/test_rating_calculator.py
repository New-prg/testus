from datetime import UTC, datetime, timedelta
from typing import Any, Mapping

from app.config.rating_profile import CAR_TYPE_KAMAZ, CAR_TYPE_NOT_KAMAZ, RATING_WEIGHTS
from app.services.ratings.metric_calculator import MetricWindowResult
from app.services.ratings.rating_calculator import RatingCalculator, score_by_threshold
from app.services.ratings.threshold_resolver import ThresholdResolver


def build_metric(**overrides: Any) -> MetricWindowResult:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    payload: dict[str, Any] = {
        "vehicle_id": "vehicle-1",
        "period_start": start,
        "period_end": start + timedelta(days=1),
        "distance_km": 100.0,
        "fuel_consumed_liters": 30.0,
        "fuel_per_100km": 30.0,
        "coasting_ratio": 0.35,
        "optimal_rpm_ratio": 0.60,
        "idle_ratio": 0.20,
        "brakes_per_100km": 14.0,
        "high_speed_brakes_per_100km": 4.0,
        "cruise_control_ratio": 0.10,
        "overspeed_ratio": 0.10,
        "engine_work_seconds": 10000.0,
        "moving_seconds": 8000.0,
        "idle_seconds": 1200.0,
        "raw_json": {},
    }
    payload.update(overrides)
    return MetricWindowResult(**payload)


def test_weights_sum_is_about_one() -> None:
    assert abs(sum(RATING_WEIGHTS.values()) - 1.0) <= 0.001


def test_score_by_threshold_predictable_boundaries() -> None:
    threshold: Mapping[str, object] = {"direction": "lower_is_better", "score_thresholds": {1: 20, 5: 10, 10: 5}}
    assert score_by_threshold(4, threshold) == 10
    assert score_by_threshold(10, threshold) == 5
    assert score_by_threshold(21, threshold) == 1


def test_rating_range_is_1_to_10() -> None:
    rating = RatingCalculator().calculate(build_metric(), CAR_TYPE_NOT_KAMAZ)
    assert 1.0 <= rating.final_rating <= 10.0


def test_kamaz_cruise_is_lower_better_and_not_kamaz_higher_better() -> None:
    resolver = ThresholdResolver()
    assert score_by_threshold(2.0, resolver.profile_for(CAR_TYPE_KAMAZ)["cruise_control"]) > score_by_threshold(10.0, resolver.profile_for(CAR_TYPE_KAMAZ)["cruise_control"])
    assert score_by_threshold(12.0, resolver.profile_for(CAR_TYPE_NOT_KAMAZ)["cruise_control"]) > score_by_threshold(4.0, resolver.profile_for(CAR_TYPE_NOT_KAMAZ)["cruise_control"])


def test_null_metrics_do_not_break_rating() -> None:
    rating = RatingCalculator().calculate(build_metric(cruise_control_ratio=None, coasting_ratio=None), CAR_TYPE_NOT_KAMAZ)
    assert rating.metric_scores["cruise_control"] is None
    assert rating.metric_scores["coasting"] is None
    assert 1.0 <= rating.final_rating <= 10.0
    assert rating.warnings
