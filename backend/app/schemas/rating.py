from datetime import datetime
from typing import Any

from pydantic import BaseModel


class RatingRead(BaseModel):
    id: str
    vehicle_id: str
    metric_window_id: str | None
    period_start: datetime
    period_end: datetime
    car_type: str
    final_rating: float
    fuel_score: float | None
    coasting_score: float | None
    optimal_rpm_score: float | None
    idle_score: float | None
    brakes_score: float | None
    high_speed_brakes_score: float | None
    cruise_control_score: float | None
    overspeed_score: float | None
    weights_json: dict[str, Any]
    warnings_json: list[str]
    positive_factors_json: list[str]
    negative_factors_json: list[str]

    model_config = {"from_attributes": True}
