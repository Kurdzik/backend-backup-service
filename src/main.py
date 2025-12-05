from fastapi import FastAPI, HTTPException, status, Depends, Query
from src.utils import get_user_info, get_db_session, UserInfo
from pydantic import BaseModel
from typing import Optional, Literal
from sqlalchemy import create_engine
from sqlmodel import Session, select, and_
from src.models.db import User, Source, Destination
from src.models.db import Session as AuthSession
import os
from dotenv import load_dotenv
from uuid import uuid4
from fastapi.responses import ORJSONResponse
from datetime import datetime, timedelta
from src.middleware import (
    AuthMiddleWare,
    ResponseTimeLoggingMiddleware,
    SQLAlchemySessionMiddleware,
    session,
)
from src.base import Credentials
from src.backup_destination import BackupDestinationManager
from src.backup_source import BackupManager

load_dotenv()

engine = create_engine(os.environ["DATABASE_URL"])
app = FastAPI(title="Backend", redoc_url=None, default_response_class=ORJSONResponse)

app.add_middleware(AuthMiddleWare)
app.add_middleware(ResponseTimeLoggingMiddleware)
app.add_middleware(SQLAlchemySessionMiddleware, db_session_factory=session)


class ApiResponse(BaseModel):
    message: str
    data: Optional[str] = None


# =========== USER MANAGEMENT ===========
class RegisterUserRequest(BaseModel):
    username: str
    password: str
    password2: str


class LoginUserRequest(BaseModel):
    username: str
    password: str


class ResetPasswordRequest(BaseModel):
    username: str
    old_password: str
    new_password: str
    new_password2: str


@app.post("/api/v1/users/register")
def register(request: RegisterUserRequest):
    if request.password != request.password2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match"
        )

    with Session(engine) as session:
        # Check if user already exists
        existing_user = session.exec(
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
        session.add(user)
        session.commit()
        session.refresh(user)

    return ApiResponse(message="User created successfully", data=None)


@app.post("/api/v1/users/login")
def login(request: LoginUserRequest):
    with Session(engine) as session:
        user = session.exec(
            select(User).where(
                and_(
                    User.username == request.username, User.password == request.password
                )
            )
        ).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Wrong username or password",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled"
            )

        auth_session = AuthSession(
            user_id=user.id,
            ip_address="127.0.0.1",
            user_agent="Mozilla",
            expires_at=datetime.now() + timedelta(days=7),
        )
        session.add(auth_session)
        session.commit()
        session.refresh(auth_session)
        session_token = auth_session.token

    return ApiResponse(message="User logged in successfully", data=session_token)


@app.post("/api/v1/users/reset-password")
def reset_password(request: ResetPasswordRequest):
    if request.new_password != request.new_password2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="New passwords do not match"
        )

    if request.old_password == request.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from old password",
        )

    with Session(engine) as session:
        user = session.exec(
            select(User).where(User.username == request.username)
        ).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        if user.password != request.old_password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Old password is incorrect",
            )

        user.password = request.new_password
        session.add(user)
        session.commit()

    return ApiResponse(message="Password reset successfully", data=None)


# / =========== USER MANAGEMENT ===========
# =========== BACKUP SOURCE ===========


class AddBackupSourceRequest:
    source_type: Literal["vault", "qdrant", "postgres", "elasticsearch"]
    source_name: str
    credentials: Credentials


class DeleteBackupSourceRequest:
    source_id: int


class UpdateBackupSourceRequest:
    source_id: int
    source_name: Optional[str] = None
    credentials: Optional[Credentials] = None


