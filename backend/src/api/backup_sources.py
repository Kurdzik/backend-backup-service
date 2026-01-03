from src import configure_logger, get_logger
from sqlalchemy import create_engine
import os
from fastapi.routing import APIRouter
from fastapi import Depends, HTTPException, Query
from sqlmodel import select
import sqlmodel
from datetime import datetime
from src.models import *
from src import *
from src.utils import get_db_session, get_user_info
from src.backup_source import BackupManager

engine = create_engine(os.environ["DATABASE_URL"])
configure_logger(engine, service_name="api")
logger = get_logger("api")

router = APIRouter(prefix="/backup-sources", tags=["Backup Source Management"])


@router.post("/add", response_model=ApiResponse)
def add_backup_source(
    request: AddBackupSourceRequest,
    db_session: sqlmodel.Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api"):
        try:
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

            logger.info("backup_source_added", source_type=request.source_type)
            return ApiResponse(message="Backup source added successfully")
        except Exception as e:
            logger.error("failed_to_add_backup_source", error=str(e), exc_info=True)
            raise


@router.get("/list", response_model=ApiResponse)
def list_backup_sources(
    db_session: sqlmodel.Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    statement = select(Source).where(Source.tenant_id == user_info.tenant_id)
    all_backup_sources = db_session.exec(statement).all()

    return ApiResponse(
        message="Backups sources retrieved successfully",
        data={"backup_sources": list(all_backup_sources)},
    )


@router.delete("/delete", response_model=ApiResponse)
def delete_backup_source(
    source_id: int = Query(),
    db_session: sqlmodel.Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api"):
        statement = select(Source).where(
            Source.id == source_id, Source.tenant_id == user_info.tenant_id
        )
        source = db_session.exec(statement).first()

        if not source:
            raise HTTPException(status_code=404, detail="Backup source not found")

        try:
            db_session.delete(source)
            db_session.commit()
            logger.info("backup_source_deleted", source_id=source_id)
            return ApiResponse(message="Backup source deleted successfully")
        except Exception as e:
            logger.error(
                "failed_to_delete_backup_source",
                source_id=source_id,
                error=str(e),
                exc_info=True,
            )
            raise


@router.post("/update", response_model=ApiResponse)
def update_backup_source(
    request: UpdateBackupSourceRequest,
    db_session: sqlmodel.Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api"):
        statement = select(Source).where(
            Source.id == request.source_id, Source.tenant_id == user_info.tenant_id
        )
        source = db_session.exec(statement).first()

        if not source:
            raise HTTPException(status_code=404, detail="Backup source not found")

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
            logger.info("backup_source_updated", source_id=request.source_id)
            return ApiResponse(message="Backup source updated successfully")
        except Exception as e:
            logger.error(
                "failed_to_update_backup_source",
                source_id=request.source_id,
                error=str(e),
                exc_info=True,
            )
            raise


@router.get("/test-connection", response_model=ApiResponse)
def test_connection_backup_source(
    source_id: int = Query(),
    db_session: sqlmodel.Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api"):
        statement = select(Source).where(
            Source.id == source_id, Source.tenant_id == user_info.tenant_id
        )
        source = db_session.exec(statement).first()

        if not source:
            raise HTTPException(status_code=404, detail="Backup source not found")

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
                    "backup_source_connection_test_success", source_id=source_id
                )
                return ApiResponse(message="Backup source configuration success")
            else:
                logger.warning(
                    "backup_source_connection_test_failed", source_id=source_id
                )
                raise HTTPException(400, detail="Could not reach backup source")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "backup_source_connection_test_error",
                source_id=source_id,
                error=str(e),
                exc_info=True,
            )
            raise HTTPException(500, detail="Error testing backup source connection")
