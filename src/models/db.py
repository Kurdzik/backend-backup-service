from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
import uuid


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(index=True)
    username: str = Field(unique=True, index=True)
    password: str
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class Session(SQLModel, table=True):
    __tablename__ = "sessions"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    token: str = Field(
        unique=True, index=True, default_factory=lambda: f"ust-{str(uuid.uuid4()).replace("-","")}"
    )
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.now)


class Source(SQLModel, table=True):
    __tablename__ = "backup_sources"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(index=True)
    name: str = Field(index=True)
    source_type: str  # postgres, qdrant, vault, elasticsearch
    url: str
    login: Optional[str] = None
    password: Optional[str] = None
    api_key: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class Destination(SQLModel, table=True):
    __tablename__ = "backup_destinations"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(index=True)
    name: str = Field(index=True)
    destination_type: str  # local_fs, s3, sftp
    url: str
    login: Optional[str] = None
    password: Optional[str] = None
    api_key: Optional[str] = None
    config: Optional[str] = None  # JSON string for additional config
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class Schedule(SQLModel, table=True):
    __tablename__ = "backup_schedules"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(index=True)
    name: str = Field(index=True)
    source_id: int = Field(foreign_key="backup_sources.id")
    destination_id: int = Field(foreign_key="backup_destinations.id")
    keep_n: int  # The number of backups to keep
    schedule: str  # Cron expression or schedule format
    is_active: bool = Field(default=True)
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
