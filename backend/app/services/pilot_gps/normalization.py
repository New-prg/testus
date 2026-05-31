from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any


def first_not_empty(*values: Any) -> Any | None:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def day_chunks(start_ts: int, stop_ts: int) -> Iterable[tuple[int, int]]:
    current = start_ts
    step = 24 * 60 * 60
    while current < stop_ts:
        chunk_stop = min(current + step - 1, stop_ts)
        yield current, chunk_stop
        current = chunk_stop + 1


def to_unix(value: str | datetime) -> int:
    if isinstance(value, datetime):
        dt = value
    elif "T" in value:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        dt = datetime.fromisoformat(value).replace(tzinfo=UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return int(dt.timestamp())


def extract_vehicle_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("list", "data", "agents", "vehicles"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise RuntimeError(f"Unexpected vehicle list response: {payload}")


def extract_status_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("data", "agents_status", "list", "status"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            return [value]
    return []


def extract_sensors_from_status(status_item: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("sensors_status", "sensors", "sensor_status"):
        value = status_item.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def normalize_sensor(sensor: dict[str, Any]) -> dict[str, Any] | None:
    sensor_record_id = first_not_empty(sensor.get("id"), sensor.get("sensor_id"), sensor.get("tag_id"))
    sensor_tag_id = first_not_empty(sensor.get("tag_id"), sensor.get("sensor_id"), sensor.get("id"))
    if sensor_tag_id is None:
        return None
    return {
        "id": str(sensor_record_id) if sensor_record_id is not None else None,
        "tag_id": str(sensor_tag_id),
        "name": sensor.get("name"),
        "group": sensor.get("group"),
        "type": sensor.get("type"),
        "last_hum_value": sensor.get("hum_value"),
        "last_dig_value": sensor.get("dig_value"),
        "last_raw_value": sensor.get("raw_value"),
        "last_change_ts": sensor.get("change_ts"),
        "raw": sensor,
    }


def extract_sensor_points(payload: dict[str, Any], sensor_id: str | None = None) -> list[Any]:
    for key in ("sensor_data", "data", "values", "points"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            normalized_sensor_id = str(sensor_id) if sensor_id is not None else None
            if normalized_sensor_id is not None:
                sensor_bucket = value.get(normalized_sensor_id)
                if isinstance(sensor_bucket, dict):
                    return normalize_sensor_bucket(sensor_bucket)
            nested = [bucket for bucket in value.values() if isinstance(bucket, dict)]
            if nested:
                return [point for bucket in nested for point in normalize_sensor_bucket(bucket)]
    return []


def normalize_sensor_bucket(sensor_bucket: dict[str, Any]) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for timestamp, point in sensor_bucket.items():
        if not isinstance(point, dict):
            continue
        normalized = dict(point)
        normalized.setdefault("unixtimestamp", int(timestamp) if str(timestamp).isdigit() else timestamp)
        points.append(normalized)
    return points
