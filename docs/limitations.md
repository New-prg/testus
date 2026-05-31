## Limitations

### Data source limitations

- Pilot-GPS is preserved as a provider boundary, but it is not the central object of research.
- Publicly documented live historical semantics from Pilot-GPS remain limited, so local datasets and demo flows are still important for reproducible experiments.

### Dataset limitations

- Imported datasets may be incomplete, irregular, or weakly labeled.
- Daily aggregation reduces noise, but also removes some temporal detail.
- Forecasting quality is constrained by short historical windows and a small feature space.

### Modeling limitations

- Rule-based `final_rating` is a baseline / weak label, not a learned truth.
- Unsupervised anomaly and clustering outputs are sensitive to fleet composition and scaling choices.
- Cluster profile names are interpretable heuristics, not strict semantic classes.
- Forecasting currently targets a derived operational score rather than a fully independent business target.

### Interpretation limitations

- Explanations are descriptive and comparative, not causal.
- A high anomaly score indicates deviation from the fleet pattern, not automatically unsafe or faulty behavior.
- Model outputs should be interpreted together with domain metrics such as fuel usage, idle ratio, braking, and overspeed.

### Platform scope limitations

- This repository is a minimal ML platform for thesis demonstration.
- It does not yet implement experiment tracking beyond database persistence, feature registry versioning, or production deployment of models.
