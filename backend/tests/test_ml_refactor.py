from collections.abc import Generator
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import deps
from app.db.models import User, Vehicle, VehicleMetricWindow, VehicleRatingWindow
from app.db.session import Base, get_db
from app.main import app
from app.services.ml.anomaly_service import AnomalyService
from app.services.ml.clustering_service import ClusteringService
from app.services.ml.dataset_builder import FeatureBuilder
from app.services.ml.forecasting_service import ForecastingService
from app.services.ml.preprocessing import preprocess_feature_rows
from app.services.telemetry.dataset_importer import DatasetImporter, DatasetProvider, LocalDatasetProvider


def build_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def build_static_session() -> tuple[Session, sessionmaker[Session]]:
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return factory(), factory


def seed_ml_windows(db: Session, vehicle_count: int = 6, days: int = 4) -> list[Vehicle]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    vehicles: list[Vehicle] = []
    for vehicle_index in range(vehicle_count):
        vehicle = Vehicle(name=f"Vehicle {vehicle_index}", pilot_agent_id=f"demo-agent-{vehicle_index:03d}", car_type="UNKNOWN")
        db.add(vehicle)
        db.flush()
        vehicles.append(vehicle)
        for day in range(days):
            period_start = start + timedelta(days=day)
            period_end = period_start + timedelta(days=1)
            factor = vehicle_index + day
            outlier = 10 if vehicle_index == vehicle_count - 1 and day == days - 1 else 0
            metric = VehicleMetricWindow(
                vehicle_id=vehicle.id,
                period_start=period_start,
                period_end=period_end,
                distance_km=100 + factor,
                fuel_consumed_liters=25 + factor + outlier,
                fuel_per_100km=24 + factor + outlier,
                coasting_ratio=None if day == 0 else 0.25 + vehicle_index * 0.01,
                optimal_rpm_ratio=0.55 - vehicle_index * 0.01,
                idle_ratio=0.12 + vehicle_index * 0.01,
                brakes_per_100km=3 + factor,
                high_speed_brakes_per_100km=1 + vehicle_index * 0.2,
                cruise_control_ratio=0.08 + day * 0.01,
                overspeed_ratio=0.03 + vehicle_index * 0.01,
                engine_work_seconds=7200 + factor,
                moving_seconds=6200 + factor,
                idle_seconds=900 + factor,
                raw_json={"test": True},
            )
            db.add(metric)
            db.flush()
            db.add(
                VehicleRatingWindow(
                    vehicle_id=vehicle.id,
                    metric_window_id=metric.id,
                    period_start=period_start,
                    period_end=period_end,
                    car_type="UNKNOWN",
                    final_rating=max(1.0, 9.0 - vehicle_index * 0.7 - day * 0.1 - outlier * 0.2),
                    fuel_score=8 - vehicle_index * 0.2,
                    coasting_score=7 - vehicle_index * 0.1,
                    optimal_rpm_score=7,
                    idle_score=6,
                    brakes_score=6 - vehicle_index * 0.1,
                    high_speed_brakes_score=6,
                    cruise_control_score=5 + day * 0.1,
                    overspeed_score=6 - vehicle_index * 0.2,
                    weights_json={},
                    warnings_json=["test warning"] if outlier else [],
                    positive_factors_json=[],
                    negative_factors_json=["high fuel"] if outlier else [],
                    raw_json={},
                )
            )
    db.commit()
    return vehicles


def test_feature_builder_excludes_final_rating_from_unsupervised_features() -> None:
    db = build_session()
    seed_ml_windows(db, vehicle_count=1, days=1)

    row = FeatureBuilder().build(db, limit=10)[0]

    assert "final_rating" not in row["features"]
    assert not any(feature.endswith("_score") for feature in row["features"])
    assert row["target_final_rating"] is not None


def test_local_dataset_provider_implements_dataset_provider_abstraction() -> None:
    assert issubclass(LocalDatasetProvider, DatasetProvider)


def test_preprocessing_imputes_missing_values_without_nan() -> None:
    rows = [
        {"features": {"fuel_per_100km": None, "idle_ratio": 0.1}},
        {"features": {"fuel_per_100km": 30.0, "idle_ratio": None}},
        {"features": {"fuel_per_100km": 35.0, "idle_ratio": 0.2}},
    ]

    prepared = preprocess_feature_rows(rows)

    assert prepared.feature_names == ["fuel_per_100km", "idle_ratio"]
    assert all(value == value for row in prepared.matrix for value in row)
    assert prepared.metadata["missing_counts"]["fuel_per_100km"] == 1


def test_anomaly_service_returns_explanations_for_detected_anomalies() -> None:
    db = build_session()
    seed_ml_windows(db)
    rows = FeatureBuilder().build(db, limit=100)

    result = AnomalyService().detect(rows)
    anomalies = [row for row in result["results"] if row["label"] == "anomaly"]

    model_names = {run["model_name"] for run in result["model_runs"]}
    assert {"robust_zscore_baseline"}.issubset(model_names)
    assert any(name in model_names for name in {"isolation_forest", "isolation_forest_fallback"})
    first_metrics = result["model_runs"][0]["metrics"]
    assert first_metrics["samples"] == len(rows)
    assert "count" in first_metrics
    assert "share" in first_metrics
    assert "score_summary" in first_metrics
    assert anomalies
    assert anomalies[0]["explanation"]["top_factors"]
    first_factor = anomalies[0]["explanation"]["top_factors"][0]
    assert "message_ru" in first_factor
    assert "fleet_median" in first_factor
    assert "fleet_mean" in first_factor
    assert "медиан" in anomalies[0]["explanation"]["summary_ru"]


