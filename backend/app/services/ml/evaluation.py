from importlib import import_module
from math import sqrt
from typing import Any


def anomaly_metrics(labels: list[str], scores: list[float]) -> dict[str, Any]:
    total = len(labels)
    anomalies = sum(1 for label in labels if label == "anomaly")
    ordered_scores = sorted(scores)
    score_summary = {
        "min": min(scores) if scores else None,
        "max": max(scores) if scores else None,
        "mean": sum(scores) / len(scores) if scores else None,
        "median": _median(ordered_scores) if ordered_scores else None,
    }
    return {
        "samples": total,
        "count": anomalies,
        "share": round(anomalies / total, 4) if total else 0.0,
        "score_summary": score_summary,
        # Backward-compatible aliases for existing consumers/tests.
        "anomalies": anomalies,
        "anomaly_rate": round(anomalies / total, 4) if total else 0.0,
        "score_min": score_summary["min"],
        "score_max": score_summary["max"],
    }


def clustering_metrics(matrix: Any, labels: list[int]) -> dict[str, Any]:
    unique_labels = sorted(set(labels))
    result: dict[str, Any] = {"samples": len(labels), "clusters": len(unique_labels), "label_counts": {str(label): labels.count(label) for label in unique_labels}}
    try:
        metrics = import_module("sklearn.metrics")
        if len(labels) > len(unique_labels) > 1:
            result["silhouette_score"] = float(metrics.silhouette_score(matrix, labels))
            result["davies_bouldin_score"] = float(metrics.davies_bouldin_score(matrix, labels))
            result["calinski_harabasz_score"] = float(metrics.calinski_harabasz_score(matrix, labels))
        else:
            result["silhouette_score"] = None
            result["davies_bouldin_score"] = None
            result["calinski_harabasz_score"] = None
    except ModuleNotFoundError:
        result["silhouette_score"] = None
        result["davies_bouldin_score"] = None
        result["calinski_harabasz_score"] = None
    return result


def forecasting_metrics(actual: list[float], predicted: list[float]) -> dict[str, Any]:
    if not actual or not predicted:
        return {"samples": 0, "MAE": None, "RMSE": None, "R2": None, "mae": None, "rmse": None, "r2": None}
    errors = [truth - estimate for truth, estimate in zip(actual, predicted, strict=True)]
    mae = sum(abs(error) for error in errors) / len(errors)
    rmse = sqrt(sum(error**2 for error in errors) / len(errors))
    mean_actual = sum(actual) / len(actual)
    total_variance = sum((truth - mean_actual) ** 2 for truth in actual)
    residual_variance = sum(error**2 for error in errors)
    r2 = 1 - residual_variance / total_variance if total_variance else None
    return {
        "samples": len(actual),
        "MAE": mae,
        "RMSE": rmse,
        "R2": r2,
        # Backward-compatible aliases.
        "mae": mae,
        "rmse": rmse,
        "r2": r2,
    }


def _median(values: list[float]) -> float:
    middle = len(values) // 2
    if len(values) % 2:
        return values[middle]
    return (values[middle - 1] + values[middle]) / 2
