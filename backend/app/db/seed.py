from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import encrypt_secret, hash_password
from app.db.models import MLModelRun, MLResult, User, Vehicle
from app.services.pilot_gps.sync_service import PilotSyncService
from app.services.telemetry.dataset_importer import DatasetImporter, DatasetProvider, LocalDatasetProvider


DEMO_SEED_DAYS = 1


def ensure_demo_admin(db: Session) -> dict[str, str]:
    admin = db.scalar(select(User).where(User.email == "admin@example.com"))
    if not admin:
        admin = User(
            email="admin@example.com",
            login="admin@example.com",
            password_hash=hash_password("admin123"),
            pilot_password_encrypted=encrypt_secret("admin123"),
            full_name="Demo Admin",
            role="admin",
            is_demo=True,
        )
        db.add(admin)
        db.flush()
    else:
        admin.login = admin.login or admin.email
        admin.is_demo = True
        admin.pilot_password_encrypted = admin.pilot_password_encrypted or encrypt_secret("admin123")
    return {"admin": "admin@example.com"}


def seed_demo_data(db: Session) -> dict[str, Any]:
    admin_payload = ensure_demo_admin(db)
    admin = db.scalar(select(User).where(User.login == "admin@example.com"))
    if admin is None:
        raise ValueError("Demo admin user was not created")
    settings = get_settings()
    dataset_path = Path(settings.demo_dataset_path).expanduser() if settings.demo_dataset_path else None
    sensor_profile_path = Path(settings.demo_sensor_profile_path).expanduser() if settings.demo_sensor_profile_path else None
    if dataset_path and dataset_path.exists():
        print(f"[seed-demo] Starting dataset import from {dataset_path} with row limit {settings.demo_dataset_row_limit}", flush=True)
        _reset_demo_statistics(db, admin)
        provider = DemoDayLimitedProvider(
            LocalDatasetProvider(dataset_path, max_size_bytes=-1, row_limit=settings.demo_dataset_row_limit),
            max_days=DEMO_SEED_DAYS,
        )
        result = DatasetImporter().import_provider(db, provider, admin).as_dict()
        return {
            **admin_payload,
            "source": "local_dataset",
            "dataset_path": str(dataset_path),
            "sensor_profile_path": str(sensor_profile_path) if sensor_profile_path and sensor_profile_path.exists() else None,
            "dataset_row_limit": settings.demo_dataset_row_limit,
            **result,
        }
    if dataset_path and not dataset_path.exists():
        print(f"[seed-demo] Demo dataset {dataset_path} is unavailable; falling back to generated demo provider", flush=True)
    sync = PilotSyncService()
    _reset_demo_statistics(db, admin)
    result = sync.sync_all(db, admin, days=DEMO_SEED_DAYS)
    return {**admin_payload, "source": "demo_pilot_provider", **result}


class DemoDayLimitedProvider(DatasetProvider):
    def __init__(self, base_provider: DatasetProvider, max_days: int = 1) -> None:
        self.base_provider = base_provider
        self.max_days = max_days

    def iter_rows(self) -> Any:
        allowed_dates: list[date] = []
        for row in self.base_provider.iter_rows():
            trimmed_row, row_dates = _limit_row_to_dates(row, allowed_dates, self.max_days)
            if trimmed_row is None:
                continue
            for row_date in row_dates:
                if row_date not in allowed_dates:
                    allowed_dates.append(row_date)
                    allowed_dates.sort()
            yield trimmed_row


def _limit_row_to_dates(row: dict[str, Any], allowed_dates: list[date], max_days: int) -> tuple[dict[str, Any] | None, list[date]]:
    if row.get("record_type") == "sensor_day_chunk" and isinstance(row.get("sensor_data"), list):
        trimmed_points: list[dict[str, Any]] = []
        seen_dates: list[date] = []
        for point in row["sensor_data"]:
            if not isinstance(point, dict):
                continue
            point_date = _row_date(point)
            if point_date is None or not _date_allowed(point_date, allowed_dates, max_days):
                continue
            if point_date not in seen_dates:
                seen_dates.append(point_date)
            trimmed_points.append(point)
        if not trimmed_points:
            return None, []
        return {**row, "sensor_data": trimmed_points}, seen_dates

    row_date = _row_date(row)
    if row_date is None or not _date_allowed(row_date, allowed_dates, max_days):
        return None, []
    return row, [row_date]


def _date_allowed(candidate: date, allowed_dates: list[date], max_days: int) -> bool:
    if candidate in allowed_dates:
        return True
    if len(allowed_dates) >= max_days:
        return False
    return not allowed_dates or candidate <= min(allowed_dates)


def _row_date(row: dict[str, Any]) -> date | None:
    timestamp = _parse_timestamp(
        row.get("timestamp")
        or row.get("recorded_at")
        or row.get("time")
        or row.get("unixtimestamp")
        or row.get("change_ts")
    )
    return timestamp.date() if timestamp else None


def _parse_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    if value in (None, ""):
        return None
    if isinstance(value, int | float) or (isinstance(value, str) and value.isdigit()):
        return datetime.fromtimestamp(int(value), tz=UTC)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _reset_demo_statistics(db: Session, admin: User) -> None:
    demo_vehicle_ids = select(Vehicle.id).where(Vehicle.user_id == admin.id)
    db.execute(delete(MLModelRun))
    db.execute(delete(MLResult).where(MLResult.vehicle_id.in_(demo_vehicle_ids)))
    db.execute(delete(Vehicle).where(Vehicle.user_id == admin.id))
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
