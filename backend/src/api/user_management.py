from src import configure_logger, get_logger
from sqlalchemy import create_engine
import os
from fastapi.routing import APIRouter
from fastapi import Depends, HTTPException, status
from sqlmodel import and_, select
import sqlmodel
from datetime import datetime, timedelta
from src.models import *
from src.models import Session as AuthSession
from src.utils import get_db_session, get_user_info
from uuid import uuid4

engine = create_engine(os.environ["DATABASE_URL"])
configure_logger(engine, service_name="api")
logger = get_logger("user-manager")

router = APIRouter(prefix="/users", tags=["User Management"])


@router.post("/register", response_model=ApiResponse)
def register(
    request: RegisterUserRequest,
    db_session: sqlmodel.Session = Depends(get_db_session),
):
    if request.password != request.password2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match"
        )

    # Check if user already exists
    existing_user = db_session.exec(
        select(User).where(User.username == request.username)
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Username already exists"
        )

    user = User(
        tenant_id=str(uuid4()),
        username=request.username,
        password=request.password,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    logger.info("user_registered", username=request.username, tenant_id=user.tenant_id)

    return ApiResponse(message="User created successfully")


@router.post("/login", response_model=ApiResponse)
def login(
    request: LoginUserRequest,
    db_session: sqlmodel.Session = Depends(get_db_session),
):
    user = db_session.exec(
        select(User).where(
            and_(User.username == request.username, User.password == request.password)
        )
    ).first()

    if not user:
        logger.warning(
            "login_failed", username=request.username, reason="invalid_credentials"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wrong username or password",
        )

    if not user.is_active:
        logger.warning(
            "login_failed", username=request.username, reason="account_disabled"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled"
        )

    auth_session = AuthSession(
        user_id=user.id,
        ip_address="127.0.0.1",
        user_agent="Mozilla",
        expires_at=datetime.now() + timedelta(days=7),
    )
    db_session.add(auth_session)
    db_session.commit()
    db_session.refresh(auth_session)
    session_token = auth_session.token

    logger.info("user_logged_in", username=request.username, tenant_id=user.tenant_id)

    return ApiResponse(
        message="User logged in successfully", data={"session_token": session_token}
    )


@router.post("/change-password", response_model=ApiResponse)
def reset_password(
    request: ResetPasswordRequest,
    db_session: sqlmodel.Session = Depends(get_db_session),
):
    if request.new_password != request.new_password2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="New passwords do not match"
        )

    if request.old_password == request.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from old password",
        )

    user = db_session.exec(
        select(User).where(User.username == request.username)
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if user.password != request.old_password:
        logger.warning(
            "password_change_failed",
            username=request.username,
            reason="incorrect_old_password",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Old password is incorrect",
        )

    user.password = request.new_password
    db_session.add(user)

    logger.info("password_changed", username=request.username, tenant_id=user.tenant_id)

    return ApiResponse(message="Password reset successfully")


@router.get("/get-info", response_model=ApiResponse)
def get_current_user_info(user_info: UserInfo = Depends(get_user_info)):
    return ApiResponse(
        message="Information retrieved successfully", data=user_info.model_dump()
    )
