from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.config.analytics_sensors import resolve_analytics_key, resolve_analytics_key_from_candidates
from app.core.security import encrypt_secret, hash_password
from app.db.models import AnalyticsSensorLink, SensorReading, User, Vehicle
from app.db.session import Base
from app.services.pilot_gps.client import PilotGpsClient
from app.services.pilot_gps.sensor_parser import PilotSensorParser
from app.services.pilot_gps.sync_service import PilotSyncService


def build_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


class FakePilotClient(PilotGpsClient):
    def list_vehicles(self) -> list[dict[str, object]]:
        return [
            {
                "agentid": 1001,
                "imei": "867236071418257",
                "vehiclenumber": "У683МА196",
                "vin": "XTC549015S2627819",
                "type": "Big rig",
                "sensors": [{"id": "139219", "name": "Полный пробег (CAN)"}],
                "sensors_status": [{"id": "139219", "name": "Полный пробег (CAN)", "raw_value": "61981", "dig_value": "61981", "change_ts": "1780172313", "speed": "54"}],
            }
        ]

    def list_sensors(self, pilot_agent_id: str) -> list[dict[str, object]]:
        return []

    def list_sensor_history(self, pilot_agent_id: str, days: int) -> dict[str, list[dict[str, object]]]:
        return {}

    def list_current_status(self, agent_ids: list[str]) -> dict[str, dict[str, object]]:
        return {
            "1001": {
                "agentid": 1001,
                "sensors_status": [{"id": "139219", "name": "Полный пробег (CAN)", "raw_value": "61981", "dig_value": "61981", "change_ts": "1780172313", "speed": "54"}],
            }
        }


class FakeFieldnamePilotClient(PilotGpsClient):
    def list_vehicles(self) -> list[dict[str, object]]:
        return [
            {
                "agentid": 2001,
                "imei": "867236071418258",
                "vehiclenumber": "А001АА196",
                "vin": "FIELDNAME-VIN-001",
                "type": "Big rig",
                "sensors": [{"id": "fld-1", "fieldname": "distance", "description": "Distance counter"}],
                "sensors_status": [
                    {"id": "fld-1", "fieldname": "distance", "raw_value": "100", "dig_value": "100", "change_ts": "1780172313"},
                    {"id": "fld-1", "fieldname": "distance", "raw_value": "100", "dig_value": "100", "change_ts": "1780172313"},
                ],
            }
        ]

    def list_sensors(self, pilot_agent_id: str) -> list[dict[str, object]]:
        return []

    def list_sensor_history(self, pilot_agent_id: str, days: int) -> dict[str, list[dict[str, object]]]:
        return {
            "distance": [
                {"timestamp": "2026-01-01T00:00:00Z", "value": 100.0, "speed": 0.0},
                {"timestamp": "2026-01-01T00:00:00Z", "value": 100.0, "speed": 0.0},
                {"timestamp": "2026-01-01T01:00:00Z", "value": 110.0, "speed": 20.0},
            ]
        }

    def list_current_status(self, agent_ids: list[str]) -> dict[str, dict[str, object]]:
        return {
            "2001": {
                "agentid": 2001,
                "sensors_status": [
                    {"id": "fld-1", "fieldname": "distance", "raw_value": "100", "dig_value": "100", "change_ts": "1780172313"},
                    {"id": "fld-1", "fieldname": "distance", "raw_value": "100", "dig_value": "100", "change_ts": "1780172313"},
                ],
            }
        }


class FakeAliasHistoryPilotClient(FakeFieldnamePilotClient):
    def list_sensor_history(self, pilot_agent_id: str, days: int) -> dict[str, list[dict[str, object]]]:
        return {
            "Полный пробег (CAN)": [
                {"timestamp": "2026-01-01T00:00:00Z", "value": 100.0, "speed": 0.0},
                {"timestamp": "2026-01-01T01:00:00Z", "value": 110.0, "speed": 20.0},
            ]
        }


def test_resolve_analytics_key_uses_aliases() -> None:
    assert resolve_analytics_key("Полный пробег (CAN)") == "distance"
    assert resolve_analytics_key("Полный расход топлива (CAN)") == "fuel_consumption"
    assert resolve_analytics_key("Педаль тормоза") == "brake_pedal"
    assert resolve_analytics_key("Неизвестный сенсор") is None


