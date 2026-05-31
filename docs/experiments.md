## Experiments

### Execution flow

The experiment cycle is available through:

- `POST /api/ml/recalculate` (admin only)
- `GET /api/ml/model-comparison`
- `GET /api/ml/anomalies`
- `GET /api/ml/clusters`
- `GET /api/ml/forecasts`
- `GET /api/ml/explanations/{vehicle_id}`

### What is persisted

- `MLModelRun` stores run metadata, model name, feature names, metrics, status, and creation time.
- `MLResult` stores per-vehicle outputs for anomaly, cluster, and forecast views.

### Practical demo scenario

1. Start the stack with `docker compose up --build`.
2. Seed demo data or import a local dataset.
3. Open `/ml`.
4. Press **Пересчитать ML** as an administrator.
5. Review:
   - model comparison
   - anomalies with explanations
   - cluster profiles
   - forecasts

### Experimental interpretation

- Anomaly results show local deviations from fleet norms.
- Cluster results provide behavior-oriented fleet segmentation.
- Forecasting compares a simple operational baseline with a tree-based regressor.

This is intentionally a minimal platform for diploma demonstration rather than a production MLOps stack.
