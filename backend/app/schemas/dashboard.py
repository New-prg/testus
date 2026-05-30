from typing import Any

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    vehicle_count: int
    metric_windows: int
    average_rating: float
    total_distance_km: float
    total_fuel_liters: float


class DashboardPayload(BaseModel):
    summary: DashboardSummary
    latest_ratings: list[dict[str, Any]]
