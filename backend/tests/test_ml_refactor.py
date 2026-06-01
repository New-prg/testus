from collections.abc import Generator, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

import alembic.command as alembic_command
import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import deps
from app.core.config import get_settings
from app.db.models import AnalyticsSensorLink, MLModelRun, MLResult, SensorReading, User, Vehicle, VehicleMetricWindow, VehicleRatingWindow, VehicleSensor
from app.db.seed import DemoDayLimitedProvider, seed_demo_data
from app.db.session import Base, get_db
from app.main import app
from app.services.ml.anomaly_service import AnomalyService
from app.services.ml.clustering_service import ClusteringService
from app.services.ml.dataset_builder import FeatureBuilder
from app.services.ml.forecasting_service import ForecastingService
from app.services.pilot_gps.client import validate_pilot_server_address
from app.services.pilot_gps.sync_service import PilotSyncService
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


def build_no_autoflush_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()


def make_user(login: str, role: str = "admin") -> User:
    return User(email=login, login=login, password_hash="hash", full_name=login, role=role)


def seed_ml_windows(db: Session, owner: User, vehicle_count: int = 6, days: int = 4) -> list[Vehicle]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    vehicles: list[Vehicle] = []
    for vehicle_index in range(vehicle_count):
        vehicle = Vehicle(user_id=owner.id, name=f"Vehicle {vehicle_index}", pilot_agent_id=f"demo-agent-{vehicle_index:03d}", car_type="UNKNOWN")
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
    owner = User(email="owner@example.com", login="owner@example.com", password_hash="hash", full_name="Owner", role="admin")
    db.add(owner)
    db.commit()
    seed_ml_windows(db, owner, vehicle_count=1, days=1)

    row = FeatureBuilder().build(db, limit=10, user_id=owner.id)[0]

    assert "final_rating" not in row["features"]
    assert not any(feature.endswith("_score") for feature in row["features"])
    assert row["target_final_rating"] is not None


def test_local_dataset_provider_implements_dataset_provider_abstraction() -> None:
    assert issubclass(LocalDatasetProvider, DatasetProvider)


def test_dataset_provider_alias_matches_telemetry_provider() -> None:
    from app.services.telemetry.provider import TelemetryProvider

    assert DatasetProvider is TelemetryProvider
    assert issubclass(LocalDatasetProvider, TelemetryProvider)


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
    owner = make_user("anomaly@example.com")
    db.add(owner)
    db.commit()
    seed_ml_windows(db, owner)
    rows = FeatureBuilder().build(db, limit=100, user_id=owner.id)

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
    owner = make_user("cluster@example.com")
    db.add(owner)
    db.commit()
    seed_ml_windows(db, owner)
    rows = FeatureBuilder().build(db, limit=100, user_id=owner.id)

    result = ClusteringService().cluster(rows)

    model_names = {run["model_name"] for run in result["model_runs"]}
    assert any(name in model_names for name in {"kmeans", "kmeans_fallback"})
    assert "quantile_baseline" in model_names
    if "agglomerative_clustering" in model_names:
        assert "agglomerative_fallback" not in model_names
    first_metrics = result["model_runs"][0]["metrics"]
    assert first_metrics["clusters"] == 3
    assert "davies_bouldin_score" in first_metrics
    assert "calinski_harabasz_score" in first_metrics
    assert all("cluster" in row and "cluster_id" in row for row in result["results"])
    assert all(row["profile_description_ru"] for row in result["results"])
    assert {profile["code"] for profile in result["profiles"].values()} & {"economical_usage", "high_idle", "aggressive_braking", "balanced_usage"}


def test_forecasting_service_returns_model_metrics() -> None:
    db = build_session()
    owner = make_user("forecast@example.com")
    db.add(owner)
    db.commit()
    seed_ml_windows(db, owner)
    rows = FeatureBuilder().build(db, limit=100, user_id=owner.id)

    result = ForecastingService().forecast(rows)

    assert result["metrics"]["moving_average"]["samples"] > 0
    assert result["metrics"]["evaluation"] == "time_based_holdout"
    assert result["metrics"]["test_samples"] == len(result["results"])
    assert result["metrics"]["test_samples"] < len(rows)
    assert result["metrics"]["random_forest"]["MAE"] is not None
    assert {"moving_average_baseline", "random_forest_regressor"} == {run["model_name"] for run in result["model_runs"]}
    assert "RMSE" in result["metrics"]["moving_average"]
    assert "R2" in result["metrics"]["moving_average"]
    assert result["results"]
    assert all("moving_average_forecast" in row and "random_forest_forecast" in row for row in result["results"])


