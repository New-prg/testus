from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import deps
from app.db.models import SyncLog, User
from app.db.session import get_db
from app.services.pilot_gps.client import HttpPilotGpsClient
from app.services.pilot_gps.sync_service import PilotSyncService


router = APIRouter(prefix="/pilot/sync", tags=["pilot-sync"], dependencies=[Depends(deps.get_admin_user)])


@router.post("/vehicles")
def sync_vehicles(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(deps.get_admin_user)],
) -> dict[str, Any]:
    return PilotSyncService().sync_vehicles(db, current_user)


@router.post("/sensors")
def sync_sensors(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(deps.get_admin_user)],
) -> dict[str, Any]:
    return PilotSyncService().sync_sensors(db, current_user)


@router.post("/readings")
def sync_readings(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(deps.get_admin_user)],
    days: int = 30,
) -> dict[str, Any]:
    return PilotSyncService().sync_readings(db, current_user, days)


@router.post("/analytics")
def sync_analytics(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(deps.get_admin_user)],
    days: int = 30,
) -> dict[str, Any]:
    return PilotSyncService().calculate_analytics(db, current_user, days)


@router.post("/all")
def sync_all(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(deps.get_admin_user)],
    days: int = 30,
) -> dict[str, Any]:
    return PilotSyncService().sync_all(db, current_user, days)


@router.post("/current")
def import_current_snapshot(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(deps.get_admin_user)],
    replace_shared_fleet: bool = False,
    anonymize: bool = False,
) -> dict[str, Any]:
    return PilotSyncService(HttpPilotGpsClient()).import_live_current_snapshot(
        db,
        current_user,
        replace_shared_fleet=replace_shared_fleet,
        anonymize=anonymize,
    )


@router.get("/logs")
def sync_logs(db: Annotated[Session, Depends(get_db)], limit: int = 100) -> list[dict[str, Any]]:
    logs = db.scalars(select(SyncLog).order_by(SyncLog.started_at.desc()).limit(min(limit, 500))).all()
    return [
        {
            "id": log.id,
            "sync_type": log.sync_type,
            "status": log.status,
            "message": log.message,
            "started_at": log.started_at,
            "finished_at": log.finished_at,
            "payload": log.payload,
        }
        for log in logs
    ]
