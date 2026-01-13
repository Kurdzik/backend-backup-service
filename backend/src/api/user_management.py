from src import configure_logger, get_logger, tenant_context
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
configure_logger(engine, service_name="api.user_management")
logger = get_logger("api.user_management")

router = APIRouter(prefix="/users", tags=["User Management"])


@router.post("/register", response_model=ApiResponse)
def register(
    request: RegisterUserRequest,
    db_session: sqlmodel.Session = Depends(get_db_session),
):
    logger.info("register_request_received", username=request.username)

    if request.password != request.password2:
        logger.warning(
            "register_failed",
            username=request.username,
            reason="passwords_do_not_match",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match",
        )

    try:
        # Check if user already exists
        existing_user = db_session.exec(
            select(User).where(User.username == request.username)
        ).first()

        if existing_user:
            logger.warning(
                "register_failed",
                username=request.username,
                reason="username_already_exists",
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already exists",
            )

        tenant_id = str(uuid4())
        user = User(
            tenant_id=tenant_id,
            username=request.username,
            password=request.password,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        logger.info(
            "user_registered_successfully",
            username=request.username,
            tenant_id=tenant_id,
            user_id=user.id,
        )

        return ApiResponse(message="User created successfully")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "register_failed",
            username=request.username,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register user",
        )


@router.post("/login", response_model=ApiResponse)
def login(
    request: LoginUserRequest,
    db_session: sqlmodel.Session = Depends(get_db_session),
):
    logger.info("login_request_received", username=request.username)

    try:
        user = db_session.exec(
            select(User).where(
                and_(
                    User.username == request.username,
                    User.password == request.password,
                )
            )
        ).first()

        if not user:
            logger.warning(
                "login_failed",
                username=request.username,
                reason="invalid_credentials",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Wrong username or password",
            )

        if not user.is_active:
            logger.warning(
                "login_failed",
                username=request.username,
                tenant_id=user.tenant_id,
                reason="account_disabled",
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is disabled",
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

        logger.info(
            "user_logged_in_successfully",
            username=request.username,
            tenant_id=user.tenant_id,
            user_id=user.id,
            session_id=auth_session.id,
        )

        return ApiResponse(
            message="User logged in successfully",
            data={"session_token": session_token},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "login_failed",
            username=request.username,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to login",
        )


@router.post("/change-password", response_model=ApiResponse)
def reset_password(
    request: ResetPasswordRequest,
    db_session: sqlmodel.Session = Depends(get_db_session),
):
    logger.info("change_password_request_received", username=request.username)

    if request.new_password != request.new_password2:
        logger.warning(
            "change_password_failed",
            username=request.username,
            reason="new_passwords_do_not_match",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New passwords do not match",
        )

    if request.old_password == request.new_password:
        logger.warning(
            "change_password_failed",
            username=request.username,
            reason="new_password_same_as_old",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from old password",
        )

    try:
        user = db_session.exec(
            select(User).where(User.username == request.username)
        ).first()

        if not user:
            logger.warning(
                "change_password_failed",
                username=request.username,
                reason="user_not_found",
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        if user.password != request.old_password:
            logger.warning(
                "change_password_failed",
                username=request.username,
                tenant_id=user.tenant_id,
                reason="incorrect_old_password",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Old password is incorrect",
            )

        user.password = request.new_password
        db_session.add(user)
        db_session.commit()

        logger.info(
            "password_changed_successfully",
            username=request.username,
            tenant_id=user.tenant_id,
            user_id=user.id,
        )

        return ApiResponse(message="Password reset successfully")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "change_password_failed",
            username=request.username,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password",
        )


@router.get("/get-info", response_model=ApiResponse)
def get_current_user_info(user_info: UserInfo = Depends(get_user_info)):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api"):
        logger.info(
            "get_user_info_request_received",
            tenant_id=user_info.tenant_id,
            user_id=user_info.user_id,
        )

        try:
            logger.info(
                "user_info_retrieved_successfully",
                tenant_id=user_info.tenant_id,
                user_id=user_info.user_id,
            )

            return ApiResponse(
                message="Information retrieved successfully",
                data=user_info.model_dump(),
            )

        except Exception as e:
            logger.error(
                "get_user_info_failed",
                tenant_id=user_info.tenant_id,
                error=str(e),
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve user information",
            )