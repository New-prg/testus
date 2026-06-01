from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.config.analytics_sensors import resolve_analytics_key
from app.core.security import encrypt_secret, hash_password
from app.db.models import User, Vehicle
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


def test_resolve_analytics_key_uses_aliases() -> None:
    assert resolve_analytics_key("Полный пробег (CAN)") == "distance"
    assert resolve_analytics_key("Полный расход топлива (CAN)") == "fuel_consumption"
    assert resolve_analytics_key("Педаль тормоза") == "brake_pedal"
    assert resolve_analytics_key("Неизвестный сенсор") is None


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
