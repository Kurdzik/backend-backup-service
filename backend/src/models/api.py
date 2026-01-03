from pydantic import BaseModel
from typing import Any, Optional, Literal
from pydantic import Field
from src.models import Credentials


class ApiResponse(BaseModel):
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    detail: str


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


class CreateScheduleBackupRequest(BaseModel):
    schedule_name: str
    backup_source_id: int
    backup_destination_id: int
    backup_schedule: str
    keep_n: int


class RestoreBackupRequest(BaseModel):
    backup_source_id: int
    backup_destination_id: int
    backup_path: str


class AddBackupSourceRequest(BaseModel):
    source_type: Literal["vault", "qdrant", "postgres", "elasticsearch"]
    source_name: Optional[str] = None
    credentials: Credentials


class UpdateBackupSourceRequest(BaseModel):
    source_id: int
    source_name: Optional[str] = None
    credentials: Optional[Credentials] = None


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


class CreateScheduleBackupRequest(BaseModel):
    schedule_name: str
    backup_source_id: int
    backup_destination_id: int
    backup_schedule: str
    keep_n: int


class UpdateScheduleBackupRequest(BaseModel):
    schedule_id: int
    schedule_name: str
    backup_source_id: int
    backup_destination_id: int
    backup_schedule: str
    is_active: bool
    keep_n: int
