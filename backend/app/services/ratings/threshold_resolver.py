from typing import Any

from app.config.rating_profile import CAR_TYPE_UNKNOWN, RATING_THRESHOLDS


class ThresholdResolver:
    def profile_for(self, car_type: str | None) -> dict[str, dict[str, Any]]:
        normalized = (car_type or CAR_TYPE_UNKNOWN).upper()
        return RATING_THRESHOLDS.get(normalized, RATING_THRESHOLDS[CAR_TYPE_UNKNOWN])
