from importlib import import_module
from typing import Any

from app.services.ml.evaluation import anomaly_metrics
from app.services.ml.preprocessing import preprocess_feature_rows


FEATURE_LABELS_RU = {
    "fuel_per_100km": "расход топлива на 100 км",
    "idle_ratio": "доля простоя",
    "brakes_per_100km": "торможения на 100 км",
    "high_speed_brakes_per_100km": "резкие торможения на скорости",
    "overspeed_ratio": "доля превышения скорости",
    "coasting_ratio": "доля движения накатом",
    "optimal_rpm_ratio": "доля оптимальных оборотов",
    "cruise_control_ratio": "использование круиз-контроля",
    "distance_km": "пробег",
}


class AnomalyService:
    def detect(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        if len(rows) < 5:
            return {"message": "Недостаточно данных для обучения модели.", "model_name": "anomaly_comparison", "metrics": {"samples": len(rows)}, "model_runs": [], "results": []}
        prepared = preprocess_feature_rows(rows, scaler="robust")
        fleet_stats = self._fleet_stats(rows, prepared.feature_names)
        model_runs = []
        combined_results = []
        for predictions, scores, model_name in self._predict_all(prepared.matrix):
            labels = ["anomaly" if prediction == -1 else "normal" for prediction in predictions]
            results = []
            for row, label, score in zip(rows, labels, scores, strict=True):
                results.append(
                    row
                    | {
                        "model_name": model_name,
                        "score": float(score),
                        "label": label,
                        "explanation": self._explain_row(prepared.feature_names, row, fleet_stats),
                    }
                )
            metrics = anomaly_metrics(labels, [float(score) for score in scores])
            model_runs.append({"model_name": model_name, "metrics": metrics, "results": results})
            combined_results.extend(results)
        return {
            "message": "ok",
            "model_name": "anomaly_comparison",
            "feature_names": prepared.feature_names,
            "preprocessing": prepared.metadata,
            "metrics": {run["model_name"]: run["metrics"] for run in model_runs},
            "model_runs": model_runs,
            "results": combined_results,
        }

    @staticmethod
    def _predict_all(matrix: Any) -> list[tuple[list[int], list[float], str]]:
        runs = [AnomalyService._robust_zscore_predictions(matrix)]
        try:
            isolation_forest_class = import_module("sklearn.ensemble").IsolationForest
            model = isolation_forest_class(random_state=42, contamination=0.15)
            predictions = [int(value) for value in model.fit_predict(matrix)]
            scores = [float(value) for value in model.decision_function(matrix)]
            runs.insert(0, (predictions, scores, "isolation_forest"))
        except ModuleNotFoundError:
            runs.insert(0, AnomalyService._robust_zscore_predictions(matrix, model_name="isolation_forest_fallback"))
        return runs

    @staticmethod
    def _robust_zscore_predictions(matrix: Any, model_name: str = "robust_zscore_baseline") -> tuple[list[int], list[float], str]:
        distances = [-sum(value**2 for value in row) ** 0.5 for row in matrix]
        anomaly_count = max(1, round(len(distances) * 0.15))
        cutoff = sorted(distances)[:anomaly_count][-1]
        predictions = [-1 if score <= cutoff else 1 for score in distances]
        return predictions, distances, model_name

    @staticmethod
    def _explain_row(feature_names: list[str], row: dict[str, Any], fleet_stats: dict[str, dict[str, float]]) -> dict[str, Any]:
        deviations = []
        for feature in feature_names:
            value = row["features"].get(feature)
            stats = fleet_stats.get(feature)
            if value is None or not stats:
                continue
            median = stats["median"]
            mean = stats["mean"]
            spread = max(stats["max"] - stats["min"], 1.0)
            delta = float(value) - median
            deviations.append((abs(delta) / spread, feature, float(value), median, mean, delta))
        top_factors = []
        for _, feature, value, median, mean, delta in sorted(deviations, reverse=True)[:3]:
            direction = "выше" if delta > 0 else "ниже"
            label = FEATURE_LABELS_RU.get(feature) or feature
            top_factors.append(
                {
                    "feature": feature,
                    "feature_label_ru": label,
                    "value": value,
                    "fleet_median": median,
                    "fleet_mean": mean,
                    "difference_from_median": delta,
                    "message_ru": f"{label.capitalize()} {direction} медианы автопарка: {value:.3f} против {median:.3f}.",
                }
            )
        return {
            "top_factors": top_factors,
            "summary_ru": "Отклонение рассчитано сравнением показателей автомобиля с медианой и средним значением автопарка.",
            "baseline_final_rating": row.get("baseline", {}).get("final_rating"),
            "negative_factors": row.get("interpretation", {}).get("negative_factors", []),
        }

    @staticmethod
    def _fleet_stats(rows: list[dict[str, Any]], feature_names: list[str]) -> dict[str, dict[str, float]]:
        stats: dict[str, dict[str, float]] = {}
        for feature in feature_names:
            values = [float(row["features"][feature]) for row in rows if row.get("features", {}).get(feature) is not None]
            if not values:
                continue
            ordered = sorted(values)
            middle = len(ordered) // 2
            median = ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2
            stats[feature] = {
                "mean": sum(values) / len(values),
                "median": median,
                "min": min(values),
                "max": max(values),
            }
        return stats
