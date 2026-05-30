from typing import Any

from app.config.rating_profile import CAR_TYPE_KAMAZ, CAR_TYPE_NOT_KAMAZ, CAR_TYPE_UNKNOWN


class PilotVehicleParser:
    def parse(self, payload: dict[str, Any]) -> dict[str, Any]:
        # TODO: Pilot-GPS vehicle structure is unstable in public examples; replace fallback keys after official schema confirmation.
        raw_type = str(payload.get("car_type") or payload.get("vehicle_type") or payload.get("type") or "").upper()
        if "KAMAZ" in raw_type or "КАМАЗ" in raw_type:
            car_type = CAR_TYPE_KAMAZ
        elif raw_type:
            car_type = CAR_TYPE_NOT_KAMAZ
        else:
            car_type = CAR_TYPE_UNKNOWN
        return {
            "pilot_agent_id": str(payload.get("pilot_agent_id") or payload.get("agentid") or payload.get("id") or payload.get("object_id") or payload.get("vehicle_id")),
            "imei": payload.get("imei"),
            "plate_number": payload.get("plate_number") or payload.get("vehiclenumber") or payload.get("registration_number") or payload.get("number"),
            "name": payload.get("name") or payload.get("vehiclenumber") or payload.get("title") or "Pilot-GPS vehicle",
            "vin": payload.get("vin"),
            "vehicle_type": payload.get("vehicle_type") or payload.get("type"),
            "car_type": car_type,
            "is_active": bool(payload.get("is_active", True)),
            "raw_json": payload,
        }
