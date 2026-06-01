from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.models import MLModelRun, MLResult, User, Vehicle
from app.services.pilot_gps.sync_service import PilotSyncService
from app.services.telemetry.dataset_importer import DatasetImporter, LocalDatasetProvider


def ensure_demo_admin(db: Session) -> dict[str, str]:
    admin = db.scalar(select(User).where(User.email == "admin@example.com"))
    if not admin:
        db.add(User(email="admin@example.com", password_hash=hash_password("admin123"), full_name="Demo Admin", role="admin"))
        db.flush()
    return {"admin": "admin@example.com"}


def seed_demo_data(db: Session) -> dict[str, Any]:
    admin_payload = ensure_demo_admin(db)
    settings = get_settings()
    dataset_path = Path(settings.demo_dataset_path).expanduser() if settings.demo_dataset_path else None
    sensor_profile_path = Path(settings.demo_sensor_profile_path).expanduser() if settings.demo_sensor_profile_path else None
    if dataset_path and not dataset_path.exists():
        raise ValueError(f"Configured demo dataset path does not exist: {dataset_path}")
    if dataset_path and dataset_path.exists():
        print(f"[seed-demo] Starting background dataset import from {dataset_path} with row limit {settings.demo_dataset_row_limit}", flush=True)
        _reset_demo_statistics(db)
        provider = LocalDatasetProvider(dataset_path, max_size_bytes=-1, row_limit=settings.demo_dataset_row_limit)
        result = DatasetImporter().import_provider(db, provider).as_dict()
        return {
            **admin_payload,
            "source": "local_dataset",
            "dataset_path": str(dataset_path),
            "sensor_profile_path": str(sensor_profile_path) if sensor_profile_path and sensor_profile_path.exists() else None,
            "dataset_row_limit": settings.demo_dataset_row_limit,
            **result,
        }
    sync = PilotSyncService()
    result = sync.sync_all(db, days=32)
    return {**admin_payload, "source": "demo_pilot_provider", **result}


def _reset_demo_statistics(db: Session) -> None:
    db.execute(delete(MLModelRun))
    db.execute(delete(MLResult))
    db.execute(delete(Vehicle))
    db.flush()


def main() -> None:
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        payload = seed_demo_data(db)
        db.commit()
        print(payload)
    finally:
        db.close()


if __name__ == "__main__":
    main()
