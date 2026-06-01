from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from ipaddress import ip_address
from random import Random
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config.analytics_sensors import ANALYTICS_SENSORS
from app.config.rating_profile import CAR_TYPE_KAMAZ, CAR_TYPE_NOT_KAMAZ
from app.core.config import Settings, get_settings
from app.services.pilot_gps.normalization import extract_status_items, extract_vehicle_list, first_not_empty
from app.services.telemetry.provider import TelemetryProvider


def validate_pilot_server_address(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https":
        raise ValueError("Pilot-GPS server must use HTTPS")
    if parsed.username or parsed.password:
        raise ValueError("Pilot-GPS server must not include embedded credentials")
    if parsed.params or parsed.query or parsed.fragment:
        raise ValueError("Pilot-GPS server must not include params, query, or fragment")
    if parsed.path not in ("", "/"):
        raise ValueError("Pilot-GPS server must point to the host root only")
    if not parsed.hostname:
        raise ValueError("Pilot-GPS server host is required")

    hostname = parsed.hostname.strip().lower()
    if hostname in {"localhost", "localhost.localdomain"}:
        raise ValueError("Pilot-GPS server host is not allowed")

    try:
        candidate = ip_address(hostname)
    except ValueError:
        candidate = None

    if candidate and (
        candidate.is_private
        or candidate.is_loopback
        or candidate.is_link_local
        or candidate.is_multicast
        or candidate.is_reserved
        or candidate.is_unspecified
    ):
        raise ValueError("Pilot-GPS server host is not allowed")

    return f"https://{hostname}" if parsed.port is None else f"https://{hostname}:{parsed.port}"


def redact_sensitive_error(message: str) -> str:
    lowered = message.lower()
    if any(token in lowered for token in ("authorization", "password", "token", "basic ", "bearer ")):
        return "Pilot-GPS request failed"
    return message


class PilotGpsClient(TelemetryProvider, ABC):
    @abstractmethod
    def list_vehicles(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def list_sensors(self, pilot_agent_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def list_sensor_history(self, pilot_agent_id: str, days: int) -> dict[str, list[dict[str, Any]]]:
        raise NotImplementedError

    @abstractmethod
    def list_current_status(self, agent_ids: list[str]) -> dict[str, dict[str, Any]]:
        raise NotImplementedError


class DemoPilotGpsClient(PilotGpsClient):
    def list_vehicles(self) -> list[dict[str, Any]]:
        vehicles: list[dict[str, Any]] = []
        for index in range(1, 13):
            car_type = CAR_TYPE_KAMAZ if index <= 4 else CAR_TYPE_NOT_KAMAZ
            vehicles.append(
                {
                    "pilot_agent_id": f"demo-agent-{index:03d}",
                    "imei": f"860000000000{index:03d}",
                    "plate_number": f"DEMO-{index:03d}",
                    "name": f"Demo vehicle {index:02d}",
                    "vin": f"DEMO-VIN-{index:05d}",
                    "vehicle_type": "truck" if car_type == CAR_TYPE_KAMAZ else "tractor",
                    "car_type": car_type,
                    "is_active": True,
                    "raw_json": {"provider": "demo", "style": ["good", "average", "inefficient", "anomalous"][index % 4]},
                }
            )
        return vehicles

    def list_sensors(self, pilot_agent_id: str) -> list[dict[str, Any]]:
        return [
            {
                "pilot_sensor_id": f"{pilot_agent_id}:{key}",
                "name": spec["pilot_name"],
                "fieldname": key,
                "typeid": spec["kind"],
                "measure_unit": spec["unit"],
                "history_enabled": True,
                "filter_enabled": False,
                "formula": None,
                "raw_json": {"source": "demo", "analytics_key": key},
            }
            for key, spec in ANALYTICS_SENSORS.items()
        ]

    def list_sensor_history(self, pilot_agent_id: str, days: int) -> dict[str, list[dict[str, Any]]]:
        rng = Random(sum(ord(char) for char in pilot_agent_id))
        start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days)
        style = sum(ord(char) for char in pilot_agent_id) % 4
        distance_counter = 0.0
        fuel_counter = 0.0
        history = {key: [] for key in ANALYTICS_SENSORS}
        for day in range(days):
            for sample in range(24):
                timestamp = start + timedelta(days=day, hours=sample)
                moving = 6 <= sample <= 20
                speed = 0.0 if not moving else max(0.0, rng.gauss(60 if style != 3 else 75, 12))
                if style == 0:
                    fuel_rate = 0.24
                    coasting = 0.34
                    optimal_rpm = 0.64
                    idle_seconds = 180
                    cruise = 0.18
                    overspeed = 0.02
                    brakes = 2
                elif style == 1:
                    fuel_rate = 0.29
                    coasting = 0.24
                    optimal_rpm = 0.52
                    idle_seconds = 420
                    cruise = 0.12
                    overspeed = 0.05
                    brakes = 4
                elif style == 2:
                    fuel_rate = 0.34
                    coasting = 0.16
                    optimal_rpm = 0.42
                    idle_seconds = 780
                    cruise = 0.08
                    overspeed = 0.09
                    brakes = 6
                else:
                    fuel_rate = 0.41
                    coasting = 0.1
                    optimal_rpm = 0.32
                    idle_seconds = 1200
                    cruise = 0.03
                    overspeed = 0.16
                    brakes = 9
                    if rng.random() < 0.25:
                        speed += 25
                distance_delta = 0.0 if not moving else speed * 0.7
                fuel_delta = 0.0 if not moving else distance_delta * fuel_rate
                distance_counter += distance_delta
                fuel_counter += fuel_delta
                brake_speed = speed if brakes > 0 else 0.0
                rows = {
                    "distance": distance_counter,
                    "fuel_consumption": fuel_counter,
                    "coasting": coasting,
                    "optimal_rpm": optimal_rpm,
                    "idle_time": float(idle_seconds),
                    "engine_work_time": 3600.0 if moving else 0.0,
                    "brake_pedal": float(brakes),
                    "cruise_control": cruise,
                    "overspeed": overspeed,
                    "speed": speed,
                }
                for key, value in rows.items():
                    history[key].append({
                        "timestamp": timestamp,
                        "value": round(float(value), 4),
                        "speed": round(float(brake_speed), 4),
                        "raw_json": {"provider": "demo", "analytics_key": key, "timestamp": timestamp.isoformat()},
                    })
        return history

    def list_current_status(self, agent_ids: list[str]) -> dict[str, dict[str, Any]]:
        status_map: dict[str, dict[str, Any]] = {}
        for agent_id in agent_ids:
            history = self.list_sensor_history(agent_id, 1)
            sensors_status = []
            for key, rows in history.items():
                if not rows:
                    continue
                latest = rows[-1]
                sensors_status.append(
                    {
                        "id": f"{agent_id}:{key}",
                        "name": ANALYTICS_SENSORS[key]["pilot_name"],
                        "raw_value": latest["value"],
                        "dig_value": latest["value"],
                        "change_ts": int(latest["timestamp"].timestamp()),
                        "speed": latest["speed"],
                    }
                )
            status_map[agent_id] = {"agentid": agent_id, "sensors_status": sensors_status}
        return status_map


class HttpPilotGpsClient(PilotGpsClient):
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        base_url: str | None = None,
        node: int | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.base_url = validate_pilot_server_address(base_url or self.settings.pilot_gps_base_url).rstrip("/")
        self.node = node if node is not None else self.settings.pilot_gps_node
        self.username = username if username is not None else self.settings.pilot_gps_username
        self.password = password if password is not None else self.settings.pilot_gps_password

    def list_vehicles(self) -> list[dict[str, Any]]:
        payload = self._get_json(self.base_url + "/api/api.php", {"cmd": "list", "node": self.node})
        return extract_vehicle_list(payload)

    def list_sensors(self, pilot_agent_id: str) -> list[dict[str, Any]]:
        return []

    def list_sensor_history(self, pilot_agent_id: str, days: int) -> dict[str, list[dict[str, Any]]]:
        # TODO: Historical calibrated per-sensor Pilot-GPS values remain unconfirmed in public official docs.
        return {}

    def list_current_status(self, agent_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not agent_ids:
            return {}
        payload = self._get_json(
            self.base_url + "/api/api.php",
            {"cmd": "status", "node": self.node, "agents": ",".join(agent_ids)},
        )
        rows = extract_status_items(payload)
        status_by_agent: dict[str, dict[str, Any]] = {}
        for row in rows:
            agent_id = first_not_empty(row.get("agentid"), row.get("agent_id"), row.get("id"))
            imei = first_not_empty(row.get("imei"), row.get("uniqid"), row.get("unique_id"))
            key = str(agent_id or imei or "")
            if key:
                status_by_agent[key] = row
        return status_by_agent

    def _get_json(self, url: str, params: dict[str, Any] | None = None, retries: int = 5, sleep_base: float = 1.5) -> Any:
        auth = (
            (self.username, self.password)
            if self.username and self.password
            else None
        )
        last_error: Exception | None = None
        for attempt in range(retries):
            try:
                with httpx.Client(timeout=60, auth=auth, headers={"Accept": "application/json", "User-Agent": "driving-analytics-backend/1.0"}) as client:
                    response = client.get(url, params=params)
                    response.raise_for_status()
                    payload = response.json()
                    if isinstance(payload, dict) and payload.get("code") not in (None, 0):
                        raise RuntimeError(f"Pilot-GPS API error code={payload.get('code')}")
                    return payload
            except Exception as exc:
                last_error = exc
                if attempt == retries - 1:
                    raise
                time.sleep(sleep_base * (2**attempt))
        raise RuntimeError(redact_sensitive_error(f"Pilot-GPS request failed: {last_error}"))


def get_pilot_client(settings: Settings | None = None) -> PilotGpsClient:
    settings = settings or get_settings()
    return DemoPilotGpsClient() if settings.use_demo_data else HttpPilotGpsClient(settings)
