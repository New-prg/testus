## System architecture

This project is organized as a minimal ML platform for fleet telematics analytics.

Core pipeline:

1. **Ingestion**
   - `TelemetryProvider` defines the source boundary.
   - Pilot-GPS remains one provider and is not the central object of research.
   - `DatasetProvider` / local dataset import can load CSV, JSON, or JSONL into `Vehicle`, `VehicleSensor`, and `SensorReading`.

2. **Operational analytics layer**
   - Raw readings are aggregated into `VehicleMetricWindow`.
   - Rule-based ratings are stored in `VehicleRatingWindow`.
   - The rule-based rating is a **baseline / weak label**, not an ML model.

3. **ML feature layer**
   - `FeatureBuilder` constructs ML-ready feature rows from metric and rating windows.
   - For unsupervised tasks, `final_rating` is not included as a feature.
   - `final_rating` is used only as target, baseline, or interpretation aid.

4. **Preprocessing**
   - Missing values are imputed.
   - Numeric features are scaled through StandardScaler or RobustScaler.
   - ML services consume preprocessed matrices rather than raw feature dictionaries.

5. **ML experiments**
   - Anomaly detection: IsolationForest with a robust baseline comparator.
   - Clustering: KMeans and AgglomerativeClustering with profile descriptions.
   - Forecasting: moving-average baseline and RandomForestRegressor.
   - Run metadata is persisted in `MLModelRun`; per-vehicle outputs remain in `MLResult`.

6. **Presentation**
   - FastAPI exposes `/api/ml/*` endpoints.
   - React renders `/ml` as a thesis-oriented analytics screen with comparison, anomalies, clusters, forecasts, and explanations.

The design goal is not to replace the existing dashboard, vehicle, or report modules, but to add a minimal and explicit ML pipeline on top of the existing telemetry analytics stack.