def test_resolve_analytics_key_from_candidates_supports_canonical_fieldname() -> None:
    assert resolve_analytics_key_from_candidates("distance") == "distance"
    assert resolve_analytics_key_from_candidates("speed", "Неизвестный сенсор") == "speed"
    assert resolve_analytics_key_from_candidates("unknown", "Полный пробег (CAN)") == "distance"


def test_parse_status_reading_parses_numeric_snapshot() -> None:
    payload = {
        "id": "139219",
        "name": "Полный пробег (CAN)",
        "raw_value": "61981",
        "dig_value": "61981",
        "change_ts": "1780172313",
        "speed": "54",
    }

    reading = PilotSensorParser().parse_status_reading(payload)

    assert reading is not None
    assert reading["value"] == 61981.0
    assert reading["speed"] == 54.0
    assert reading["timestamp"] == datetime.fromtimestamp(1780172313, tz=UTC)


def test_import_can_replace_demo_fleet_and_anonymize_visible_fields() -> None:
    db = build_session()
    admin = User(email="admin@example.com", login="admin@example.com", password_hash=hash_password("admin123"), pilot_password_encrypted=encrypt_secret("admin123"), full_name="Demo Admin", role="admin", is_demo=True)
    db.add(admin)
    db.commit()
    db.add(Vehicle(user_id=admin.id, pilot_agent_id="demo-agent-001", imei="860000000000001", plate_number="DEMO-001", name="Demo vehicle 01", vin="DEMO-VIN-00001", vehicle_type="truck", car_type="KAMAZ", is_active=True, raw_json={"provider": "demo"}))
    db.commit()

    result = PilotSyncService(FakePilotClient()).import_live_current_snapshot(db, admin, replace_shared_fleet=True, anonymize=True)
    vehicles = db.scalars(select(Vehicle).order_by(Vehicle.name)).all()

    assert result["vehicles"] == 1
    assert len(vehicles) == 1
    assert vehicles[0].pilot_agent_id == "1001"
    assert vehicles[0].name == "Vehicle 001"
    assert vehicles[0].plate_number == "ANON-001"
    assert vehicles[0].imei == "IMEI-001"
    assert vehicles[0].vin == "VIN-001"


def test_import_live_current_snapshot_maps_fieldname_and_deduplicates_payload_rows() -> None:
    db = build_session()
    admin = User(email="fieldname@example.com", login="fieldname@example.com", password_hash=hash_password("admin123"), pilot_password_encrypted=encrypt_secret("admin123"), full_name="Fieldname Admin", role="admin", is_demo=True)
    db.add(admin)
    db.commit()

    result = PilotSyncService(FakeFieldnamePilotClient()).import_live_current_snapshot(db, admin)
    vehicle = db.scalars(select(Vehicle)).one()
    links = db.scalars(select(AnalyticsSensorLink).where(AnalyticsSensorLink.vehicle_id == vehicle.id)).all()
    readings = db.scalars(select(SensorReading).where(SensorReading.vehicle_id == vehicle.id)).all()

    assert result["vehicles"] == 1
    assert {link.analytics_key for link in links} == {"distance"}
    assert len(readings) == 1


def test_sync_readings_imports_only_new_history_points() -> None:
    db = build_session()
    owner = User(email="history@example.com", login="history@example.com", password_hash=hash_password("admin123"), pilot_password_encrypted=encrypt_secret("admin123"), full_name="History Owner", role="admin", is_demo=True)
    db.add(owner)
    db.commit()

    service = PilotSyncService(FakeFieldnamePilotClient())
    service.import_live_current_snapshot(db, owner)
    first_result = service.sync_readings(db, owner, days=2)
    second_result = service.sync_readings(db, owner, days=2)
    readings = db.scalars(select(SensorReading).order_by(SensorReading.timestamp.asc())).all()

    assert first_result["inserted"] == 2
    assert second_result["inserted"] == 0
    assert len(readings) == 3


def test_sync_readings_accepts_alias_history_keys() -> None:
    db = build_session()
    owner = User(email="history-alias@example.com", login="history-alias@example.com", password_hash=hash_password("admin123"), pilot_password_encrypted=encrypt_secret("admin123"), full_name="History Alias Owner", role="admin", is_demo=True)
    db.add(owner)
    db.commit()

    service = PilotSyncService(FakeAliasHistoryPilotClient())
    service.import_live_current_snapshot(db, owner)
    result = service.sync_readings(db, owner, days=2)

    assert result["inserted"] == 2
