from collections import defaultdict
from importlib import import_module
from math import isnan, sqrt
from typing import Any

from app.services.ml.evaluation import forecasting_metrics
from app.services.ml.preprocessing import rows_value


class ForecastingService:
    def forecast(self, rows: list[dict[str, Any]], window: int = 3) -> dict[str, Any]:
        eligible = [row for row in rows if row.get("target_final_rating") is not None]
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in eligible:
            grouped[str(row["vehicle_id"])].append(row)
        train_rows: list[dict[str, Any]] = []
        test_rows: list[dict[str, Any]] = []
        moving_baselines: dict[tuple[str, Any], float] = {}

        for vehicle_id, vehicle_rows in grouped.items():
            ordered = sorted(vehicle_rows, key=lambda row: row["period_start"])
            if len(ordered) < 2:
                continue
            history = [float(row["target_final_rating"]) for row in ordered]
            test_row = ordered[-1]
            test_rows.append(test_row)
            train_rows.extend(ordered[:-1])
            start = max(0, len(history) - 1 - window)
            moving_baselines[(vehicle_id, test_row["period_start"])] = sum(history[start:-1]) / len(history[start:-1])

        if len(train_rows) < 2 or not test_rows:
            return self._skipped_payload(eligible, train_rows, test_rows)

        feature_names, train_matrix, test_matrix, preprocessing_metadata = self._prepare_train_test_matrices(train_rows, test_rows)
        rf_prediction_by_key = self._random_forest_predictions(train_rows, test_rows, train_matrix, test_matrix)

        results: list[dict[str, Any]] = []
        moving_results: list[dict[str, Any]] = []
        rf_results: list[dict[str, Any]] = []
        moving_actual: list[float] = []
        moving_predicted: list[float] = []
        rf_actual: list[float] = []
        rf_predicted: list[float] = []

        for latest in sorted(test_rows, key=lambda row: (row["vehicle_id"], row["period_start"])):
            vehicle_id = str(latest["vehicle_id"])
            next_moving = moving_baselines[(vehicle_id, latest["period_start"])]
            rf_prediction = rf_prediction_by_key.get((vehicle_id, latest["period_start"]), next_moving)
            actual = float(latest["target_final_rating"])
            moving_actual.append(actual)
            moving_predicted.append(float(next_moving))
            rf_actual.append(actual)
            rf_predicted.append(float(rf_prediction))
            common = {
                "vehicle_id": vehicle_id,
                "period_start": latest["period_start"],
                "period_end": latest["period_end"],
                "baseline_final_rating": latest.get("baseline", {}).get("final_rating"),
                "history_points": len(grouped[vehicle_id]),
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
            "feature_names": feature_names,
            "preprocessing": preprocessing_metadata,
            "metrics": {
                "evaluation": "time_based_holdout",
                "train_samples": len(train_rows),
                "test_samples": len(test_rows),
                "moving_average": moving_metrics,
                "random_forest": rf_metrics,
                "moving_average_baseline": moving_metrics,
                "random_forest_regressor": rf_metrics,
            },
            "model_runs": model_runs,
            "results": results,
        }

    @staticmethod
    def _random_forest_predictions(
        train_rows: list[dict[str, Any]], test_rows: list[dict[str, Any]], train_matrix: list[list[float]] | Any, test_matrix: list[list[float]] | Any
    ) -> dict[tuple[str, Any], float]:
        if len(train_rows) < 5 or not test_rows:
            return {}
        targets = [float(row["target_final_rating"]) for row in train_rows]
        try:
            random_forest_class = import_module("sklearn.ensemble").RandomForestRegressor
            model = random_forest_class(n_estimators=50, random_state=42, min_samples_leaf=1)
            model.fit(train_matrix, targets)
            predictions = [float(value) for value in model.predict(test_matrix)]
            return {
                (str(row["vehicle_id"]), row["period_start"]): prediction
                for row, prediction in zip(test_rows, predictions, strict=True)
            }
        except ModuleNotFoundError:
            return {}

    @staticmethod
    def _prepare_train_test_matrices(
        train_rows: list[dict[str, Any]], test_rows: list[dict[str, Any]]
    ) -> tuple[list[str], list[list[float]] | Any, list[list[float]] | Any, dict[str, Any]]:
        feature_names = list(train_rows[0]["features"].keys()) if train_rows else []
        try:
            np = import_module("numpy")
            scalers = import_module("sklearn.preprocessing")
            raw_train = np.array([[rows_value(row, name) for name in feature_names] for row in train_rows], dtype=float)
            raw_test = np.array([[rows_value(row, name) for name in feature_names] for row in test_rows], dtype=float)
            missing_counts = {name: int(np.isnan(raw_train[:, idx]).sum()) if raw_train.size else 0 for idx, name in enumerate(feature_names)}
            medians = np.nanmedian(raw_train, axis=0) if raw_train.size else np.array([], dtype=float)
            medians = np.where(np.isnan(medians), 0.0, medians)
            if raw_train.size:
                train_nan_rows, train_nan_cols = np.where(np.isnan(raw_train))
                raw_train[train_nan_rows, train_nan_cols] = medians[train_nan_cols]
            if raw_test.size:
                test_nan_rows, test_nan_cols = np.where(np.isnan(raw_test))
                raw_test[test_nan_rows, test_nan_cols] = medians[test_nan_cols]
            scaler = scalers.StandardScaler()
            train_matrix = scaler.fit_transform(raw_train)
            test_matrix = scaler.transform(raw_test) if raw_test.size else raw_test
            train_matrix = np.nan_to_num(train_matrix, nan=0.0, posinf=0.0, neginf=0.0)
            test_matrix = np.nan_to_num(test_matrix, nan=0.0, posinf=0.0, neginf=0.0)
            metadata = {
                "row_count": len(train_rows),
                "scaler": "standard",
                "missing_counts": missing_counts,
                "imputation": {name: float(medians[idx]) for idx, name in enumerate(feature_names)},
            }
            return feature_names, train_matrix, test_matrix, metadata
        except ModuleNotFoundError:
            return ForecastingService._prepare_train_test_matrices_stdlib(train_rows, test_rows, feature_names)

    @staticmethod
    def _prepare_train_test_matrices_stdlib(
        train_rows: list[dict[str, Any]], test_rows: list[dict[str, Any]], feature_names: list[str]
    ) -> tuple[list[str], list[list[float]], list[list[float]], dict[str, Any]]:
        train_raw = [[rows_value(row, name) for name in feature_names] for row in train_rows]
        test_raw = [[rows_value(row, name) for name in feature_names] for row in test_rows]
        columns = [[row[idx] for row in train_raw] for idx in range(len(feature_names))]
        imputations = [ForecastingService._median([value for value in column if not isnan(value)]) for column in columns]
        missing_counts = {name: sum(1 for value in columns[idx] if isnan(value)) for idx, name in enumerate(feature_names)}
        imputed_train = [[imputations[idx] if isnan(value) else value for idx, value in enumerate(row)] for row in train_raw]
        imputed_test = [[imputations[idx] if isnan(value) else value for idx, value in enumerate(row)] for row in test_raw]
        stats = ForecastingService._standard_stats(imputed_train)
        train_matrix = [ForecastingService._scale_row(row, stats) for row in imputed_train]
        test_matrix = [ForecastingService._scale_row(row, stats) for row in imputed_test]
        metadata = {
            "row_count": len(train_rows),
            "scaler": "standard_stdlib_fallback",
            "missing_counts": missing_counts,
            "imputation": {name: float(imputations[idx]) for idx, name in enumerate(feature_names)},
        }
        return feature_names, train_matrix, test_matrix, metadata

    @staticmethod
    def _scale_row(row: list[float], stats: list[tuple[float, float]]) -> list[float]:
        return [0.0 if stats[idx][1] == 0 else (value - stats[idx][0]) / stats[idx][1] for idx, value in enumerate(row)]

    @staticmethod
    def _standard_stats(matrix: list[list[float]]) -> list[tuple[float, float]]:
        if not matrix:
            return []
        stats: list[tuple[float, float]] = []
        for column in zip(*matrix, strict=True):
            mean = sum(column) / len(column)
            variance = sum((value - mean) ** 2 for value in column) / len(column)
            stats.append((mean, sqrt(variance)))
        return stats

    @staticmethod
    def _median(values: list[float]) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        middle = len(ordered) // 2
        if len(ordered) % 2:
            return float(ordered[middle])
        return float((ordered[middle - 1] + ordered[middle]) / 2)

    @staticmethod
    def _skipped_payload(
        eligible_rows: list[dict[str, Any]], train_rows: list[dict[str, Any]], test_rows: list[dict[str, Any]]
    ) -> dict[str, Any]:
        skipped_metrics = {"samples": 0, "MAE": None, "RMSE": None, "R2": None, "mae": None, "rmse": None, "r2": None}
        return {
            "message": "Недостаточно данных для честной time-based оценки прогноза.",
            "model_name": "forecasting_comparison",
            "feature_names": [],
            "preprocessing": {},
            "metrics": {
                "evaluation": "time_based_holdout",
                "eligible_samples": len(eligible_rows),
                "train_samples": len(train_rows),
                "test_samples": len(test_rows),
                "moving_average": skipped_metrics,
                "random_forest": skipped_metrics,
                "moving_average_baseline": skipped_metrics,
                "random_forest_regressor": skipped_metrics,
            },
            "model_runs": [
                {"model_name": "moving_average_baseline", "metrics": skipped_metrics, "results": []},
                {"model_name": "random_forest_regressor", "metrics": skipped_metrics, "results": []},
            ],
            "results": [],
        }
