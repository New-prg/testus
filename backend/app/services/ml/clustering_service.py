from typing import Any
from importlib import import_module


class ClusteringService:
    def cluster(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        np = import_module("numpy")
        kmeans_class = import_module("sklearn.cluster").KMeans

        if len(rows) < 3:
            return {"message": "Недостаточно данных для обучения модели.", "results": []}
        feature_names = list(rows[0]["features"].keys())
        data = np.array([[float(row["features"][name]) for name in feature_names] for row in rows], dtype=float)
        model = kmeans_class(n_clusters=3, random_state=42, n_init=10)
        labels = model.fit_predict(data)
        cluster_scores: dict[int, list[float]] = {}
        for label, row in zip(labels, rows, strict=True):
            cluster_scores.setdefault(int(label), []).append(float(row["features"].get("final_rating", 0.0)))
        ordered = sorted(cluster_scores, key=lambda key: sum(cluster_scores[key]) / len(cluster_scores[key]))
        naming = {ordered[0]: "inefficient", ordered[1]: "average", ordered[2]: "efficient"}
        results = [row | {"cluster": naming[int(label)]} for row, label in zip(rows, labels, strict=True)]
        return {"message": "ok", "results": results}
