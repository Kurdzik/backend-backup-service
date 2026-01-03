from src import configure_logger, get_logger
from sqlalchemy import create_engine
import os
from fastapi.routing import APIRouter
from fastapi import Depends, Query
import sqlmodel
from datetime import datetime
from src.models import *
from src import *
from src.utils import get_db_session, get_user_info
from src.backup_schedule_manager import ScheduleManager

engine = create_engine(os.environ["DATABASE_URL"])
configure_logger(engine, service_name="api")
logger = get_logger("api")

router = APIRouter(prefix="/backup-schedules", tags=["Backup Schedule Management"])


@router.post("/add", response_model=ApiResponse)
def add_backup_schedule(
    request: CreateScheduleBackupRequest,
    db_session: sqlmodel.Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api"):
        try:
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

            logger.info(
                "backup_schedule_added",
                backup_source_id=request.backup_source_id,
                backup_destination_id=request.backup_destination_id,
                schedule=request.backup_schedule,
            )

            return ApiResponse(message="Backup schedule added successfully")
        except Exception as e:
            logger.error("failed_to_add_backup_schedule", error=str(e), exc_info=True)
            raise


@router.delete("/delete", response_model=ApiResponse)
def delete_backup_schedule(
    schedule_id: int = Query(),
    db_session: sqlmodel.Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api"):
        try:
            schedule_manager = ScheduleManager(db_session)
            schedule_manager.delete_schedule(schedule_id, user_info.tenant_id)

            logger.info("backup_schedule_deleted", schedule_id=schedule_id)
            return ApiResponse(message="Backup schedule deleted successfully")
        except Exception as e:
            logger.error(
                "failed_to_delete_backup_schedule",
                schedule_id=schedule_id,
                error=str(e),
                exc_info=True,
            )
            raise


@router.post("/update", response_model=ApiResponse)
def update_backup_schedules(
    request: UpdateScheduleBackupRequest,
    db_session: sqlmodel.Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api"):
        try:
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

            logger.info("backup_schedule_updated", schedule_id=request.schedule_id)
            return ApiResponse(message="Backup schedule added successfully")
        except Exception as e:
            logger.error(
                "failed_to_update_backup_schedule",
                schedule_id=request.schedule_id,
                error=str(e),
                exc_info=True,
            )
            raise


@router.get("/list", response_model=ApiResponse)
def list_backup_schedules(
    db_session: sqlmodel.Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    schedule_manager = ScheduleManager(db_session)

    schedules = schedule_manager.list_schedules(tenant_id=user_info.tenant_id)

    return ApiResponse(
        message="Backup schedules retrieved successfully",
        data={"backup_schedules": schedules},
    )
