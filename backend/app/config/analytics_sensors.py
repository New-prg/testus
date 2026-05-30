from typing import Literal, NotRequired, TypedDict


SensorKind = Literal["counter", "active_interval", "active_interval_or_counter", "trigger_count", "number"]


class AnalyticsSensorConfig(TypedDict):
    pilot_name: str
    required: bool
    kind: SensorKind
    unit: str
    aliases: NotRequired[list[str]]


IDLE_GRACE_SECONDS = 600
HIGH_SPEED_BRAKING_THRESHOLD_KMH = 70

ANALYTICS_SENSORS: dict[str, AnalyticsSensorConfig] = {
    "distance": {
        "pilot_name": "Пробег (FTLot_Service)",
        "required": True,
        "kind": "counter",
        "unit": "km",
        "aliases": ["Полный пробег (CAN)", "Пробег"],
    },
    "fuel_consumption": {
        "pilot_name": "Абс. расход топлива (FTLot_Service)",
        "required": True,
        "kind": "counter",
        "unit": "l",
        "aliases": ["Полный расход топлива (CAN)", "Датчик топлива CAN"],
    },
    "coasting": {
        "pilot_name": "Накат (FTLot_Service)",
        "required": True,
        "kind": "active_interval_or_counter",
        "unit": "percent_source",
    },
    "optimal_rpm": {
        "pilot_name": "Оптимальные обороты (FTLot_Service)",
        "required": True,
        "kind": "active_interval_or_counter",
        "unit": "percent_source",
        "aliases": ["Обороты двигателя (CAN)", "Обороты (для отчёта)"],
    },
    "idle_time": {
        "pilot_name": "Время простоев (FTLot_Service)",
        "required": True,
        "kind": "active_interval",
        "unit": "seconds",
    },
    "engine_work_time": {
        "pilot_name": "Время работы двигателя (FTLot_Service)",
        "required": True,
        "kind": "active_interval_or_counter",
        "unit": "seconds",
        "aliases": ["Общее время работы двигателя (CAN)"],
    },
    "brake_pedal": {
        "pilot_name": "Педаль тормоза (FTLot_Service)",
        "required": True,
        "kind": "trigger_count",
        "unit": "count",
        "aliases": ["Педаль тормоза"],
    },
    "cruise_control": {
        "pilot_name": "Круиз-контроль (FTLot_Service)",
        "required": True,
        "kind": "active_interval_or_counter",
        "unit": "percent_source",
        "aliases": ["Круиз-контроль", "Круиз-контроль пробег"],
    },
    "overspeed": {
        "pilot_name": "Неоптимальная скорость (FTLot_Service)",
        "required": True,
        "kind": "active_interval_or_counter",
        "unit": "percent_source",
        "aliases": ["Превышение скорости 85км/ч", "Неоптимальная скорость"],
    },
    "speed": {
        "pilot_name": "скорость CAN (для отчёта)",
        "required": False,
        "kind": "number",
        "unit": "kmh",
        "aliases": ["Скорость (CAN)", "скорость CAN (для отчёта)", "Скорость Тах (для отчёта)"],
    },
}

DISTANCE_SENSOR = "distance"
FUEL_SENSOR = "fuel_consumption"
COASTING_SENSOR = "coasting"
OPTIMAL_RPM_SENSOR = "optimal_rpm"
IDLE_TIME_SENSOR = "idle_time"
ENGINE_WORK_TIME_SENSOR = "engine_work_time"
BRAKE_PEDAL_SENSOR = "brake_pedal"
CRUISE_CONTROL_SENSOR = "cruise_control"
OVERSPEED_SENSOR = "overspeed"
SPEED_SENSOR = "speed"


def normalize_sensor_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


def resolve_analytics_key(sensor_name: str) -> str | None:
    normalized = normalize_sensor_name(sensor_name)
    for key, spec in ANALYTICS_SENSORS.items():
        candidates = [spec["pilot_name"], *spec.get("aliases", [])]
        if any(normalize_sensor_name(candidate) == normalized for candidate in candidates):
            return key
    return None


TOTAL_ANALYTICS_SENSORS = len(ANALYTICS_SENSORS)
