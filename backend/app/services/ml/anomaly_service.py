from typing import Any
from importlib import import_module


class AnomalyService:
    def detect(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        np = import_module("numpy")
        isolation_forest_class = import_module("sklearn.ensemble").IsolationForest

        if len(rows) < 5:
            return {"message": "Недостаточно данных для обучения модели.", "results": []}
        feature_names = list(rows[0]["features"].keys())
        data = np.array([[float(row["features"][name]) for name in feature_names] for row in rows], dtype=float)
        model = isolation_forest_class(random_state=42, contamination=0.15)
        predictions = model.fit_predict(data)
        scores = model.decision_function(data)
        results = []
        for row, prediction, score in zip(rows, predictions, scores, strict=True):
            results.append(row | {"model_name": "isolation_forest", "score": float(score), "label": "anomaly" if prediction == -1 else "normal"})
        return {"message": "ok", "results": results}
