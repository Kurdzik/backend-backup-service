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
from src.backup_destination import BackupDestinationManager

engine = create_engine(os.environ["DATABASE_URL"])
configure_logger(engine, service_name="api")
logger = get_logger("api")

router = APIRouter(prefix="/backup-destinations", tags=["Backup Destination Management"])







@router.post("/add", response_model=ApiResponse)
def add_backup_destination(
    request: AddBackupDestinationRequest,
    db_session: sqlmodel.Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api"):
        try:
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

            logger.info(
                "backup_destination_added", destination_type=request.destination_type
            )
            return ApiResponse(message="Backup destination added successfully")
        except Exception as e:
            logger.error(
                "failed_to_add_backup_destination", error=str(e), exc_info=True
            )
            raise


@router.get("/list", response_model=ApiResponse)
def list_backup_destinations(
    db_session: sqlmodel.Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    statement = select(Destination).where(Destination.tenant_id == user_info.tenant_id)
    all_backup_destinations = db_session.exec(statement).all()

    return ApiResponse(
        message="Backup destinations retrieved successfully",
        data={"backup_destinations": list(all_backup_destinations)},
    )


@router.delete("/delete", response_model=ApiResponse)
def delete_backup_destination(
    destination_id: int = Query(),
    db_session: sqlmodel.Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api"):
        statement = select(Destination).where(
            Destination.id == destination_id,
            Destination.tenant_id == user_info.tenant_id,
        )
        destination = db_session.exec(statement).first()

        if not destination:
            raise HTTPException(status_code=404, detail="Backup destination not found")

        try:
            db_session.delete(destination)
            db_session.commit()
            logger.info("backup_destination_deleted", destination_id=destination_id)
            return ApiResponse(message="Backup destination deleted successfully")
        except Exception as e:
            logger.error(
                "failed_to_delete_backup_destination",
                destination_id=destination_id,
                error=str(e),
                exc_info=True,
            )
            raise


@router.post("/update", response_model=ApiResponse)
def update_backup_destination(
    request: UpdateBackupDestinationRequest,
    db_session: sqlmodel.Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api"):
        statement = select(Destination).where(
            Destination.id == request.destination_id,
            Destination.tenant_id == user_info.tenant_id,
        )
        destination = db_session.exec(statement).first()

        if not destination:
            raise HTTPException(status_code=404, detail="Backup destination not found")

        try:
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

            logger.info(
                "backup_destination_updated", destination_id=request.destination_id
            )
            return ApiResponse(message="Backup destination updated successfully")
        except Exception as e:
            logger.error(
                "failed_to_update_backup_destination",
                destination_id=request.destination_id,
                error=str(e),
                exc_info=True,
            )
            raise


@router.get("/test-connection", response_model=ApiResponse)
def test_connection_backup_destination(
    destination_id: int = Query(),
    db_session: sqlmodel.Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api"):
        statement = select(Destination).where(
            Destination.id == destination_id,
            Destination.tenant_id == user_info.tenant_id,
        )
        destination = db_session.exec(statement).first()

        if not destination:
            raise HTTPException(status_code=404, detail="Backup destination not found")

        try:
            backup_destination_manager = BackupDestinationManager(
                credentials=Credentials(
                    url=destination.url,
                    login=destination.login,
                    password=destination.password,
                    api_key=destination.api_key,
                )
            ).create_from_type(destination.destination_type)

            if backup_destination_manager.test_connection():
                logger.info(
                    "backup_destination_connection_test_success",
                    destination_id=destination_id,
                )
                return ApiResponse(message="Backup destination configuration success")
            else:
                logger.warning(
                    "backup_destination_connection_test_failed",
                    destination_id=destination_id,
                )
                raise HTTPException(400, detail="Could not reach backup destination")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "backup_destination_connection_test_error",
                destination_id=destination_id,
                error=str(e),
                exc_info=True,
            )
            raise HTTPException(
                500, detail="Error testing backup destination connection"
            )
