from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import User
from app.services.pilot_gps.sync_service import PilotSyncService


def seed_demo_data(db: Session) -> dict[str, Any]:
    admin = db.scalar(select(User).where(User.email == "admin@example.com"))
    if not admin:
        db.add(User(email="admin@example.com", password_hash=hash_password("admin123"), full_name="Demo Admin", role="admin"))
        db.flush()
    sync = PilotSyncService()
    result = sync.sync_all(db, days=32)
    return {"admin": "admin@example.com", **result}


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
