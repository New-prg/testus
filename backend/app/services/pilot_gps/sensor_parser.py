from datetime import UTC, datetime
from typing import Any


class PilotSensorParser:
    def parse_vehicle_sensor(self, payload: dict[str, Any], analytics_key: str | None = None) -> dict[str, Any]:
        return {
            "pilot_sensor_id": str(payload.get("id")) if payload.get("id") is not None else None,
            "name": str(payload.get("name") or payload.get("description") or "Pilot-GPS sensor"),
            "sensor_type": analytics_key or "pilot_gps_sensor",
            "unit": payload.get("unit") or payload.get("measure_unit"),
            "is_active": True,
            "raw_json": payload,
        }

    def parse_reading(self, payload: dict[str, Any]) -> dict[str, Any]:
        timestamp = payload.get("timestamp") or payload.get("recorded_at") or payload.get("time")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        raw_json = dict(payload)
        for key in ("timestamp", "recorded_at", "time"):
            if isinstance(raw_json.get(key), datetime):
                raw_json[key] = raw_json[key].isoformat()
        return {
            "timestamp": timestamp,
            "value": float(payload["value"]) if payload.get("value") is not None else None,
            "speed": float(payload["speed"]) if payload.get("speed") is not None else None,
            "raw_json": raw_json,
        }

    def parse_status_reading(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        timestamp = payload.get("change_ts") or payload.get("timestamp")
        if isinstance(timestamp, str) and timestamp.isdigit():
            timestamp = datetime.fromtimestamp(int(timestamp), tz=UTC)
        elif isinstance(timestamp, int | float):
            timestamp = datetime.fromtimestamp(int(timestamp), tz=UTC)
        elif isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        else:
            timestamp = datetime.now(UTC)

        raw_value = payload.get("raw_value")
        dig_value = payload.get("dig_value")
        value = None
        for candidate in (raw_value, dig_value):
            try:
                if candidate is None:
                    continue
                value = float(candidate)
                break
            except (TypeError, ValueError):
                continue
        if value is None:
            return None

        speed = None
        for candidate in (payload.get("speed"), raw_value, dig_value):
            try:
                speed = float(candidate) if candidate is not None else None
                if speed is not None:
                    break
            except (TypeError, ValueError):
                continue

        return {
            "timestamp": timestamp,
            "value": value,
            "speed": speed,
            "raw_json": dict(payload),
        }
