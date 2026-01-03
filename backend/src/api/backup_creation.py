from src import configure_logger, get_logger
from sqlalchemy import create_engine
import os
from fastapi.routing import APIRouter
from fastapi import Depends, HTTPException, Query, status
from src.models import *
from src import *
from src.utils import get_user_info
from src.services.worker import (
    create_backup,
    list_backups,
    restore_from_backup,
    delete_backup,
)

engine = create_engine(os.environ["DATABASE_URL"])
configure_logger(engine, service_name="api")
logger = get_logger("api")

router = APIRouter(prefix="/backup", tags=["Backups Management"])


@router.put("/create", response_model=ApiResponse)
def create_backup_from_source(
    backup_source_id: int = Query(),
    backup_destination_id: int = Query(),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api"):
        logger.info(
            "backup_creation_queued",
            backup_source_id=backup_source_id,
            backup_destination_id=backup_destination_id,
        )

        create_backup.apply_async(
            kwargs={
                "backup_source_id": backup_source_id,
                "backup_destination_id": backup_destination_id,
                "tenant_id": user_info.tenant_id,
            },
            ignore_result=True,
        )

        return ApiResponse(message="Backup is being created")


@router.get("/list", response_model=ApiResponse)
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


@router.delete("/delete", response_model=ApiResponse)
def delete_backup_from_destination(
    backup_destination_id: int = Query(),
    backup_path: str = Query(),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api"):
        logger.info(
            "backup_deletion_queued",
            backup_destination_id=backup_destination_id,
            backup_path=backup_path,
        )

        delete_backup.apply_async(
            kwargs={
                "backup_destination_id": backup_destination_id,
                "backup_path": backup_path,
                "user_info": user_info.model_dump(),
            },
            ignore_result=True,
        )

        return ApiResponse(message="Backup deleted successfully")


@router.post("/restore", response_model=ApiResponse)
def restore_backup_to_source(
    request: RestoreBackupRequest,
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api"):
        logger.info(
            "restore_queued",
            backup_source_id=request.backup_source_id,
            backup_destination_id=request.backup_destination_id,
        )

        try:
            result = restore_from_backup.apply_async(
                kwargs={
                    "request": request.model_dump(),
                    "user_info": user_info.model_dump(),
                },
                ignore_result=False,
            )

            result = result.get()

            if result:
                logger.info("restore_completed")
                return ApiResponse(message="Backup restored successfully")
            else:
                logger.error("restore_failed_at_source")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Source could not be restored from backup",
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error("restore_task_error", error=str(e), exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to restore backup",
            )
