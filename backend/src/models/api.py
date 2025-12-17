from pydantic import BaseModel


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
