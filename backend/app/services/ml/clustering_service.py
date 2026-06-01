from importlib import import_module
from typing import Any

from app.services.ml.evaluation import clustering_metrics
from app.services.ml.preprocessing import preprocess_feature_rows


class ClusteringService:
    def cluster(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        if len(rows) < 3:
            return {"message": "Недостаточно данных для обучения модели.", "model_name": "clustering_comparison", "metrics": {"samples": len(rows)}, "model_runs": [], "results": []}
        prepared = preprocess_feature_rows(rows, scaler="standard")
        cluster_count = min(3, len(rows))
        model_runs = []
        combined_results = []
        combined_profiles: dict[str, dict[str, Any]] = {}
        for numeric_labels, model_name in self._label_runs(prepared.matrix, cluster_count):
            naming = self._name_clusters(rows, numeric_labels)
            profiles = self._cluster_profiles(rows, numeric_labels)
            results = [
                row
                | {
                    "model_name": model_name,
                    "cluster_id": label,
                    "cluster": naming[label],
                    "profile": profiles[label],
                    "profile_description_ru": profiles[label]["description_ru"],
                }
                for row, label in zip(rows, numeric_labels, strict=True)
            ]
            metrics = clustering_metrics(prepared.matrix, numeric_labels)
            model_runs.append({"model_name": model_name, "metrics": metrics, "profiles": {str(label): profile for label, profile in profiles.items()}, "results": results})
            combined_profiles.update({f"{model_name}:{label}": profile for label, profile in profiles.items()})
            combined_results.extend(results)
        return {
            "message": "ok",
            "model_name": "clustering_comparison",
            "feature_names": prepared.feature_names,
            "preprocessing": prepared.metadata,
            "metrics": {run["model_name"]: run["metrics"] for run in model_runs},
            "profiles": combined_profiles,
            "model_runs": model_runs,
            "results": combined_results,
        }

    @staticmethod
    def _label_runs(matrix: Any, cluster_count: int) -> list[tuple[list[int], str]]:
        runs = [ClusteringService._quantile_labels(matrix, cluster_count, "quantile_baseline")]
        try:
            kmeans_class = import_module("sklearn.cluster").KMeans
            model = kmeans_class(n_clusters=cluster_count, random_state=42, n_init=10)
            runs.insert(0, ([int(label) for label in model.fit_predict(matrix)], "kmeans"))
            agglomerative_class = import_module("sklearn.cluster").AgglomerativeClustering
            agglomerative = agglomerative_class(n_clusters=cluster_count)
            runs.append(([int(label) for label in agglomerative.fit_predict(matrix)], "agglomerative_clustering"))
        except ModuleNotFoundError:
            runs.insert(0, ClusteringService._quantile_labels(matrix, cluster_count, "kmeans_fallback"))
        return runs

    @staticmethod
    def _quantile_labels(matrix: Any, cluster_count: int, model_name: str) -> tuple[list[int], str]:
        scores = [(index, sum(row)) for index, row in enumerate(matrix)]
        ordered = sorted(scores, key=lambda item: item[1])
        labels = [0] * len(scores)
        for rank, (index, _) in enumerate(ordered):
            labels[index] = min(cluster_count - 1, int(rank * cluster_count / len(scores)))
        return labels, model_name

    @staticmethod
    def _name_clusters(rows: list[dict[str, Any]], labels: list[int]) -> dict[int, str]:
        scores: dict[int, list[float]] = {}
        for label, row in zip(labels, rows, strict=True):
            target = row.get("target_final_rating")
            if target is not None:
                scores.setdefault(label, []).append(float(target))
        if len(scores) == 3:
            ordered = sorted(scores, key=lambda key: sum(scores[key]) / len(scores[key]))
            return {ordered[0]: "inefficient", ordered[1]: "average", ordered[2]: "efficient"}
        return {label: f"cluster_{label}" for label in sorted(set(labels))}

    @staticmethod
    def _cluster_profiles(rows: list[dict[str, Any]], labels: list[int]) -> dict[int, dict[str, Any]]:
        fleet = ClusteringService._average_features(rows)
        grouped: dict[int, list[dict[str, Any]]] = {}
        for label, row in zip(labels, rows, strict=True):
            grouped.setdefault(label, []).append(row)
        profiles: dict[int, dict[str, Any]] = {}
        for label, cluster_rows in grouped.items():
            averages = ClusteringService._average_features(cluster_rows)
            profile_code, description = ClusteringService._profile_from_pattern(averages, fleet)
            profiles[label] = {
                "code": profile_code,
                "description_ru": description,
                "feature_averages": averages,
            }
        return profiles

    @staticmethod
    def _average_features(rows: list[dict[str, Any]]) -> dict[str, float]:
        sums: dict[str, float] = {}
        counts: dict[str, int] = {}
        for row in rows:
            for feature, value in row.get("features", {}).items():
                if value is None:
                    continue
                sums[feature] = sums.get(feature, 0.0) + float(value)
                counts[feature] = counts.get(feature, 0) + 1
        return {feature: sums[feature] / counts[feature] for feature in sums if counts.get(feature)}

    @staticmethod
    def _profile_from_pattern(averages: dict[str, float], fleet: dict[str, float]) -> tuple[str, str]:
        fuel = averages.get("fuel_per_100km", 0.0)
        idle = averages.get("idle_ratio", 0.0)
        brakes = averages.get("brakes_per_100km", 0.0) + averages.get("high_speed_brakes_per_100km", 0.0)
        overspeed = averages.get("overspeed_ratio", 0.0)
        coasting = averages.get("coasting_ratio", 0.0)
        if idle > fleet.get("idle_ratio", 0.0) * 1.15:
            return "high_idle", "Высокая доля простоя: автомобили чаще работают на холостом ходу относительно автопарка."
        if brakes > (fleet.get("brakes_per_100km", 0.0) + fleet.get("high_speed_brakes_per_100km", 0.0)) * 1.15 or overspeed > fleet.get("overspeed_ratio", 0.0) * 1.15:
            return "aggressive_braking", "Агрессивное вождение: повышены торможения, резкие торможения или превышения скорости."
        if fuel <= fleet.get("fuel_per_100km", fuel) and coasting >= fleet.get("coasting_ratio", coasting):
            return "economical_usage", "Экономичная эксплуатация: расход не выше среднего по автопарку и больше движения накатом."
        return "balanced_usage", "Сбалансированный профиль: показатели близки к средним значениям автопарка."