@app.post("/api/v1/backup-sources/add")
def add_backup_source(
    request: AddBackupSourceRequest,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    db_session.add(
        Source(
            tenant_id=user_info.tenant_id,
            name=request.source_name,
            source_type=request.source_type,
            url=request.credentials.url,
            login=request.credentials.login,
            password=request.credentials.password,
            api_key=request.credentials.api_key,
        )
    )

    return ApiResponse(message="Backup source added successfully", data=None)


@app.get("/api/v1/backup-sources/list")
def list_backup_sources(
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    statement = select(Source).where(Source.tenant_id == user_info.tenant_id)
    all_backup_sources = db_session.exec(statement).all()

    return ApiResponse(
        message="Backups sources retrieved successfully", data=list(all_backup_sources)
    )


@app.delete("/api/v1/backup-sources/delete")
def delete_backup_source(
    request: DeleteBackupSourceRequest,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    statement = select(Source).where(
        Source.id == request.source_id, Source.tenant_id == user_info.tenant_id
    )
    source = db_session.exec(statement).first()

    if not source:
        raise HTTPException(status_code=404, detail="Backup source not found")

    db_session.delete(source)
    db_session.commit()

    return ApiResponse(message="Backup source deleted successfully", data=None)


@app.put("/api/v1/backup-sources/update")
def update_backup_source(
    request: UpdateBackupSourceRequest,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    statement = select(Source).where(
        Source.id == request.source_id, Source.tenant_id == user_info.tenant_id
    )
    source = db_session.exec(statement).first()

    if not source:
        raise HTTPException(status_code=404, detail="Backup source not found")

    if request.source_name is not None:
        source.name = request.source_name

    if request.credentials is not None:
        if request.credentials.url is not None:
            source.url = request.credentials.url
        if request.credentials.login is not None:
            source.login = request.credentials.login
        if request.credentials.password is not None:
            source.password = request.credentials.password
        if request.credentials.api_key is not None:
            source.api_key = request.credentials.api_key

    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)

    return ApiResponse(message="Backup source updated successfully", data=source)


# / =========== BACKUP SOURCE ===========
# =========== BACKUP DESTINATION ===========
class AddBackupDestinationRequest:
    source_type: Literal["s3", "local_fs", "sftp"]
    source_name: str
    credentials: Credentials
    config: dict[str, str]


class DeleteBackupDestinationRequest:
    destination_id: int


class UpdateBackupDestinationRequest:
    destination_id: int
    source_name: Optional[str] = None
    credentials: Optional[Credentials] = None
    config: Optional[dict[str, str]] = None


@app.post("/api/v1/backup-destinations/add")
def add_backup_destination(
    request: AddBackupDestinationRequest,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    db_session.add(
        Destination(
            tenant_id=user_info.tenant_id,
            name=request.source_name,
            destination_type=request.source_type,
            url=request.credentials.url,
            login=request.credentials.login,
            password=request.credentials.password,
            api_key=request.credentials.api_key,
            config=request.config,
        )
    )
    db_session.commit()

    return ApiResponse(message="Backup destination added successfully", data=None)


@app.get("/api/v1/backup-destinations/list")
def list_backup_destinations(
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    statement = select(Destination).where(Destination.tenant_id == user_info.tenant_id)
    all_backup_destinations = db_session.exec(statement).all()

    return ApiResponse(
        message="Backup destinations retrieved successfully",
        data=list(all_backup_destinations),
    )


@app.delete("/api/v1/backup-destinations/delete")
def delete_backup_destination(
    request: DeleteBackupDestinationRequest,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    statement = select(Destination).where(
        Destination.id == request.destination_id,
        Destination.tenant_id == user_info.tenant_id,
    )
    destination = db_session.exec(statement).first()

    if not destination:
        raise HTTPException(status_code=404, detail="Backup destination not found")

    db_session.delete(destination)
    db_session.commit()

    return ApiResponse(message="Backup destination deleted successfully", data=None)


@app.put("/api/v1/backup-destinations/update")
def update_backup_destination(
    request: UpdateBackupDestinationRequest,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    statement = select(Destination).where(
        Destination.id == request.destination_id,
        Destination.tenant_id == user_info.tenant_id,
    )
    destination = db_session.exec(statement).first()

    if not destination:
        raise HTTPException(status_code=404, detail="Backup destination not found")

    if request.source_name is not None:
        destination.name = request.source_name

    if request.credentials is not None:
        if request.credentials.url is not None:
            destination.url = request.credentials.url
        if request.credentials.login is not None:
            destination.login = request.credentials.login
        if request.credentials.password is not None:
            destination.password = request.credentials.password
        if request.credentials.api_key is not None:
            destination.api_key = request.credentials.api_key

    if request.config is not None:
        destination.config = request.config

    db_session.add(destination)
    db_session.commit()
    db_session.refresh(destination)

    return ApiResponse(
        message="Backup destination updated successfully", data=destination
    )


# / =========== BACKUP DESTINATION ===========
# =========== PERFORMING BACKUPS ===========
from src.base import create_backup, restore_from_backup, list_backups


@app.put("/api/v1/backup/create")
def create_backup_from_source(
    backup_source_id: int = Query(),
    backup_destination_id: int = Query(),
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    statement = select(Destination).where(
        and_(
            Destination.tenant_id == user_info.tenant_id,
            Destination.id == backup_destination_id,
        )
    )
    backup_destination = db_session.exec(statement).one()

    statement = select(Source).where(
        and_(Source.tenant_id == user_info.tenant_id, Source.id == backup_source_id)
    )
    backup_source = db_session.exec(statement).one()

    backup_manager = BackupManager(
        Credentials(
            url=backup_source.url,
            login=backup_source.login,
            password=backup_source.password,
            api_key=backup_source.api_key,
        )
    ).create_from_type(backup_source.source_type)
    backup_destination_manager = BackupDestinationManager(
        Credentials(
            url=backup_destination.url,
            login=backup_destination.login,
            password=backup_destination.password,
            api_key=backup_destination.api_key,
        )
    ).create_from_type(backup_destination.source_type)

    remote_path = create_backup(backup_manager, backup_destination_manager)

    return ApiResponse(
        message="Backup created successfully", data={"path": remote_path}
    )


@app.get("/api/v1/backup/list")
def list_backups_from_destination(
    backup_destination_id: int = Query(),
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    statement = select(Destination).where(
        and_(
            Destination.tenant_id == user_info.tenant_id,
            Destination.id == backup_destination_id,
        )
    )
    backup_destination = db_session.exec(statement).one()

    backup_destination_manager = BackupDestinationManager(
        Credentials(
            url=backup_destination.url,
            login=backup_destination.login,
            password=backup_destination.password,
            api_key=backup_destination.api_key,
        )
    ).create_from_type(backup_destination.source_type)

    backups = list_backups(backup_destination_manager)

    return ApiResponse(
        message="Backups retrieved successfully",
        data={
            "backups": [backup.model_dump() for backup in backups],
            "count": len(backups),
        },
    )


@app.delete("/api/v1/backup/delete")
def delete_backup_from_destination(
    backup_destination_id: int = Query(),
    backup_path: str = Query(),
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    statement = select(Destination).where(
        and_(
            Destination.tenant_id == user_info.tenant_id,
            Destination.id == backup_destination_id,
        )
    )
    backup_destination = db_session.exec(statement).one()

    backup_destination_manager = BackupDestinationManager(
        Credentials(
            url=backup_destination.url,
            login=backup_destination.login,
            password=backup_destination.password,
            api_key=backup_destination.api_key,
        )
    ).create_from_type(backup_destination.source_type)

    backup_destination_manager.delete_backup(backup_path)

    return ApiResponse(
        message="Backup deleted successfully", data={"path": backup_path}
    )


@app.post("/api/v1/backup/restore")
def restore_backup_to_source(
    backup_source_id: int = Query(),
    backup_destination_id: int = Query(),
    backup_path: str = Query(),
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    statement = select(Destination).where(
        and_(
            Destination.tenant_id == user_info.tenant_id,
            Destination.id == backup_destination_id,
        )
    )
    backup_destination = db_session.exec(statement).one()

    statement = select(Source).where(
        and_(Source.tenant_id == user_info.tenant_id, Source.id == backup_source_id)
    )
    backup_source = db_session.exec(statement).one()

    backup_manager = BackupManager(
        Credentials(
            url=backup_source.url,
            login=backup_source.login,
            password=backup_source.password,
            api_key=backup_source.api_key,
        )
    ).create_from_type(backup_source.source_type)

    backup_destination_manager = BackupDestinationManager(
        Credentials(
            url=backup_destination.url,
            login=backup_destination.login,
            password=backup_destination.password,
            api_key=backup_destination.api_key,
        )
    ).create_from_type(backup_destination.source_type)

    restore_from_backup(
        backup_path=backup_path,
        backup_manager=backup_manager,
        backup_destination_manager=backup_destination_manager,
        backup_destination=backup_source.url,
    )

    return ApiResponse(
        message="Backup restored successfully", data={"path": backup_path}
    )


# / =========== PERFORMING BACKUPS ===========
