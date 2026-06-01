from collections.abc import Generator
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import deps
from app.db.models import MLResult, SensorReading, User, Vehicle, VehicleMetricWindow, VehicleRatingWindow
from app.db.session import Base, get_db
from app.main import app


def build_static_session() -> tuple[Session, sessionmaker[Session]]:
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    return factory(), factory


def make_user(login: str, role: str = "admin") -> User:
    return User(email=login, login=login, password_hash="hash", full_name=login, role=role)


def seed_dashboard_report_data(db: Session, owner: User) -> dict[str, str]:
    now = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    current_start = now - timedelta(days=1)
    previous_start = now - timedelta(days=8)
    current_end = current_start + timedelta(days=1)
    previous_end = previous_start + timedelta(days=1)

    vehicle_1 = Vehicle(user_id=owner.id, name="Vehicle 1", plate_number="A001AA", pilot_agent_id="veh-001", car_type="UNKNOWN")
    vehicle_2 = Vehicle(user_id=owner.id, name="Vehicle 2", plate_number="A002AA", pilot_agent_id="veh-002", car_type="UNKNOWN")
    db.add_all([vehicle_1, vehicle_2])
    db.flush()

    metric_rows = [
        VehicleMetricWindow(
            vehicle_id=vehicle_1.id,
            period_start=current_start,
            period_end=current_end,
            distance_km=100.0,
            fuel_consumed_liters=20.0,
            fuel_per_100km=20.0,
            coasting_ratio=0.30,
            optimal_rpm_ratio=0.60,
            idle_ratio=0.20,
            brakes_per_100km=2.0,
            high_speed_brakes_per_100km=1.0,
            cruise_control_ratio=0.10,
            overspeed_ratio=0.05,
            engine_work_seconds=1000.0,
            moving_seconds=800.0,
            idle_seconds=200.0,
            raw_json={},
        ),
        VehicleMetricWindow(
            vehicle_id=vehicle_2.id,
            period_start=current_start,
            period_end=current_end,
            distance_km=10.0,
            fuel_consumed_liters=5.0,
            fuel_per_100km=50.0,
            coasting_ratio=0.10,
            optimal_rpm_ratio=0.40,
            idle_ratio=0.50,
            brakes_per_100km=8.0,
            high_speed_brakes_per_100km=4.0,
            cruise_control_ratio=0.20,
            overspeed_ratio=0.15,
            engine_work_seconds=100.0,
            moving_seconds=50.0,
            idle_seconds=50.0,
            raw_json={},
        ),
        VehicleMetricWindow(
            vehicle_id=vehicle_1.id,
            period_start=previous_start,
            period_end=previous_end,
            distance_km=90.0,
            fuel_consumed_liters=18.0,
            fuel_per_100km=20.0,
            coasting_ratio=0.28,
            optimal_rpm_ratio=0.58,
            idle_ratio=0.22,
            brakes_per_100km=2.5,
            high_speed_brakes_per_100km=1.5,
            cruise_control_ratio=0.11,
            overspeed_ratio=0.06,
            engine_work_seconds=900.0,
            moving_seconds=700.0,
            idle_seconds=198.0,
            raw_json={},
        ),
    ]
    db.add_all(metric_rows)
    db.flush()

    rating_rows = [
        VehicleRatingWindow(
            vehicle_id=vehicle_1.id,
            metric_window_id=metric_rows[0].id,
            period_start=current_start,
            period_end=current_end,
            car_type="UNKNOWN",
            final_rating=8.0,
            fuel_score=9.0,
            coasting_score=8.0,
            optimal_rpm_score=7.0,
            idle_score=6.0,
            brakes_score=7.0,
            high_speed_brakes_score=8.0,
            cruise_control_score=9.0,
            overspeed_score=8.0,
            weights_json={},
            warnings_json=[],
            positive_factors_json=[],
            negative_factors_json=[],
            raw_json={},
        ),
        VehicleRatingWindow(
            vehicle_id=vehicle_2.id,
            metric_window_id=metric_rows[1].id,
            period_start=current_start,
            period_end=current_end,
            car_type="UNKNOWN",
            final_rating=4.0,
            fuel_score=3.0,
            coasting_score=4.0,
            optimal_rpm_score=5.0,
            idle_score=3.0,
            brakes_score=4.0,
            high_speed_brakes_score=2.0,
            cruise_control_score=4.0,
            overspeed_score=3.0,
            weights_json={},
            warnings_json=["needs attention"],
            positive_factors_json=[],
            negative_factors_json=["high fuel"],
            raw_json={},
        ),
        VehicleRatingWindow(
            vehicle_id=vehicle_1.id,
            metric_window_id=metric_rows[2].id,
            period_start=previous_start,
            period_end=previous_end,
            car_type="UNKNOWN",
            final_rating=7.0,
            fuel_score=8.0,
            coasting_score=7.0,
            optimal_rpm_score=7.0,
            idle_score=6.0,
            brakes_score=6.0,
            high_speed_brakes_score=7.0,
            cruise_control_score=8.0,
            overspeed_score=7.0,
            weights_json={},
            warnings_json=[],
            positive_factors_json=[],
            negative_factors_json=[],
            raw_json={},
        ),
    ]
    db.add_all(rating_rows)

    db.add_all(
        [
            SensorReading(vehicle_id=vehicle_1.id, sensor_id="sensor-1", timestamp=current_end, value=1.0, speed=0.0, raw_json={}),
            SensorReading(vehicle_id=vehicle_2.id, sensor_id="sensor-2", timestamp=current_end, value=1.0, speed=0.0, raw_json={}),
        ]
    )

    db.add_all(
        [
            MLResult(result_type="anomaly", vehicle_id=vehicle_1.id, period_start=current_start, period_end=current_end, payload={"vehicle_id": vehicle_1.id}),
            MLResult(result_type="anomaly", vehicle_id=vehicle_1.id, period_start=current_start, period_end=current_end, payload={"vehicle_id": vehicle_1.id, "duplicate": True}),
            MLResult(result_type="anomaly", vehicle_id=vehicle_2.id, period_start=previous_start, period_end=previous_end, payload={"vehicle_id": vehicle_2.id}),
        ]
    )
    db.commit()
    return {"vehicle_1_id": vehicle_1.id, "vehicle_2_id": vehicle_2.id, "future_from": (now + timedelta(days=10)).date().isoformat(), "future_to": (now + timedelta(days=11)).date().isoformat()}


