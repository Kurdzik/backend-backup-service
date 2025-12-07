from fastapi import FastAPI, HTTPException, status, Depends, Query
from src.utils import get_user_info, get_db_session, UserInfo
from pydantic import BaseModel, Field
from typing import Optional, Literal, Union, Any
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
    AuthMiddleware,
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

app.add_middleware(AuthMiddleware)
app.add_middleware(ResponseTimeLoggingMiddleware)
app.add_middleware(SQLAlchemySessionMiddleware, db_session_factory=session)


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
def register(request: RegisterUserRequest,     db_session: Session = Depends(get_db_session),):
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
def login(request: LoginUserRequest,     db_session: Session = Depends(get_db_session),):

    user = db_session.exec(
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
    db_session.add(auth_session)
    db_session.commit()
    db_session.refresh(auth_session)
    session_token = auth_session.token

    return ApiResponse(message="User logged in successfully", data={"session_token":session_token})


@app.post("/api/v1/users/change-password", response_model=ApiResponse)
def reset_password(request: ResetPasswordRequest,     db_session: Session = Depends(get_db_session)):
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
            name=request.source_name if request.source_name else f"{request.source_type} created at: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
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
        message="Backups sources retrieved successfully", data={"backup_sources": list(all_backup_sources)}
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

    backup_manager = BackupManager(credentials=Credentials(url=source.url,
                                                            login=source.login,
                                                            password=source.password,
                                                            api_key=source.api_key)).create_from_type(source.source_type)
    
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
            name=request.destination_name if request.destination_name else f"{request.destination_type} created at: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
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



    backup_destination_manager = BackupDestinationManager(credentials=Credentials(url=destination.url,
                                                            login=destination.login,
                                                            password=destination.password,
                                                            api_key=destination.api_key)).create_from_type(destination.destination_type)
    
    if backup_destination_manager.test_connection():
        return ApiResponse(message="Backup destination configuration success")

    else:
        raise HTTPException(400, detail="Could not reach backup destination")

# / =========== BACKUP DESTINATION ===========
# =========== PERFORMING BACKUPS ===========
from src.base import create_backup, restore_from_backup, list_backups


@app.put("/api/v1/backup/create", response_model=ApiResponse)
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
    ).create_from_type(backup_destination.destination_type)

    remote_path = create_backup(backup_manager, backup_destination_manager)

    return ApiResponse(
        message="Backup created successfully", data={"path": remote_path}
    )


@app.get("/api/v1/backup/list", response_model=ApiResponse)
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
    ).create_from_type(backup_destination.destination_type)

    backups = list_backups(backup_destination_manager)

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
    ).create_from_type(backup_destination.destination_type)

    backup_destination_manager.delete_backup(backup_path)

    return ApiResponse(
        message="Backup deleted successfully")


class RestoreBackupRequest(BaseModel):
    backup_source_id: int
    backup_destination_id: int
    backup_path: str


@app.post("/api/v1/backup/restore", response_model=ApiResponse)
def restore_backup_to_source(
    request: RestoreBackupRequest,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    statement = select(Destination).where(
        and_(
            Destination.tenant_id == user_info.tenant_id,
            Destination.id == request.backup_destination_id,
        )
    )
    backup_destination = db_session.exec(statement).one()

    statement = select(Source).where(
        and_(Source.tenant_id == user_info.tenant_id, Source.id == request.backup_source_id)
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
    ).create_from_type(backup_destination.destination_type)

    restore_from_backup(
        backup_path=request.backup_path,
        backup_manager=backup_manager,
        backup_destination_manager=backup_destination_manager,
    )

    return ApiResponse(message="Backup restored successfully")


# / =========== PERFORMING BACKUPS ===========
