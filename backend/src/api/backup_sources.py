from src import configure_logger, get_logger, tenant_context
from sqlalchemy import create_engine
import os
from fastapi.routing import APIRouter
from fastapi import Depends, HTTPException, Query, status
from sqlmodel import select
import sqlmodel
from datetime import datetime
from src.models import *
from src import *
from src.utils import get_db_session, get_user_info
from src.backup_source import BackupManager

engine = create_engine(os.environ["DATABASE_URL"])
configure_logger(engine, service_name="api.backup_sources")
logger = get_logger("api.backup_sources")

router = APIRouter(prefix="/backup-sources", tags=["Backup Source Management"])


@router.post("/add", response_model=ApiResponse)
def add_backup_source(
    request: AddBackupSourceRequest,
    db_session: sqlmodel.Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api"):
        logger.info(
            "add_backup_source_request_received",
            source_type=request.source_type,
            source_name=request.source_name,
        )

        try:
            source = Source(
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
            
            db_session.add(source)
            db_session.commit()

            logger.info(
                "backup_source_added_successfully",
                source_type=request.source_type,
                source_id=source.id,
            )
            return ApiResponse(message="Backup source added successfully")

        except Exception as e:
            logger.error(
                "add_backup_source_failed",
                error=str(e),
                source_type=request.source_type,
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to add backup source",
            )


@router.get("/list", response_model=ApiResponse)
def list_backup_sources(
    db_session: sqlmodel.Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api"):
        logger.info("list_backup_sources_request_received")

        try:
            statement = select(Source).where(Source.tenant_id == user_info.tenant_id)
            all_backup_sources = db_session.exec(statement).all()

            count = len(all_backup_sources)
            logger.info(
                "list_backup_sources_success",
                count=count,
            )

            return ApiResponse(
                message="Backups sources retrieved successfully",
                data={
                    "backup_sources": list(all_backup_sources),
                    "count": count,
                },
            )

        except Exception as e:
            logger.error(
                "list_backup_sources_failed",
                error=str(e),
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve backup sources",
            )


@router.delete("/delete", response_model=ApiResponse)
def delete_backup_source(
    source_id: int = Query(),
    db_session: sqlmodel.Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api"):
        logger.info(
            "delete_backup_source_request_received",
            source_id=source_id,
        )

        statement = select(Source).where(
            Source.id == source_id, Source.tenant_id == user_info.tenant_id
        )
        source = db_session.exec(statement).first()

        if not source:
            logger.warning(
                "delete_backup_source_not_found",
                source_id=source_id,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Backup source not found",
            )

        try:
            db_session.delete(source)
            db_session.commit()

            logger.info(
                "backup_source_deleted_successfully",
                source_id=source_id,
            )
            return ApiResponse(message="Backup source deleted successfully")

        except Exception as e:
            logger.error(
                "delete_backup_source_failed",
                source_id=source_id,
                error=str(e),
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete backup source",
            )


@router.post("/update", response_model=ApiResponse)
def update_backup_source(
    request: UpdateBackupSourceRequest,
    db_session: sqlmodel.Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api"):
        logger.info(
            "update_backup_source_request_received",
            source_id=request.source_id,
        )

        statement = select(Source).where(
            Source.id == request.source_id, Source.tenant_id == user_info.tenant_id
        )
        source = db_session.exec(statement).first()

        if not source:
            logger.warning(
                "update_backup_source_not_found",
                source_id=request.source_id,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Backup source not found",
            )

        try:
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
            db_session.commit()

            logger.info(
                "backup_source_updated_successfully",
                source_id=request.source_id,
            )
            return ApiResponse(message="Backup source updated successfully")

        except Exception as e:
            logger.error(
                "update_backup_source_failed",
                source_id=request.source_id,
                error=str(e),
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update backup source",
            )


@router.get("/test-connection", response_model=ApiResponse)
def test_connection_backup_source(
    source_id: int = Query(),
    db_session: sqlmodel.Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api"):
        logger.info(
            "test_connection_request_received",
            source_id=source_id,
        )

        statement = select(Source).where(
            Source.id == source_id, Source.tenant_id == user_info.tenant_id
        )
        source = db_session.exec(statement).first()

        if not source:
            logger.warning(
                "test_connection_source_not_found",
                source_id=source_id,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Backup source not found",
            )

        try:
            backup_manager = BackupManager(
                credentials=Credentials(
                    url=source.url,
                    login=source.login,
                    password=source.password,
                    api_key=source.api_key,
                )
            ).create_from_type(source.source_type)

            if backup_manager.test_connection():
                logger.info(
                    "test_connection_success",
                    source_id=source_id,
                    source_type=source.source_type,
                )
                return ApiResponse(message="Backup source configuration success")
            else:
                logger.warning(
                    "test_connection_failed",
                    source_id=source_id,
                    source_type=source.source_type,
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Could not reach backup source",
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "test_connection_exception",
                source_id=source_id,
                error=str(e),
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error testing backup source connection",
            )