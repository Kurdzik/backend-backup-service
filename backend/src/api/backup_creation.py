from src import configure_logger, get_logger, tenant_context
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
configure_logger(engine, service_name="api.backup_management")
logger = get_logger("api.backup_management")

router = APIRouter(prefix="/backup", tags=["Backups Management"])


@router.put("/create", response_model=ApiResponse)
def create_backup_from_source(
    backup_source_id: int = Query(),
    backup_destination_id: int = Query(),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api"):
        logger.info(
            "create_backup_request_received",
            backup_source_id=backup_source_id,
            backup_destination_id=backup_destination_id,
        )

        try:
            task = create_backup.apply_async(
                kwargs={
                    "backup_source_id": backup_source_id,
                    "backup_destination_id": backup_destination_id,
                    "tenant_id": user_info.tenant_id,
                },
                ignore_result=True,
            )
            
            logger.info(
                "create_backup_task_queued",
                task_id=task.id,
                backup_source_id=backup_source_id
            )

            return ApiResponse(message="Backup is being created")

        except Exception as e:
            logger.error(
                "create_backup_failed",
                error=str(e),
                backup_source_id=backup_source_id,
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to queue backup creation",
            )


@router.get("/list", response_model=ApiResponse)
def list_backups_from_destination(
    backup_destination_id: int = Query(),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api"):
        logger.info(
            "list_backups_request_received",
            backup_destination_id=backup_destination_id
        )

        try:
            task = list_backups.apply_async(
                kwargs={
                    "backup_destination_id": backup_destination_id,
                    "user_info": user_info.model_dump(),
                },
                ignore_result=False,
            )
            
            logger.info("list_backups_task_queued", task_id=task.id)

            backups = task.get()
            
            count = len(backups) if backups else 0
            logger.info(
                "list_backups_success",
                count=count,
                backup_destination_id=backup_destination_id
            )

            return ApiResponse(
                message="Backups retrieved successfully",
                data={
                    "backups": list(backups),
                    "count": count,
                },
            )

        except Exception as e:
            logger.error(
                "list_backups_failed",
                error=str(e),
                backup_destination_id=backup_destination_id,
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve backups",
            )


@router.delete("/delete", response_model=ApiResponse)
def delete_backup_from_destination(
    backup_destination_id: int = Query(),
    backup_path: str = Query(),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api"):
        logger.info(
            "delete_backup_request_received",
            backup_destination_id=backup_destination_id,
            backup_path=backup_path,
        )

        try:
            task = delete_backup.apply_async(
                kwargs={
                    "backup_destination_id": backup_destination_id,
                    "backup_path": backup_path,
                    "user_info": user_info.model_dump(),
                },
                ignore_result=True,
            )

            logger.info(
                "delete_backup_task_queued",
                task_id=task.id,
                backup_path=backup_path
            )

            return ApiResponse(message="Backup deleted successfully")

        except Exception as e:
            logger.error(
                "delete_backup_failed",
                error=str(e),
                backup_path=backup_path,
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete backup",
            )


@router.post("/restore", response_model=ApiResponse)
def restore_backup_to_source(
    request: RestoreBackupRequest,
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api"):
        logger.info(
            "restore_backup_request_received",
            backup_source_id=request.backup_source_id,
            backup_destination_id=request.backup_destination_id,
        )

        try:
            task = restore_from_backup.apply_async(
                kwargs={
                    "request": request.model_dump(),
                    "user_info": user_info.model_dump(),
                },
                ignore_result=False,
            )
            
            logger.info("restore_task_queued", task_id=task.id)

            result = task.get()

            if result:
                logger.info(
                    "restore_process_completed_successfully",
                    backup_source_id=request.backup_source_id
                )
                return ApiResponse(message="Backup restored successfully")
            else:
                logger.error(
                    "restore_process_returned_failure",
                    backup_source_id=request.backup_source_id,
                    result=result
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Source could not be restored from backup",
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "restore_backup_exception",
                error=str(e),
                backup_source_id=request.backup_source_id,
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to restore backup",
            )