def build_client(factory: sessionmaker[Session], user: User) -> TestClient:
    def override_db() -> Generator[Session, None, None]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[deps.get_current_user] = lambda: user
    return TestClient(app)


def test_dashboard_summary_uses_weighted_aggregates_and_period_scoped_anomalies() -> None:
    db, factory = build_static_session()
    admin = make_user("dashboard@example.com")
    db.add(admin)
    db.commit()
    seed_dashboard_report_data(db, admin)

    client = build_client(factory, admin)
    try:
        response = client.get("/api/dashboard/summary", params={"period": "week"})
    finally:
        app.dependency_overrides.clear()

    payload = response.json()
    assert response.status_code == 200
    assert payload["fuel_per_100km"] == 22.73
    assert payload["idle_ratio"] == 0.2273
    assert payload["anomaly_vehicles_count"] == 1
    assert payload["metric_scores"]["cruise_control_ratio"] == 6.5
    assert payload["metric_scores"]["high_speed_brakes_per_100km"] == 5.0
    assert payload["metric_scores"]["analytics_readiness_percent"] == 0.0


def test_dashboard_timeseries_and_problem_vehicles_are_period_correct() -> None:
    db, factory = build_static_session()
    admin = make_user("dashboard-timeseries@example.com")
    db.add(admin)
    db.commit()
    data = seed_dashboard_report_data(db, admin)

    client = build_client(factory, admin)
    try:
        timeseries_response = client.get("/api/dashboard/timeseries", params={"period": "week"})
        problem_response = client.get("/api/dashboard/problem-vehicles", params={"period": "week"})
    finally:
        app.dependency_overrides.clear()

    timeseries = timeseries_response.json()
    problem = problem_response.json()

    assert timeseries_response.status_code == 200
    assert len(timeseries) == 1
    assert timeseries[0]["rating"] == 6.0
    assert timeseries[0]["fuel_per_100km"] == 22.7273
    assert timeseries[0]["brakes_per_100km"] == 2.5455
    assert timeseries[0]["analytics_readiness_percent"] == 0.0
    assert problem_response.status_code == 200
    assert problem["worst"][0]["vehicle_id"] == data["vehicle_2_id"]
    assert problem["worst"][0]["anomaly_flag"] is False
    assert problem["best"][0]["vehicle_id"] == data["vehicle_1_id"]
    assert problem["best"][0]["anomaly_flag"] is True


