import hashlib
import os
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import Depends, HTTPException, status
from fastapi.routing import APIRouter
from sqlalchemy import create_engine
from sqlmodel import select
import sqlmodel
from src import configure_logger, get_logger, tenant_context
from src.backup_schedule_manager import notify_scheduler_reload
from src.crypto import encrypt_str, hash_password, verify_password
from src.models import (
    ApiResponse,
    LoginUserRequest,
    RegisterUserRequest,
    ResetPasswordRequest,
    SaveEncryptionKeyRequest,
    TenantBackupSettings,
    TenantEncryptionKey,
    TenantLogSettings,
    UpdateUserSettingsRequest,
    User,
    UserInfo,
)
from src.models import Session as AuthSession
from src.utils import get_db_session, get_user_info

engine = create_engine(os.environ["DATABASE_URL"])
configure_logger(engine, service_name="api.user_management")
logger = get_logger("api.user_management")

router = APIRouter(prefix="/users", tags=["User Management"])


def _get_or_create_log_settings(
    db_session: sqlmodel.Session, tenant_id: str
) -> TenantLogSettings:
    settings = db_session.exec(
        select(TenantLogSettings).where(TenantLogSettings.tenant_id == tenant_id)
    ).first()
    if settings:
        return settings

    settings = TenantLogSettings(tenant_id=tenant_id)
    db_session.add(settings)
    db_session.commit()
    db_session.refresh(settings)
    return settings


def _get_or_create_backup_settings(
    db_session: sqlmodel.Session, tenant_id: str
) -> TenantBackupSettings:
    settings = db_session.exec(
        select(TenantBackupSettings).where(TenantBackupSettings.tenant_id == tenant_id)
    ).first()
    if settings:
        return settings

    settings = TenantBackupSettings(tenant_id=tenant_id)
    db_session.add(settings)
    db_session.commit()
    db_session.refresh(settings)
    return settings