def test_forecasting_service_skips_when_holdout_is_not_possible() -> None:
    db = build_session()
    owner = make_user("holdout@example.com")
    db.add(owner)
    db.commit()
    seed_ml_windows(db, owner, vehicle_count=3, days=1)
    rows = FeatureBuilder().build(db, limit=100, user_id=owner.id)

    result = ForecastingService().forecast(rows)

    assert result["message"] != "ok"
    assert result["metrics"]["evaluation"] == "time_based_holdout"
    assert result["metrics"]["test_samples"] == 0
    assert result["model_runs"][0]["metrics"]["MAE"] is None


def test_dataset_importer_supports_repeated_rows_for_same_sensor() -> None:
    db = build_session()
    importer = DatasetImporter()
    owner = make_user("dataset-repeat@example.com")
    db.add(owner)
    db.commit()

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
        owner,
    )

    assert result.readings == 2
    assert result.sensors >= 1


def test_dataset_importer_deduplicates_same_timestamp_rows_without_autoflush() -> None:
    db = build_no_autoflush_session()
    importer = DatasetImporter()
    owner = make_user("dataset-dedupe@example.com")
    db.add(owner)
    db.commit()

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
                    "timestamp": "2026-01-01T00:00:00Z",
                    "value": 100.0,
                    "sensor_name": "Полный пробег (CAN)",
                    "sensor_id": "distance-1",
                    "analytics_key": "distance",
                    "vehicle_id": "veh-1",
                    "name": "Vehicle 1",
                },
            ]
        ),
        owner,
    )

    assert result.readings == 1
    assert db.query(SensorReading).count() == 1
    assert result.skipped_rows == 0