def test_fleet_report_matches_weighted_summary_and_counts_anomalies() -> None:
    db, factory = build_static_session()
    admin = make_user("report@example.com")
    db.add(admin)
    db.commit()
    seed_dashboard_report_data(db, admin)

    client = build_client(factory, admin)
    try:
        response = client.get("/api/reports/fleet", params={"period": "week"})
        csv_response = client.get("/api/reports/export/csv", params={"period": "week"})
    finally:
        app.dependency_overrides.clear()

    payload = response.json()

    assert response.status_code == 200
    assert payload["summary"]["fuel_per_100km"] == 22.73
    assert payload["summary"]["idle_ratio"] == 0.2273
    assert payload["summary"]["brakes_per_100km"] == 2.55
    assert payload["summary"]["anomaly_vehicles_count"] == 1
    assert payload["conclusions"][0]["title"] == "Рейтинг автопарка"
    assert "A001AA" in csv_response.text
    assert "A002AA" in csv_response.text


def test_reports_return_no_data_conclusion_for_empty_period() -> None:
    db, factory = build_static_session()
    admin = make_user("report-empty@example.com")
    db.add(admin)
    db.commit()
    data = seed_dashboard_report_data(db, admin)

    client = build_client(factory, admin)
    try:
        fleet_response = client.get("/api/reports/fleet", params={"date_from": data["future_from"], "date_to": data["future_to"]})
        vehicle_response = client.get(f"/api/reports/vehicle/{data['vehicle_1_id']}", params={"date_from": data["future_from"], "date_to": data["future_to"]})
    finally:
        app.dependency_overrides.clear()

    assert fleet_response.status_code == 200
    assert fleet_response.json()["conclusions"][0]["title"] == "Нет данных"
    assert vehicle_response.status_code == 200
    assert vehicle_response.json()["conclusions"][0]["title"] == "Нет данных"


def test_dashboard_and_reports_include_current_day_windows() -> None:
    db, factory = build_static_session()
    admin = make_user("dashboard-current-day@example.com")
    db.add(admin)
    db.commit()

    now = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    current_start = now
    current_end = now + timedelta(days=1)

    vehicle = Vehicle(user_id=admin.id, name="Today Vehicle", plate_number="TODAY-001", pilot_agent_id="today-001", car_type="UNKNOWN")
    db.add(vehicle)
    db.flush()
    metric = VehicleMetricWindow(
        vehicle_id=vehicle.id,
        period_start=current_start,
        period_end=current_end,
        distance_km=120.0,
        fuel_consumed_liters=24.0,
        fuel_per_100km=20.0,
        coasting_ratio=0.22,
        optimal_rpm_ratio=0.55,
        idle_ratio=0.18,
        brakes_per_100km=2.5,
        high_speed_brakes_per_100km=1.0,
        cruise_control_ratio=0.14,
        overspeed_ratio=0.03,
        engine_work_seconds=1000.0,
        moving_seconds=820.0,
        idle_seconds=180.0,
        raw_json={"reading_counts": {"distance": 2}},
    )
    db.add(metric)
    db.flush()
    db.add(
        VehicleRatingWindow(
            vehicle_id=vehicle.id,
            metric_window_id=metric.id,
            period_start=current_start,
            period_end=current_end,
            car_type="UNKNOWN",
            final_rating=8.2,
            fuel_score=8.0,
            coasting_score=7.0,
            optimal_rpm_score=8.0,
            idle_score=8.0,
            brakes_score=8.0,
            high_speed_brakes_score=8.0,
            cruise_control_score=7.0,
            overspeed_score=8.0,
            weights_json={},
            warnings_json=[],
            positive_factors_json=[],
            negative_factors_json=[],
            raw_json={},
        )
    )
    db.commit()

    client = build_client(factory, admin)
    try:
        summary_response = client.get("/api/dashboard/summary", params={"period": "week"})
        timeseries_response = client.get("/api/dashboard/timeseries", params={"period": "week"})
        report_response = client.get("/api/reports/fleet", params={"period": "week"})
    finally:
        app.dependency_overrides.clear()

    assert summary_response.status_code == 200
    assert summary_response.json()["vehicles_count"] == 1
    assert summary_response.json()["fleet_rating"] == 8.2
    assert timeseries_response.status_code == 200
    assert len(timeseries_response.json()) == 1
    assert timeseries_response.json()[0]["fuel_per_100km"] == 20.0
    assert report_response.status_code == 200
    assert report_response.json()["summary"]["vehicles_count"] == 1


