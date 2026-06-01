from abc import ABC
from collections.abc import Iterable
from typing import Any


class TelemetryProvider(ABC):
    """Common boundary for telemetry sources used by the platform.

    Providers may either expose operational sync methods (Pilot-GPS) or yield
    normalized/importable telemetry rows for reproducible local dataset flows.
    Unsupported capabilities can raise ``NotImplementedError``.
    """

    def list_vehicles(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def list_sensors(self, pilot_agent_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    def list_sensor_history(self, pilot_agent_id: str, days: int) -> dict[str, list[dict[str, Any]]]:
        raise NotImplementedError

    def list_current_status(self, agent_ids: list[str]) -> dict[str, dict[str, Any]]:
        raise NotImplementedError

    def iter_rows(self) -> Iterable[dict[str, Any]]:
        raise NotImplementedError
