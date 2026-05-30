from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.db.models import User, Vehicle


oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{get_settings().api_prefix}/auth/login")


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: Annotated[Session, Depends(get_db)]) -> User:
    credentials_error = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError as exc:
        raise credentials_error from exc
    user_id = payload.get("sub")
    if not user_id:
        raise credentials_error
    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise credentials_error
    return user


def get_admin_user(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def get_fleet_access_user(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if current_user.is_admin:
        return current_user
    live_vehicle_exists = db.scalar(
        select(Vehicle.id)
        .where(Vehicle.pilot_agent_id.is_not(None))
        .where(~Vehicle.pilot_agent_id.like("demo-agent-%"))
        .limit(1)
    )
    if live_vehicle_exists:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Live Pilot-GPS data is available to admin users only")
    return current_user
