from collections.abc import Mapping


class RatingExplainer:
    def explain(self, metric_scores: Mapping[str, float | None]) -> tuple[list[str], list[str], list[str]]:
        warnings = [f"{name} is missing, rating was recalculated using available weights" for name, value in metric_scores.items() if value is None]
        positive = [f"high {name} score" for name, value in metric_scores.items() if value is not None and value >= 8]
        negative = [f"low {name} score" for name, value in metric_scores.items() if value is not None and value <= 4]
        return warnings, positive, negative
