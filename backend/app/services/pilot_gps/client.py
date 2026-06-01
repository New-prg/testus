from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from ipaddress import ip_address
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
        raise RuntimeError("Generated demo Pilot-GPS data is disabled. Use the static demo dataset import instead.")

    def list_sensors(self, pilot_agent_id: str) -> list[dict[str, Any]]:
        raise RuntimeError("Generated demo Pilot-GPS data is disabled. Use the static demo dataset import instead.")

    def list_sensor_history(self, pilot_agent_id: str, days: int) -> dict[str, list[dict[str, Any]]]:
        raise RuntimeError("Generated demo Pilot-GPS data is disabled. Use the static demo dataset import instead.")

    def list_current_status(self, agent_ids: list[str]) -> dict[str, dict[str, Any]]:
        raise RuntimeError("Generated demo Pilot-GPS data is disabled. Use the static demo dataset import instead.")


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
    if settings.use_demo_data:
        raise RuntimeError("Generated demo Pilot-GPS data is disabled. Seed the static demo dataset instead.")
    return HttpPilotGpsClient(settings)