def test_dashboard_and_reports_anchor_default_week_to_latest_available_data() -> None:
    db, factory = build_static_session()
    admin = make_user("dashboard-latest-anchor@example.com")
    db.add(admin)
    db.commit()

    latest_period_start = datetime(2026, 5, 24, tzinfo=UTC)
    latest_period_end = latest_period_start + timedelta(days=1)
    vehicle = Vehicle(user_id=admin.id, name="Anchored Vehicle", plate_number="ANCHOR-001", pilot_agent_id="anchor-001", car_type="UNKNOWN")
    db.add(vehicle)
    db.flush()
    metric = VehicleMetricWindow(
        vehicle_id=vehicle.id,
        period_start=latest_period_start,
        period_end=latest_period_end,
        distance_km=90.0,
        fuel_consumed_liters=18.0,
        fuel_per_100km=20.0,
        coasting_ratio=0.25,
        optimal_rpm_ratio=0.55,
        idle_ratio=0.15,
        brakes_per_100km=2.0,
        high_speed_brakes_per_100km=1.0,
        cruise_control_ratio=0.1,
        overspeed_ratio=0.03,
        engine_work_seconds=1000.0,
        moving_seconds=850.0,
        idle_seconds=150.0,
        raw_json={"reading_counts": {"distance": 2}},
    )
    db.add(metric)
    db.flush()
    db.add(
        VehicleRatingWindow(
            vehicle_id=vehicle.id,
            metric_window_id=metric.id,
            period_start=latest_period_start,
            period_end=latest_period_end,
            car_type="UNKNOWN",
            final_rating=7.5,
            fuel_score=8.0,
            coasting_score=7.0,
            optimal_rpm_score=7.0,
            idle_score=8.0,
            brakes_score=8.0,
            high_speed_brakes_score=8.0,
            cruise_control_score=7.0,
            overspeed_score=8.0,
            weights_json={},
            warnings_json=[],
            positive_factors_json=[],
            negative_factors_json=[],
            raw_json={},
        )
    )
    db.commit()

    client = build_client(factory, admin)
    try:
        summary_response = client.get('/api/dashboard/summary', params={'period': 'week'})
        timeseries_response = client.get('/api/dashboard/timeseries', params={'period': 'week'})
        comparison_response = client.get('/api/dashboard/comparison', params={'period': 'week'})
        report_response = client.get('/api/reports/fleet', params={'period': 'week'})
    finally:
        app.dependency_overrides.clear()

    assert summary_response.status_code == 200
    assert summary_response.json()['vehicles_count'] == 1
    assert summary_response.json()['fleet_rating'] == 7.5
    assert timeseries_response.status_code == 200
    assert len(timeseries_response.json()) == 1
    assert comparison_response.status_code == 200
    assert len(comparison_response.json()) == 1
    assert report_response.status_code == 200
    assert report_response.json()['summary']['vehicles_count'] == 1