def test_clustering_service_returns_labels_and_metrics() -> None:
    db = build_session()
    seed_ml_windows(db)
    rows = FeatureBuilder().build(db, limit=100)

    result = ClusteringService().cluster(rows)

    model_names = {run["model_name"] for run in result["model_runs"]}
    assert any(name in model_names for name in {"kmeans", "kmeans_fallback"})
    assert any(name in model_names for name in {"agglomerative_clustering", "agglomerative_fallback"})
    first_metrics = result["model_runs"][0]["metrics"]
    assert first_metrics["clusters"] == 3
    assert "davies_bouldin_score" in first_metrics
    assert "calinski_harabasz_score" in first_metrics
    assert all("cluster" in row and "cluster_id" in row for row in result["results"])
    assert all(row["profile_description_ru"] for row in result["results"])
    assert {profile["code"] for profile in result["profiles"].values()} & {"economical_usage", "high_idle", "aggressive_braking", "balanced_usage"}


def test_forecasting_service_returns_model_metrics() -> None:
    db = build_session()
    seed_ml_windows(db)
    rows = FeatureBuilder().build(db, limit=100)

    result = ForecastingService().forecast(rows)

    assert result["metrics"]["moving_average"]["samples"] > 0
    assert result["metrics"]["random_forest"]["MAE"] is not None
    assert {"moving_average_baseline", "random_forest_regressor"} == {run["model_name"] for run in result["model_runs"]}
    assert "RMSE" in result["metrics"]["moving_average"]
    assert "R2" in result["metrics"]["moving_average"]
    assert result["results"]
    assert all("moving_average_forecast" in row and "random_forest_forecast" in row for row in result["results"])


def test_dataset_importer_supports_repeated_rows_for_same_sensor() -> None:
    db = build_session()
    importer = DatasetImporter()

    result = importer.import_provider(
        db,
        _InMemoryDatasetProvider(
            [
                {
                    "timestamp": "2026-01-01T00:00:00Z",
                    "value": 100.0,
                    "sensor_name": "Полный пробег (CAN)",
                    "sensor_id": "distance-1",
                    "analytics_key": "distance",
                    "vehicle_id": "veh-1",
                    "name": "Vehicle 1",
                },
                {
                    "timestamp": "2026-01-01T01:00:00Z",
                    "value": 125.0,
                    "sensor_name": "Полный пробег (CAN)",
                    "sensor_id": "distance-1",
                    "analytics_key": "distance",
                    "vehicle_id": "veh-1",
                    "name": "Vehicle 1",
                },
            ]
        ),
    )

    assert result.readings == 2
    assert result.sensors >= 1


def test_ml_model_comparison_endpoint_after_recalculate() -> None:
    db, factory = build_static_session()
    [admin] = [User(email="admin@example.com", password_hash="hash", full_name="Admin", role="admin")]
    db.add(admin)
    seed_ml_windows(db)

    def override_db() -> Generator[Session, None, None]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[deps.get_current_user] = lambda: admin
    try:
        client = TestClient(app)
        recalculate_response = client.post("/api/ml/recalculate")
        comparison_response = client.get("/api/ml/model-comparison")
    finally:
        app.dependency_overrides.clear()

    assert recalculate_response.status_code == 200
    assert comparison_response.status_code == 200
    run_types = {row["run_type"] for row in comparison_response.json()["results"]}
    assert {"anomaly", "cluster", "forecast"}.issubset(run_types)
    model_names = {row["model_name"] for row in comparison_response.json()["results"]}
    assert "robust_zscore_baseline" in model_names
    assert "moving_average_baseline" in model_names
    assert "random_forest_regressor" in model_names
    assert any(name in model_names for name in {"kmeans", "kmeans_fallback"})
    assert any(name in model_names for name in {"agglomerative_clustering", "agglomerative_fallback"})
    first_row = comparison_response.json()["results"][0]
    assert {"run_type", "model", "metrics", "created_at", "metrics_summary"}.issubset(first_row)


def test_ml_recalculate_requires_admin_user() -> None:
    db, factory = build_static_session()
    user = User(email="user@example.com", password_hash="hash", full_name="User", role="user")
    db.add(user)
    seed_ml_windows(db)

    def override_db() -> Generator[Session, None, None]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[deps.get_current_user] = lambda: user
    try:
        client = TestClient(app)
        recalculate_response = client.post("/api/ml/recalculate")
    finally:
        app.dependency_overrides.clear()

    assert recalculate_response.status_code == 403


class _InMemoryDatasetProvider(DatasetProvider):
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def iter_rows(self) -> list[dict[str, object]]:
        return self.rows
