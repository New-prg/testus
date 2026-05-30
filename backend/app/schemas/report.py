from datetime import date
from typing import Any

from pydantic import BaseModel


class ReportCreate(BaseModel):
    period_start: date
    period_end: date
    name: str | None = None


class ReportRead(BaseModel):
    id: str
    name: str
    report_type: str
    period_start: date
    period_end: date
    payload: dict[str, Any]

    model_config = {"from_attributes": True}
