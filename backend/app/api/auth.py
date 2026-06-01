from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token, encrypt_secret, hash_password, verify_password
from app.db.models import User, utcnow
from app.db.session import get_db
from app.schemas.auth import LoginRequest, TokenResponse, UserCreate, UserRead
from app.services.pilot_gps.client import HttpPilotGpsClient, validate_pilot_server_address


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Annotated[Session, Depends(get_db)]) -> User:
    if db.scalar(select(User).where(User.login == payload.login)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Пользователь с таким логином уже зарегистрирован")

    try:
        server_address = validate_pilot_server_address(payload.server_address)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        HttpPilotGpsClient(
            base_url=server_address,
            node=payload.node,
            username=payload.login,
            password=payload.password,
        ).list_vehicles()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось подтвердить доступ к Pilot-GPS с указанными логином, паролем, сервером и нодой",
        ) from exc

    user = User(
        email=payload.login,
        login=payload.login,
        password_hash=hash_password(payload.password),
        pilot_password_encrypted=encrypt_secret(payload.password),
        full_name=payload.full_name,
        pilot_server_address=server_address,
        pilot_node=payload.node,
        sync_started_at=utcnow(),
        next_sync_at=utcnow(),
    )
    db.add(user)
    db.flush()
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    user = db.scalar(select(User).where(User.login == payload.login))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")
    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserRead)
def me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user
