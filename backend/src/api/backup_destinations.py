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
from src.backup_destination import BackupDestinationManager

# Setup Logger
engine = create_engine(os.environ["DATABASE_URL"])
configure_logger(engine, service_name="api.backup_destinations")
logger = get_logger("api.backup_destinations")

router = APIRouter(
    prefix="/backup-destinations", tags=["Backup Destination Management"]
)


@router.post("/add", response_model=ApiResponse)
def add_backup_destination(
    request: AddBackupDestinationRequest,
    db_session: sqlmodel.Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api"):
        logger.info(
            "add_destination_request_received",
            destination_type=request.destination_type,
            destination_name=request.destination_name
        )
        
        try:
            new_destination = Destination(
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
            
            db_session.add(new_destination)
            db_session.commit()
            db_session.refresh(new_destination)

            logger.info(
                "backup_destination_created", 
                destination_id=new_destination.id,
                destination_type=request.destination_type
            )
            return ApiResponse(message="Backup destination added successfully")

        except Exception as e:
            logger.error(
                "failed_to_add_backup_destination", 
                error=str(e), 
                destination_type=request.destination_type,
                exc_info=True
            )
            raise


@router.get("/list", response_model=ApiResponse)
def list_backup_destinations(
    db_session: sqlmodel.Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api"):
        logger.info("list_destinations_request_received")
        
        try:
            statement = select(Destination).where(Destination.tenant_id == user_info.tenant_id)
            all_backup_destinations = db_session.exec(statement).all()
            
            count = len(all_backup_destinations)
            logger.info("list_destinations_success", count=count)

            return ApiResponse(
                message="Backup destinations retrieved successfully",
                data={"backup_destinations": list(all_backup_destinations)},
            )
        except Exception as e:
            logger.error("list_destinations_failed", error=str(e), exc_info=True)
            raise


@router.delete("/delete", response_model=ApiResponse)
def delete_backup_destination(
    destination_id: int = Query(),
    db_session: sqlmodel.Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api"):
        logger.info("delete_destination_request_received", destination_id=destination_id)

        try:
            statement = select(Destination).where(
                Destination.id == destination_id,
                Destination.tenant_id == user_info.tenant_id,
            )
            destination = db_session.exec(statement).first()

            if not destination:
                logger.warning("delete_destination_not_found", destination_id=destination_id)
                raise HTTPException(status_code=404, detail="Backup destination not found")

            db_session.delete(destination)
            db_session.commit()
            
            logger.info("backup_destination_deleted", destination_id=destination_id)
            return ApiResponse(message="Backup destination deleted successfully")

        except HTTPException:
            raise
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
        logger.info("update_destination_request_received", destination_id=request.destination_id)

        try:
            statement = select(Destination).where(
                Destination.id == request.destination_id,
                Destination.tenant_id == user_info.tenant_id,
            )
            destination = db_session.exec(statement).first()

            if not destination:
                logger.warning("update_destination_not_found", destination_id=request.destination_id)
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
                destination.config = request.config  # type: ignore[invalid-assignment]

            db_session.add(destination)
            db_session.commit()
            db_session.refresh(destination)

            logger.info(
                "backup_destination_updated", 
                destination_id=request.destination_id
            )
            return ApiResponse(message="Backup destination updated successfully")

        except HTTPException:
            raise
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
        logger.info("test_connection_request_received", destination_id=destination_id)

        try:
            statement = select(Destination).where(
                Destination.id == destination_id,
                Destination.tenant_id == user_info.tenant_id,
            )
            destination = db_session.exec(statement).first()

            if not destination:
                logger.warning("test_connection_destination_not_found", destination_id=destination_id)
                raise HTTPException(status_code=404, detail="Backup destination not found")

            backup_destination_manager = BackupDestinationManager(
                credentials=Credentials(
                    url=destination.url,
                    login=destination.login,
                    password=destination.password,
                    api_key=destination.api_key,
                )
            ).create_from_type(destination.destination_type)

            logger.info("initiating_connection_test", destination_id=destination_id, type=destination.destination_type)

            if backup_destination_manager.test_connection():
                logger.info(
                    "connection_test_success",
                    destination_id=destination_id,
                )
                return ApiResponse(message="Backup destination configuration success")
            else:
                logger.warning(
                    "connection_test_failed_destination_rejected",
                    destination_id=destination_id,
                )
                raise HTTPException(400, detail="Could not reach backup destination")

        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "connection_test_exception",
                destination_id=destination_id,
                error=str(e),
                exc_info=True,
            )
            raise HTTPException(
                500, detail="Error testing backup destination connection"
            )