def test_dataset_importer_skips_existing_readings_on_reimport() -> None:
    db = build_no_autoflush_session()
    importer = DatasetImporter()
    owner = make_user("dataset-reimport@example.com")
    db.add(owner)
    db.commit()
    rows = [
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

    first_result = importer.import_provider(db, _InMemoryDatasetProvider(rows), owner)
    second_result = importer.import_provider(db, _InMemoryDatasetProvider(rows), owner)

    assert first_result.readings == 2
    assert second_result.readings == 0
    assert db.query(SensorReading).count() == 2
    assert db.query(Vehicle).count() == 1
    assert db.query(VehicleSensor).count() == 1
    assert db.query(AnalyticsSensorLink).count() == 1


def test_local_dataset_provider_streams_rows_with_limit(tmp_path: Path) -> None:
    dataset_path = tmp_path / "rows.csv"
    dataset_path.write_text(
        "timestamp,value,sensor_name,sensor_id,vehicle_id,name\n"
        "2026-01-01T00:00:00Z,1,Speed,s1,v1,Vehicle 1\n"
        "2026-01-01T01:00:00Z,2,Speed,s1,v1,Vehicle 1\n",
        encoding="utf-8",
    )

    provider = LocalDatasetProvider(dataset_path, row_limit=1)

    with pytest.raises(ValueError, match="Dataset contains too many rows"):
        list(provider.iter_rows())


def test_dataset_importer_accepts_reduced_telematics_schema() -> None:
    db = build_session()
    importer = DatasetImporter()
    owner = make_user("dataset-schema@example.com")
    db.add(owner)
    db.commit()

    result = importer.import_provider(
        db,
        _InMemoryDatasetProvider(
            [
                {
                    "vehicle_key": "10039",
                    "vehicle_agentid": "10039",
                    "imei": "862059069276700",
                    "vehiclenumber": "29-П Р762СР716",
                    "vin": "XTC549015R2601687",
                    "timestamp": "2026-05-24T03:11:20+00:00",
                    "canonical_feature": "speed",
                    "value": 45.0,
                    "local_sensor_id": "72427",
                    "sensor_name": "Скорость (тахограф)",
                    "speed_from_point": 45.0,
                }
            ]
        ),
        owner,
    )

    vehicle = db.query(Vehicle).one()
    sensor = vehicle.sensors[0]
    reading = vehicle.readings[0]

    assert result.vehicles == 1
    assert vehicle.pilot_agent_id == "10039"
    assert sensor.pilot_sensor_id == "72427"
    assert reading.speed == 45.0


def test_seed_demo_data_prefers_configured_dataset(monkeypatch, tmp_path: Path) -> None:
    db = build_session()
    dataset_path = tmp_path / "demo.csv"
    dataset_path.write_text(
        "vehicle_key,vehicle_agentid,imei,vehiclenumber,vin,timestamp,canonical_feature,value,local_sensor_id,sensor_name,speed_from_point\n"
        "10039,10039,862059069276700,29-П Р762СР716,XTC549015R2601687,2026-05-24T03:11:20+00:00,speed,45.0,72427,Скорость (тахограф),45.0\n",
        encoding="utf-8",
    )
    sensor_profile_path = tmp_path / "sensor_profile_canonical.json"
    sensor_profile_path.write_text("[]", encoding="utf-8")

    monkeypatch.setenv("DEMO_DATASET_PATH", str(dataset_path))
    monkeypatch.setenv("DEMO_SENSOR_PROFILE_PATH", str(sensor_profile_path))
    monkeypatch.setenv("DEMO_DATASET_ROW_LIMIT", "10")
    get_settings.cache_clear()

    try:
        result = seed_demo_data(db)
    finally:
        get_settings.cache_clear()

    assert result["source"] == "local_dataset"
    assert result["dataset_path"] == str(dataset_path)
    assert result["sensor_profile_path"] == str(sensor_profile_path)
    assert result["dataset_row_limit"] == 10
    assert result["vehicles"] == 1
    assert db.query(User).filter(User.email == "admin@example.com").one()


def test_demo_day_limited_provider_keeps_all_vehicles_for_first_day_only() -> None:
    provider = DemoDayLimitedProvider(
        _InMemoryDatasetProvider(
            [
                {
                    "vehicle_key": "veh-1",
                    "vehicle_agentid": "veh-1",
                    "timestamp": "2026-05-24T03:11:20+00:00",
                    "canonical_feature": "speed",
                    "value": 45.0,
                    "local_sensor_id": "72427",
                    "sensor_name": "Скорость (тахограф)",
                    "name": "Vehicle 1",
                },
                {
                    "vehicle_key": "veh-2",
                    "vehicle_agentid": "veh-2",
                    "timestamp": "2026-05-24T05:11:20+00:00",
                    "canonical_feature": "speed",
                    "value": 35.0,
                    "local_sensor_id": "72428",
                    "sensor_name": "Скорость (тахограф)",
                    "name": "Vehicle 2",
                },
                {
                    "vehicle_key": "veh-1",
                    "vehicle_agentid": "veh-1",
                    "timestamp": "2026-05-25T03:11:20+00:00",
                    "canonical_feature": "speed",
                    "value": 25.0,
                    "local_sensor_id": "72427",
                    "sensor_name": "Скорость (тахограф)",
                    "name": "Vehicle 1",
                },
            ]
        ),
        max_days=1,
    )

    rows = list(provider.iter_rows())

    assert len(rows) == 2
    assert {row["vehicle_key"] for row in rows} == {"veh-1", "veh-2"}
    assert all(str(row["timestamp"]).startswith("2026-05-24") for row in rows)


def test_seed_demo_data_resets_existing_demo_statistics_for_dataset(monkeypatch, tmp_path: Path) -> None:
    db = build_session()
    demo_admin = make_user("admin@example.com")
    demo_admin.is_demo = True
    db.add(demo_admin)
    db.commit()
    vehicle = Vehicle(user_id=demo_admin.id, name="Old demo", pilot_agent_id="old-demo", car_type="UNKNOWN")
    db.add(vehicle)
    db.flush()
    db.add(MLResult(result_type="forecast", vehicle_id=vehicle.id, payload={"vehicle_id": vehicle.id}))
    db.add(MLModelRun(run_type="forecast", model_name="old", status="success", row_count=1, feature_names=[], metrics={}, parameters={}))
    db.commit()

    dataset_path = tmp_path / "demo.csv"
    dataset_path.write_text(
        "vehicle_key,vehicle_agentid,imei,vehiclenumber,vin,timestamp,canonical_feature,value,local_sensor_id,sensor_name,speed_from_point\n"
        "10040,10040,862059069276701,30-П Р762СР717,XTC549015R2601688,2026-05-24T03:11:20+00:00,speed,25.0,72428,Скорость (тахограф),25.0\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("DEMO_DATASET_PATH", str(dataset_path))
    monkeypatch.setenv("DEMO_DATASET_ROW_LIMIT", "10")
    monkeypatch.delenv("DEMO_SENSOR_PROFILE_PATH", raising=False)
    get_settings.cache_clear()

    try:
        seed_demo_data(db)
    finally:
        get_settings.cache_clear()

    assert {row.pilot_agent_id for row in db.query(Vehicle).all()} == {"10040"}
    assert db.query(MLResult).count() == 0
    assert db.query(MLModelRun).count() == 0


def test_seed_demo_data_falls_back_when_configured_dataset_is_missing(monkeypatch, tmp_path: Path) -> None:
    db = build_session()
    missing_dataset_path = tmp_path / "missing-demo.csv"

    monkeypatch.setenv("DEMO_DATASET_PATH", str(missing_dataset_path))
    get_settings.cache_clear()

    try:
        result = seed_demo_data(db)
    finally:
        get_settings.cache_clear()

    assert result["source"] == "demo_pilot_provider"
    assert result["vehicles"]["synced"] == 12
    assert result["readings"]["inserted"] > 0


def test_demo_dataset_row_limit_defaults_to_unlimited(monkeypatch) -> None:
    monkeypatch.delenv("DEMO_DATASET_ROW_LIMIT", raising=False)
    get_settings.cache_clear()

    try:
        assert get_settings().demo_dataset_row_limit == -1
    finally:
        get_settings.cache_clear()


def test_validate_pilot_server_address_rejects_private_or_non_https_hosts() -> None:
    for value in (
        "http://pilot-gps.example",
        "https://localhost",
        "https://127.0.0.1",
        "https://192.168.1.10",
        "https://pilot-gps.example/api",
        "https://user:pass@pilot-gps.example",
    ):
        with pytest.raises(ValueError):
            validate_pilot_server_address(value)

    assert validate_pilot_server_address("https://pilot-gps.example") == "https://pilot-gps.example"


def test_next_sync_uses_registration_anchor() -> None:
    registered_at = datetime(2026, 1, 1, 10, 15, tzinfo=UTC)
    completed_at = datetime(2026, 1, 1, 13, 10, tzinfo=UTC)
    user = User(email="anchor@example.com", login="anchor@example.com", password_hash="hash", sync_started_at=registered_at)

    next_sync = PilotSyncService._next_sync_from_anchor(user, completed_at)

    assert next_sync == datetime(2026, 1, 1, 13, 15, tzinfo=UTC)


def test_safe_sync_error_redacts_sensitive_tokens() -> None:
    error = RuntimeError("Authorization failed for Bearer secret-token")

    assert PilotSyncService._safe_sync_error(error) == "Pilot-GPS sync failed"


def test_ml_model_comparison_endpoint_after_recalculate() -> None:
    db, factory = build_static_session()
    [admin] = [make_user("admin@example.com")]
    db.add(admin)
    db.commit()
    seed_ml_windows(db, admin)

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
    assert "quantile_baseline" in model_names
    if "agglomerative_clustering" in model_names:
        assert "agglomerative_fallback" not in model_names
    first_row = comparison_response.json()["results"][0]
    assert {"run_type", "model", "metrics", "created_at", "metrics_summary"}.issubset(first_row)


def test_ml_recalculate_persists_result_periods() -> None:
    db, factory = build_static_session()
    admin = make_user("admin-periods@example.com")
    db.add(admin)
    db.commit()
    seed_ml_windows(db, admin)

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
        response = client.post("/api/ml/recalculate")
        persisted = factory().scalars(select(MLResult).where(MLResult.result_type.in_(["anomaly", "cluster", "forecast"]))).all()
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert persisted
    assert all(row.period_start is not None and row.period_end is not None for row in persisted)


def test_alembic_upgrade_creates_ml_model_runs_table(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "alembic-test.sqlite3"
    database_url = f"sqlite+pysqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))

    try:
        alembic_command.upgrade(config, "head")
        table_names = set(inspect(create_engine(database_url)).get_table_names())
    finally:
        get_settings.cache_clear()

    assert "ml_model_runs" in table_names


def test_alembic_upgrade_from_legacy_0002_revision_succeeds(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "alembic-legacy.sqlite3"
    database_url = f"sqlite+pysqlite:///{database_path}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))

    try:
        alembic_command.upgrade(config, "0001_initial")
        engine = create_engine(database_url)
        with engine.begin() as connection:
            connection.exec_driver_sql("UPDATE alembic_version SET version_num = '0002_ml_model_runs'")
        alembic_command.upgrade(config, "head")
        with engine.connect() as connection:
            current_revision = connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()
    finally:
        get_settings.cache_clear()

    assert current_revision == "0002_account_scoped_pilot_sync"


def test_ml_recalculate_requires_admin_user() -> None:
    db, factory = build_static_session()
    user = make_user("user@example.com", role="user")
    db.add(user)
    db.commit()
    seed_ml_windows(db, user)

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
    def __init__(self, rows: Sequence[Mapping[str, object]]) -> None:
        self.rows = [dict(row) for row in rows]

    def iter_rows(self) -> list[dict[str, object]]:
        return self.rows
