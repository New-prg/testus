from abc import ABC, abstractmethod
from typing import Any


class TelemetryProvider(ABC):
    """Common boundary for telemetry sources that can populate fleet readings."""

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