def _settings_payload(
    log_settings: TenantLogSettings,
    backup_settings: TenantBackupSettings,
    encryption_key: TenantEncryptionKey | None,
) -> dict:
    return {
        "log_retention_period_d": log_settings.log_retention_period_d,
        "log_size": log_settings.log_size,
        "compression_enabled": backup_settings.compression_enabled,
        "encryption_enabled": backup_settings.encryption_enabled,
        "encryption_key_configured": encryption_key is not None,
        "key_fingerprint": encryption_key.key_fingerprint if encryption_key else None,
        "gotify_enabled": backup_settings.gotify_enabled,
        "gotify_url": backup_settings.gotify_url,
        "gotify_token_configured": bool(backup_settings.gotify_token),
    }


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

        hashed_password = hash_password(request.password)

        tenant_id = str(uuid4())
        user = User(
            tenant_id=tenant_id,
            username=request.username,
            password=hashed_password,
            is_active=True,
        )
        db_session.add(user)
        db_session.add(TenantLogSettings(tenant_id=tenant_id))
        db_session.add(TenantBackupSettings(tenant_id=tenant_id))
        db_session.commit()
        db_session.refresh(user)
        notify_scheduler_reload()

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
            select(User).where(User.username == request.username)
        ).first()

        if not user:
            logger.warning(
                "login_failed",
                username=request.username,
                reason="user_not_found",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Wrong username or password",
            )

        if not verify_password(request.password, user.password):
            logger.warning(
                "login_failed",
                username=request.username,
                reason="invalid_password",
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

        if not verify_password(request.old_password, user.password):
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

        user.password = hash_password(request.new_password)
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
def get_current_user_info(
    db_session: sqlmodel.Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.user_management"):
        logger.info(
            "get_user_info_request_received",
            tenant_id=user_info.tenant_id,
            user_id=user_info.user_id,
        )

        try:
            user = db_session.exec(select(User).where(User.id == user_info.user_id)).first()
            log_settings = _get_or_create_log_settings(db_session, user_info.tenant_id)
            backup_settings = _get_or_create_backup_settings(db_session, user_info.tenant_id)
            encryption_key = db_session.exec(
                select(TenantEncryptionKey).where(
                    TenantEncryptionKey.tenant_id == user_info.tenant_id
                )
            ).first()
            logger.info(
                "user_info_retrieved_successfully",
                tenant_id=user_info.tenant_id,
                user_id=user_info.user_id,
            )

            return ApiResponse(
                message="Information retrieved successfully",
                data={
                    **user_info.model_dump(),
                    "username": user.username if user else None,
                    "settings": _settings_payload(
                        log_settings, backup_settings, encryption_key
                    ),
                },
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


@router.get("/settings", response_model=ApiResponse)
def get_user_settings(
    db_session: sqlmodel.Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.user_management"):
        log_settings = _get_or_create_log_settings(db_session, user_info.tenant_id)
        backup_settings = _get_or_create_backup_settings(db_session, user_info.tenant_id)
        encryption_key = db_session.exec(
            select(TenantEncryptionKey).where(
                TenantEncryptionKey.tenant_id == user_info.tenant_id
            )
        ).first()

        return ApiResponse(
            message="Settings retrieved successfully",
            data={"settings": _settings_payload(log_settings, backup_settings, encryption_key)},
        )


@router.post("/settings", response_model=ApiResponse)
def update_user_settings(
    request: UpdateUserSettingsRequest,
    db_session: sqlmodel.Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.user_management"):
        log_settings = _get_or_create_log_settings(db_session, user_info.tenant_id)
        backup_settings = _get_or_create_backup_settings(db_session, user_info.tenant_id)
        encryption_key = db_session.exec(
            select(TenantEncryptionKey).where(
                TenantEncryptionKey.tenant_id == user_info.tenant_id
            )
        ).first()

        if request.gotify_enabled:
            if not request.gotify_url:
                raise HTTPException(status_code=400, detail="Gotify URL is required")
            if not request.gotify_token and not backup_settings.gotify_token:
                raise HTTPException(status_code=400, detail="Gotify token is required")

        if request.encryption_enabled and not encryption_key:
            raise HTTPException(status_code=400, detail="Encryption key must be generated first")

        log_settings.log_retention_period_d = request.log_retention_period_d
        log_settings.log_size = request.log_size
        log_settings.updated_at = datetime.now()

        backup_settings.compression_enabled = request.compression_enabled
        backup_settings.encryption_enabled = request.encryption_enabled
        backup_settings.gotify_enabled = request.gotify_enabled
        backup_settings.gotify_url = request.gotify_url if request.gotify_enabled else None
        if request.gotify_token:
            backup_settings.gotify_token = encrypt_str(request.gotify_token)
        backup_settings.updated_at = datetime.now()

        db_session.add(log_settings)
        db_session.add(backup_settings)
        db_session.commit()

        notify_scheduler_reload()
        logger.info("user_settings_updated", persist_db=True)

        return ApiResponse(message="Settings updated successfully")


@router.post("/encryption-key", response_model=ApiResponse)
def save_encryption_key(
    request: SaveEncryptionKeyRequest,
    db_session: sqlmodel.Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.user_management"):
        public_key = request.public_key.strip()
        if "BEGIN PUBLIC KEY" not in public_key:
            raise HTTPException(status_code=400, detail="Invalid public key")

        fingerprint = hashlib.sha256(public_key.encode("utf-8")).hexdigest()
        encryption_key = db_session.exec(
            select(TenantEncryptionKey).where(
                TenantEncryptionKey.tenant_id == user_info.tenant_id
            )
        ).first()

        if encryption_key:
            encryption_key.public_key = public_key
            encryption_key.key_fingerprint = fingerprint
            encryption_key.updated_at = datetime.now()
        else:
            encryption_key = TenantEncryptionKey(
                tenant_id=user_info.tenant_id,
                public_key=public_key,
                key_fingerprint=fingerprint,
            )

        db_session.add(encryption_key)
        db_session.commit()
        logger.info("tenant_encryption_key_saved", key_fingerprint=fingerprint, persist_db=True)

        return ApiResponse(
            message="Encryption public key saved successfully",
            data={"key_fingerprint": fingerprint},
        )
