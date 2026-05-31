## ML methodology

The project demonstrates three ML tasks on telematics-derived features.

### 1. Anomaly detection

Goal: identify vehicles or periods whose behavior deviates from the fleet norm.

- Main method: `IsolationForest`
- Lightweight fallback: distance-based robust baseline
- Output: anomaly label, score, and Russian explanation based on deviation from fleet median and mean

Evaluation summary:

- anomaly count
- anomaly share
- score summary

### 2. Clustering

Goal: discover behavioral segments inside the fleet without manual labels.

- Main methods: `KMeans` and `AgglomerativeClustering`
- Profiles are translated into Russian operational descriptions such as:
  - economical usage
  - high idle
  - aggressive braking
  - balanced usage

Evaluation:

- `silhouette_score`
- `davies_bouldin_score`
- `calinski_harabasz_score`

### 3. Forecasting

Goal: estimate near-future behavior using recent historical windows.

- Baseline: moving average
- ML model: `RandomForestRegressor`
- UI presentation: one forecast row per vehicle/window with both baseline and model predictions
- Current supervised target: `final_rating` as a weak target / baseline-aligned target

Evaluation:

- `MAE`
- `RMSE`
- `R2`

### Preprocessing

All ML services apply preprocessing before model fitting:

- missing-value imputation
- numeric scaling via `StandardScaler` or `RobustScaler`

### Important interpretation rule

The ML component complements, but does not replace, operational analytics. Pilot-GPS is not the core scientific contribution; the contribution is the construction of an interpretable telematics ML pipeline.
