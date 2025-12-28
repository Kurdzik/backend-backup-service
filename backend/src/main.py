import os
from datetime import datetime, timedelta
from typing import Any, Literal, Optional
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import create_engine
from sqlmodel import Session, and_, select

from src import configure_logger
from src.backup_destination import BackupDestinationManager
from src.backup_schedule_manager import ScheduleManager
from src.backup_source import BackupManager
from src.base import Credentials
from src.middleware import (
    AuthMiddleware,
    ResponseTimeLoggingMiddleware,
    SQLAlchemySessionMiddleware,
    session,
)
from src.models.api import RestoreBackupRequest
from src.models.db import Destination
from src.models.db import Session as AuthSession
from src.models.db import Source, User
from src.utils import UserInfo, get_db_session, get_user_info
from src.worker import create_backup, delete_backup, list_backups, restore_from_backup
from fastapi.middleware.cors import CORSMiddleware


load_dotenv()
configure_logger()

engine = create_engine(os.environ["DATABASE_URL"])
app = FastAPI(title="Backend", redoc_url=None, default_response_class=ORJSONResponse)

app.add_middleware(AuthMiddleware)  # ty:ignore[invalid-argument-type]
app.add_middleware(ResponseTimeLoggingMiddleware)  # ty:ignore[invalid-argument-type]
app.add_middleware(SQLAlchemySessionMiddleware, db_session_factory=session)  # ty:ignore[invalid-argument-type]
app.add_middleware(
    CORSMiddleware,  # ty:ignore[invalid-argument-type]
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ApiResponse(BaseModel):
    message: str
    data: dict[str, Any] = Field(default_factory=dict)



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


@app.post("/api/v1/users/register", response_model=ApiResponse)
def register(
    request: RegisterUserRequest,
    db_session: Session = Depends(get_db_session),
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

    return ApiResponse(message="User created successfully")


@app.post("/api/v1/users/login", response_model=ApiResponse)
def login(
    request: LoginUserRequest,
    db_session: Session = Depends(get_db_session),
):
    user = db_session.exec(
        select(User).where(
            and_(User.username == request.username, User.password == request.password)
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
    db_session.add(auth_session)
    db_session.commit()
    db_session.refresh(auth_session)
    session_token = auth_session.token

    return ApiResponse(
        message="User logged in successfully", data={"session_token": session_token}
    )


@app.post("/api/v1/users/change-password", response_model=ApiResponse)
def reset_password(
    request: ResetPasswordRequest, db_session: Session = Depends(get_db_session)
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Old password is incorrect",
        )

    user.password = request.new_password
    db_session.add(user)

    return ApiResponse(message="Password reset successfully")


@app.get("/api/v1/users/get-info", response_model=ApiResponse)
def get_current_user_info(user_info: UserInfo = Depends(get_user_info)):
    return ApiResponse(
        message="Information retrieved successfully", data=user_info.model_dump()
    )


# / =========== USER MANAGEMENT ===========
# =========== BACKUP SOURCE ===========


class AddBackupSourceRequest(BaseModel):
    source_type: Literal["vault", "qdrant", "postgres", "elasticsearch"]
    source_name: Optional[str] = None
    credentials: Credentials


class UpdateBackupSourceRequest(BaseModel):
    source_id: int
    source_name: Optional[str] = None
    credentials: Optional[Credentials] = None


@app.post("/api/v1/backup-sources/add", response_model=ApiResponse)
def add_backup_source(
    request: AddBackupSourceRequest,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    db_session.add(
        Source(
            tenant_id=user_info.tenant_id,
            name=request.source_name
            if request.source_name
            else f"{request.source_type} created at: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            source_type=request.source_type,
            url=request.credentials.url,
            login=request.credentials.login,
            password=request.credentials.password,
            api_key=request.credentials.api_key,
        )
    )

    return ApiResponse(message="Backup source added successfully")


@app.get("/api/v1/backup-sources/list", response_model=ApiResponse)
def list_backup_sources(
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    statement = select(Source).where(Source.tenant_id == user_info.tenant_id)
    all_backup_sources = db_session.exec(statement).all()

    return ApiResponse(
        message="Backups sources retrieved successfully",
        data={"backup_sources": list(all_backup_sources)},
    )


@app.delete("/api/v1/backup-sources/delete", response_model=ApiResponse)
def delete_backup_source(
    source_id: int = Query(),
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    statement = select(Source).where(
        Source.id == source_id, Source.tenant_id == user_info.tenant_id
    )
    source = db_session.exec(statement).first()

    if not source:
        raise HTTPException(status_code=404, detail="Backup source not found")

    db_session.delete(source)
    db_session.commit()

    return ApiResponse(message="Backup source deleted successfully")


@app.post("/api/v1/backup-sources/update", response_model=ApiResponse)
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

    db_session.merge(source)
    # db_session.commit()
    # db_session.refresh(source)

    return ApiResponse(message="Backup source updated successfully")


@app.get("/api/v1/backup-sources/test-connection", response_model=ApiResponse)
def test_connection_backup_source(
    source_id: int = Query(),
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    statement = select(Source).where(
        Source.id == source_id, Source.tenant_id == user_info.tenant_id
    )
    source = db_session.exec(statement).first()

    if not source:
        raise HTTPException(status_code=404, detail="Backup source not found")

    backup_manager = BackupManager(
        credentials=Credentials(
            url=source.url,
            login=source.login,
            password=source.password,
            api_key=source.api_key,
        )
    ).create_from_type(source.source_type)

    if backup_manager.test_connection():
        return ApiResponse(message="Backup source configuration success")

    else:
        raise HTTPException(400, detail="Could not reach backup source")


# / =========== BACKUP SOURCE ===========
# =========== BACKUP DESTINATION ===========
class AddBackupDestinationRequest(BaseModel):
    destination_type: Literal["s3", "local_fs", "sftp"]
    destination_name: Optional[str] = None
    credentials: Credentials
    config: Optional[dict[str, str]] = None


class UpdateBackupDestinationRequest(BaseModel):
    destination_id: int
    destination_name: Optional[str] = None
    credentials: Optional[Credentials] = None
    config: Optional[dict[str, str]] = None


@app.post("/api/v1/backup-destinations/add", response_model=ApiResponse)
def add_backup_destination(
    request: AddBackupDestinationRequest,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    db_session.add(
        Destination(
            tenant_id=user_info.tenant_id,
            name=request.destination_name
            if request.destination_name
            else f"{request.destination_type} created at: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            destination_type=request.destination_type,
            url=request.credentials.url,
            login=request.credentials.login,
            password=request.credentials.password,
            api_key=request.credentials.api_key,
            config=request.config,
        )
    )

    return ApiResponse(message="Backup destination added successfully")


@app.get("/api/v1/backup-destinations/list", response_model=ApiResponse)
def list_backup_destinations(
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    statement = select(Destination).where(Destination.tenant_id == user_info.tenant_id)
    all_backup_destinations = db_session.exec(statement).all()

    return ApiResponse(
        message="Backup destinations retrieved successfully",
        data={"backup_destinations": list(all_backup_destinations)},
    )


@app.delete("/api/v1/backup-destinations/delete", response_model=ApiResponse)
def delete_backup_destination(
    destination_id: int = Query(),
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    statement = select(Destination).where(
        Destination.id == destination_id,
        Destination.tenant_id == user_info.tenant_id,
    )
    destination = db_session.exec(statement).first()

    if not destination:
        raise HTTPException(status_code=404, detail="Backup destination not found")

    db_session.delete(destination)
    db_session.commit()

    return ApiResponse(message="Backup destination deleted successfully")


@app.post("/api/v1/backup-destinations/update", response_model=ApiResponse)
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

    if request.destination_name is not None:
        destination.name = request.destination_name

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

    return ApiResponse(message="Backup destination updated successfully")


@app.get("/api/v1/backup-destinations/test-connection", response_model=ApiResponse)
def test_connection_backup_destination(
    destination_id: int = Query(),
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    statement = select(Destination).where(
        Destination.id == destination_id,
        Destination.tenant_id == user_info.tenant_id,
    )
    destination = db_session.exec(statement).first()

    if not destination:
        raise HTTPException(status_code=404, detail="Backup destination not found")

    backup_destination_manager = BackupDestinationManager(
        credentials=Credentials(
            url=destination.url,
            login=destination.login,
            password=destination.password,
            api_key=destination.api_key,
        )
    ).create_from_type(destination.destination_type)

    if backup_destination_manager.test_connection():
        return ApiResponse(message="Backup destination configuration success")

    else:
        raise HTTPException(400, detail="Could not reach backup destination")


# / =========== BACKUP DESTINATION ===========
# =========== PERFORMING BACKUPS ===========


@app.put("/api/v1/backup/create", response_model=ApiResponse)
def create_backup_from_source(
    backup_source_id: int = Query(),
    backup_destination_id: int = Query(),
    user_info: UserInfo = Depends(get_user_info),
):
    create_backup.apply_async(
        kwargs={
            "backup_source_id": backup_source_id,
            "backup_destination_id": backup_destination_id,
            "tenant_id": user_info.tenant_id,
        },
        ignore_result=True,
    )

    return ApiResponse(message="Backup is being created")


@app.get("/api/v1/backup/list", response_model=ApiResponse)
def list_backups_from_destination(
    backup_destination_id: int = Query(),
    user_info: UserInfo = Depends(get_user_info),
):
    result = list_backups.apply_async(
        kwargs={
            "backup_destination_id": backup_destination_id,
            "user_info": user_info.model_dump(),
        },
        ignore_result=False,
    )
    backups = result.get()

    return ApiResponse(
        message="Backups retrieved successfully",
        data={
            "backups": list(backups),
            "count": len(backups),
        },
    )


@app.delete("/api/v1/backup/delete", response_model=ApiResponse)
def delete_backup_from_destination(
    backup_destination_id: int = Query(),
    backup_path: str = Query(),
    user_info: UserInfo = Depends(get_user_info),
):
    delete_backup.apply_async(
        kwargs={
            "backup_destination_id": backup_destination_id,
            "backup_path": backup_path,
            "user_info": user_info.model_dump(),
        },
        ignore_result=True,
    )

    return ApiResponse(message="Backup deleted successfully")


@app.post("/api/v1/backup/restore", response_model=ApiResponse)
def restore_backup_to_source(
    request: RestoreBackupRequest,
    user_info: UserInfo = Depends(get_user_info),
):
    result = restore_from_backup.apply_async(
        kwargs={"request": request.model_dump(), "user_info": user_info.model_dump()},
        ignore_result=False,
    )

    result = result.get()

    if result:
        return ApiResponse(message="Backup restored successfully")

    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Source could not be restored from backup",
        )


# / =========== PERFORMING BACKUPS ===========
# =========== SCHEDULING BACKUPS ===========


class CreateScheduleBackupRequest(BaseModel):
    schedule_name: str
    backup_source_id: int
    backup_destination_id: int
    backup_schedule: str
    keep_n: int


@app.post("/api/v1/backup-schedules/add", response_model=ApiResponse)
def add_backup_schedule(
    request: CreateScheduleBackupRequest,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    schedule_manager = ScheduleManager(db_session)

    schedule_manager.create_schedule(
        tenant_id=user_info.tenant_id,
        name=request.schedule_name
        if request.schedule_name
        else f"Schedule created at: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        source_id=request.backup_source_id,
        destination_id=request.backup_destination_id,
        keep_n=request.keep_n,
        schedule=request.backup_schedule,
        is_active=True,
    )

    return ApiResponse(message="Backup schedule added successfully")


@app.delete("/api/v1/backup-schedules/delete", response_model=ApiResponse)
def delete_backup_schedule(
    schedule_id: int = Query(),
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    schedule_manager = ScheduleManager(db_session)
    schedule_manager.delete_schedule(schedule_id, user_info.tenant_id)

    return ApiResponse(message="Backup schedule deleted successfully")


class UpdateScheduleBackupRequest(BaseModel):
    schedule_id: int
    schedule_name: str
    backup_source_id: int
    backup_destination_id: int
    backup_schedule: str
    is_active: bool
    keep_n: int

@app.post("/api/v1/backup-schedules/update", response_model=ApiResponse)
def update_backup_schedules(
    request: UpdateScheduleBackupRequest,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    schedule_manager = ScheduleManager(db_session)

    old_schedule = schedule_manager.get_schedule(
        schedule_id=request.schedule_id, tenant_id=user_info.tenant_id
    )

    schedule_manager.update_schedule(
        schedule_id=request.schedule_id,
        tenant_id=user_info.tenant_id,
        name=request.schedule_name,
        source_id=request.backup_source_id,
        destination_id=request.backup_destination_id,
        keep_n=request.keep_n,
        is_active=request.is_active,
    )

    return ApiResponse(message="Backup schedule added successfully")


@app.get("/api/v1/backup-schedules/list", response_model=ApiResponse)
def list_backup_schedules(
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    schedule_manager = ScheduleManager(db_session)

    schedules = schedule_manager.list_schedules(tenant_id=user_info.tenant_id)

    return ApiResponse(message="Backup schedules retrieved successfully", data={"backup_schedules":schedules})


# / =========== SCHEDULING BACKUPS ===========
