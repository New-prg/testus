## Feature engineering

`FeatureBuilder` creates ML rows from `VehicleMetricWindow` and aligned `VehicleRatingWindow` records.

### Minimal feature set

The required operational feature set is:

- `fuel_per_100km`
- `coasting_ratio`
- `optimal_rpm_ratio`
- `idle_ratio`
- `brakes_per_100km`
- `high_speed_brakes_per_100km`
- `cruise_control_ratio`
- `overspeed_ratio`
- `distance_km`
- `engine_work_seconds`
- `moving_seconds`

The current implementation also keeps a few adjacent operational features such as `fuel_consumed_liters` and `idle_seconds`, but the feature set above is the thesis baseline.

### Supervised vs unsupervised usage

- **Unsupervised tasks** (anomaly detection, clustering): `final_rating` is **not** used as a feature.
- **Supervised / interpretive usage**: `final_rating` may be used as:
  - `target_final_rating`
  - baseline reference
  - auxiliary interpretation signal

This separation is necessary because `final_rating` is derived from a rule-based scoring procedure and would otherwise leak manual scoring logic into unsupervised ML stages. The same rule applies to rule-based rating sub-scores: they are not used as anomaly/clustering inputs.

### Feature row structure

Each ML row contains:

- `vehicle_id`
- `period_start`
- `period_end`
- `features`
- `target_final_rating`
- `baseline.final_rating`
- `interpretation` with warnings / positive / negative factors

### Methodological note

Rule-based rating is not treated as ML. It is used as a baseline / weak label for comparison with ML outputs, not as proof of model quality.
