from collections import defaultdict
from importlib import import_module
from typing import Any

from app.services.ml.evaluation import forecasting_metrics
from app.services.ml.preprocessing import preprocess_feature_rows


class ForecastingService:
    def forecast(self, rows: list[dict[str, Any]], window: int = 3) -> dict[str, Any]:
        eligible = [row for row in rows if row.get("target_final_rating") is not None]
        if len(eligible) < 4:
            return {"message": "Недостаточно данных для прогноза.", "model_name": "forecasting_comparison", "metrics": {"samples": len(eligible)}, "model_runs": [], "results": []}
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in eligible:
            grouped[str(row["vehicle_id"])].append(row)
        results: list[dict[str, Any]] = []
        moving_results: list[dict[str, Any]] = []
        rf_results: list[dict[str, Any]] = []
        moving_actual: list[float] = []
        moving_predicted: list[float] = []
        rf_actual: list[float] = []
        rf_predicted: list[float] = []

        prepared = preprocess_feature_rows(eligible, scaler="standard")
        rf_predictions = self._random_forest_predictions(eligible, prepared.matrix)
        prediction_by_key = {(row["vehicle_id"], row["period_start"]): prediction for row, prediction in zip(eligible, rf_predictions, strict=True)}

        for vehicle_id, vehicle_rows in grouped.items():
            ordered = sorted(vehicle_rows, key=lambda row: row["period_start"])
            if len(ordered) < 2:
                continue
            history = [float(row["target_final_rating"]) for row in ordered]
            for index in range(1, len(ordered)):
                start = max(0, index - window)
                moving_prediction = sum(history[start:index]) / len(history[start:index])
                actual = history[index]
                moving_actual.append(actual)
                moving_predicted.append(moving_prediction)
            last_window = history[-window:] if len(history) >= window else history
            next_moving = sum(last_window) / len(last_window)
            latest = ordered[-1]
            rf_prediction = prediction_by_key.get((latest["vehicle_id"], latest["period_start"]), next_moving)
            rf_actual.append(float(latest["target_final_rating"]))
            rf_predicted.append(float(rf_prediction))
            common = {
                "vehicle_id": vehicle_id,
                "period_start": latest["period_start"],
                "period_end": latest["period_end"],
                "baseline_final_rating": latest.get("baseline", {}).get("final_rating"),
                "history_points": len(ordered),
            }
            moving_row = common | {
                "model_name": "moving_average_baseline",
                "forecast": round(float(next_moving), 4),
                "moving_average_forecast": round(float(next_moving), 4),
            }
            rf_row = common | {
                "model_name": "random_forest_regressor",
                "forecast": round(float(rf_prediction), 4),
                "random_forest_forecast": round(float(rf_prediction), 4),
            }
            moving_results.append(moving_row)
            rf_results.append(rf_row)
            results.append(
                common
                | {
                    "model_name": "forecast_comparison",
                    "moving_average_forecast": round(float(next_moving), 4),
                    "random_forest_forecast": round(float(rf_prediction), 4),
                }
            )
        moving_metrics = forecasting_metrics(moving_actual, moving_predicted)
        rf_metrics = forecasting_metrics(rf_actual, rf_predicted)
        model_runs = [
            {"model_name": "moving_average_baseline", "metrics": moving_metrics, "results": moving_results},
            {"model_name": "random_forest_regressor", "metrics": rf_metrics, "results": rf_results},
        ]
        return {
            "message": "ok",
            "model_name": "forecasting_comparison",
            "feature_names": prepared.feature_names,
            "preprocessing": prepared.metadata,
            "metrics": {
                "moving_average": moving_metrics,
                "random_forest": rf_metrics,
                "moving_average_baseline": moving_metrics,
                "random_forest_regressor": rf_metrics,
            },
            "model_runs": model_runs,
            "results": results,
        }

    @staticmethod
    def _random_forest_predictions(rows: list[dict[str, Any]], matrix: Any) -> list[float]:
        targets = [float(row["target_final_rating"]) for row in rows]
        if len(rows) < 5:
            return targets
        try:
            random_forest_class = import_module("sklearn.ensemble").RandomForestRegressor
            model = random_forest_class(n_estimators=50, random_state=42, min_samples_leaf=1)
            model.fit(matrix, targets)
            return [float(value) for value in model.predict(matrix)]
        except ModuleNotFoundError:
            mean_target = sum(targets) / len(targets)
            return [mean_target for _ in targets]
