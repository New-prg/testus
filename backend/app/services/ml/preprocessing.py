from dataclasses import dataclass
from importlib import import_module
from math import isnan, sqrt
from typing import Any, Literal


class Matrix(list[list[float]]):
    @property
    def shape(self) -> tuple[int, int]:
        return (len(self), len(self[0]) if self else 0)


@dataclass(frozen=True)
class PreprocessedDataset:
    feature_names: list[str]
    matrix: Any
    metadata: dict[str, Any]


def preprocess_feature_rows(rows: list[dict[str, Any]], scaler: Literal["standard", "robust"] = "standard") -> PreprocessedDataset:
    try:
        return _preprocess_with_sklearn(rows, scaler)
    except ModuleNotFoundError:
        return _preprocess_with_stdlib(rows, scaler)


def rows_value(row: dict[str, Any], feature_name: str) -> float:
    value = row.get("features", {}).get(feature_name)
    if value is None or value == "":
        return float("nan")
    return float(value)


def _preprocess_with_sklearn(rows: list[dict[str, Any]], scaler: Literal["standard", "robust"]) -> PreprocessedDataset:
    np = import_module("numpy")
    scalers = import_module("sklearn.preprocessing")
    feature_names = list(rows[0]["features"].keys()) if rows else []
    raw = np.array([[rows_value(row, name) for name in feature_names] for row in rows], dtype=float) if rows else np.empty((0, 0), dtype=float)
    missing_counts = {name: int(np.isnan(raw[:, idx]).sum()) if raw.size else 0 for idx, name in enumerate(feature_names)}
    if raw.size:
        medians = np.nanmedian(raw, axis=0)
        medians = np.where(np.isnan(medians), 0.0, medians)
        nan_rows, nan_cols = np.where(np.isnan(raw))
        raw[nan_rows, nan_cols] = medians[nan_cols]
        scaler_class = scalers.RobustScaler if scaler == "robust" else scalers.StandardScaler
        matrix = scaler_class().fit_transform(raw)
        matrix = np.nan_to_num(matrix, nan=0.0, posinf=0.0, neginf=0.0)
    else:
        medians = np.array([], dtype=float)
        matrix = raw
    metadata = {
        "row_count": len(rows),
        "scaler": scaler,
        "missing_counts": missing_counts,
        "imputation": {name: float(medians[idx]) for idx, name in enumerate(feature_names)},
    }
    return PreprocessedDataset(feature_names=feature_names, matrix=matrix, metadata=metadata)


def _preprocess_with_stdlib(rows: list[dict[str, Any]], scaler: Literal["standard", "robust"]) -> PreprocessedDataset:
    feature_names = list(rows[0]["features"].keys()) if rows else []
    raw = [[rows_value(row, name) for name in feature_names] for row in rows]
    columns = [[row[idx] for row in raw] for idx in range(len(feature_names))]
    imputations = [_median([value for value in column if not isnan(value)]) for column in columns]
    missing_counts = {name: sum(1 for value in columns[idx] if isnan(value)) for idx, name in enumerate(feature_names)}
    imputed = [[imputations[idx] if isnan(value) else value for idx, value in enumerate(row)] for row in raw]
    scaled = Matrix()
    stats = _robust_stats(imputed) if scaler == "robust" else _standard_stats(imputed)
    for row in imputed:
        scaled.append([0.0 if stats[idx][1] == 0 else (value - stats[idx][0]) / stats[idx][1] for idx, value in enumerate(row)])
    metadata = {
        "row_count": len(rows),
        "scaler": f"{scaler}_stdlib_fallback",
        "missing_counts": missing_counts,
        "imputation": {name: float(imputations[idx]) for idx, name in enumerate(feature_names)},
    }
    return PreprocessedDataset(feature_names=feature_names, matrix=scaled, metadata=metadata)


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return float((ordered[middle - 1] + ordered[middle]) / 2)


def _standard_stats(matrix: list[list[float]]) -> list[tuple[float, float]]:
    if not matrix:
        return []
    stats: list[tuple[float, float]] = []
    for column in zip(*matrix, strict=True):
        mean = sum(column) / len(column)
        variance = sum((value - mean) ** 2 for value in column) / len(column)
        stats.append((mean, sqrt(variance)))
    return stats


def _robust_stats(matrix: list[list[float]]) -> list[tuple[float, float]]:
    if not matrix:
        return []
    stats: list[tuple[float, float]] = []
    for column in zip(*matrix, strict=True):
        ordered = sorted(column)
        center = _median(list(ordered))
        q1 = ordered[len(ordered) // 4]
        q3 = ordered[(len(ordered) * 3) // 4]
        stats.append((center, float(q3 - q1)))
    return stats
