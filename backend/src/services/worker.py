import os
from datetime import datetime

from celery import Celery
from fastapi import Request
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlmodel import Session, and_, select
from typing import Optional
from src import configure_logger, get_logger
from src.backup_destination import BackupDestinationManager
from src.backup_source import BackupManager
from src.base import Credentials
from src.models.api import RestoreBackupRequest
from src.models.db import Destination, Source
from src.models.structs import UserInfo

app = Celery("worker")
app.conf.update(
    broker_url=os.environ["CELERY_BROKER_URL"],
    result_backend=os.environ["CELERY_RESULT_BACKEND"],
    timezone="Europe/Warsaw",
    # Task serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Task settings
    task_track_started=True,
    task_time_limit=3600,
    # Scheduler conf
    beat_scheduler="src.scheduler:DynamicScheduler",
)


DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(DATABASE_URL)
configure_logger(
    engine,
    tenant_id="system",
    service_name="worker"
)

logger = get_logger("worker")
db_session = Session(engine)


@app.task
def create_backup(backup_source_id: int, backup_destination_id: int, tenant_id: str, schedule_id: Optional[int] = None, keep_n: Optional[int] = None):
    logger.info("Starting backup creation", backup_source_id=backup_source_id, backup_destination_id=backup_destination_id, tenant_id=tenant_id)
    
    try:
        statement = select(Destination).where(
            and_(
                Destination.tenant_id == tenant_id,
                Destination.id == backup_destination_id,
            )
        )
        backup_destination = db_session.exec(statement).one()

        statement = select(Source).where(
            and_(Source.tenant_id == tenant_id, Source.id == backup_source_id)
        )
        backup_source = db_session.exec(statement).one()

        backup_manager = BackupManager(
            Credentials(
                url=backup_source.url,
                login=backup_source.login,
                password=backup_source.password,
                api_key=backup_source.api_key,
            )
        ).create_from_type(backup_source.source_type)

        backup_destination_manager = BackupDestinationManager(
            Credentials(
                url=backup_destination.url,
                login=backup_destination.login,
                password=backup_destination.password,
                api_key=backup_destination.api_key,
            )
        ).create_from_type(backup_destination.destination_type)

        local_path = backup_manager.create_backup(tenant_id=tenant_id, backup_source_id=backup_source_id, schedule_id=schedule_id)
        logger.info("Backup created locally", local_path=local_path, tenant_id=tenant_id)

        try:
            remote_path = backup_destination_manager.upload_backup(local_path)
            logger.info("Backup uploaded successfully", remote_path=remote_path, tenant_id=tenant_id)
            
            backups = backup_destination_manager.list_backups()

            # sorted from oldest to newest
            relevant_backups = sorted(filter(lambda backup: backup.source == backup_source.source_type, backups),
                                      key=lambda x: x.modified)
            
            if keep_n:
                for extra_backup in relevant_backups[:-keep_n]:
                    backup_destination_manager.delete_backup(extra_backup.path)
                    logger.info("Deleted old backup", backup_path=extra_backup.path, tenant_id=tenant_id)

            return remote_path

        finally:
            if os.path.exists(local_path):
                os.remove(local_path)
                logger.info("Cleaned up local backup file", local_path=local_path)
    
    except Exception as e:
        logger.error("Backup creation failed", error=str(e), tenant_id=tenant_id, exc_info=True)
        raise


@app.task
def list_backups(backup_destination_id: int, user_info: UserInfo):
    logger.info("Listing backups", backup_destination_id=backup_destination_id, tenant_id=user_info.tenant_id)
    
    try:
        user_info = UserInfo(**user_info)  # ty:ignore[invalid-argument-type]

        statement = select(Destination).where(
            and_(
                Destination.tenant_id == user_info.tenant_id,
                Destination.id == backup_destination_id,
            )
        )
        backup_destination = db_session.exec(statement).one()

        backup_destination_manager = BackupDestinationManager(
            Credentials(
                url=backup_destination.url,
                login=backup_destination.login,
                password=backup_destination.password,
                api_key=backup_destination.api_key,
            )
        ).create_from_type(backup_destination.destination_type)

        backups = backup_destination_manager.list_backups()
        logger.info("Backups listed successfully", count=len(backups), tenant_id=user_info.tenant_id)
        return backups
    
    except Exception as e:
        logger.error("Failed to list backups", error=str(e), tenant_id=user_info.tenant_id, exc_info=True)
        raise


@app.task
def delete_backup(backup_destination_id: int, backup_path: str, user_info: UserInfo):
    logger.info("Deleting backup", backup_destination_id=backup_destination_id, backup_path=backup_path, tenant_id=user_info.tenant_id)
    
    try:
        user_info = UserInfo(**user_info)  # ty:ignore[invalid-argument-type]

        statement = select(Destination).where(
            and_(
                Destination.tenant_id == user_info.tenant_id,
                Destination.id == backup_destination_id,
            )
        )
        backup_destination = db_session.exec(statement).one()

        backup_destination_manager = BackupDestinationManager(
            Credentials(
                url=backup_destination.url,
                login=backup_destination.login,
                password=backup_destination.password,
                api_key=backup_destination.api_key,
            )
        ).create_from_type(backup_destination.destination_type)

        backup_destination_manager.delete_backup(backup_path)
        logger.info("Backup deleted successfully", backup_path=backup_path, tenant_id=user_info.tenant_id)
    
    except Exception as e:
        logger.error("Failed to delete backup", error=str(e), backup_path=backup_path, tenant_id=user_info.tenant_id, exc_info=True)
        raise


@app.task
def restore_from_backup(request: RestoreBackupRequest, user_info: UserInfo):
    logger.info("Starting backup restoration", tenant_id=user_info.tenant_id)
    
    try:
        request = RestoreBackupRequest(**request)  # ty:ignore[invalid-argument-type]
        user_info = UserInfo(**user_info)  # ty:ignore[invalid-argument-type]

        statement = select(Destination).where(
            and_(
                Destination.tenant_id == user_info.tenant_id,
                Destination.id == request.backup_destination_id,
            )
        )
        backup_destination = db_session.exec(statement).one()

        statement = select(Source).where(
            and_(
                Source.tenant_id == user_info.tenant_id,
                Source.id == request.backup_source_id,
            )
        )
        backup_source = db_session.exec(statement).one()

        backup_manager = BackupManager(
            Credentials(
                url=backup_source.url,
                login=backup_source.login,
                password=backup_source.password,
                api_key=backup_source.api_key,
            )
        ).create_from_type(backup_source.source_type)

        backup_destination_manager = BackupDestinationManager(
            Credentials(
                url=backup_destination.url,
                login=backup_destination.login,
                password=backup_destination.password,
                api_key=backup_destination.api_key,
            )
        ).create_from_type(backup_destination.destination_type)

        local_path = backup_destination_manager.get_backup(request.backup_path)
        logger.info("Backup downloaded locally", local_path=local_path, tenant_id=user_info.tenant_id)

        try:
            backup_manager.restore_from_backup(local_path)
            logger.info("Backup restored successfully", tenant_id=user_info.tenant_id)
            return True

        except Exception as e:
            logger.error("Backup restoration failed", error=str(e), tenant_id=user_info.tenant_id, exc_info=True)
            return False

        finally:
            if os.path.exists(local_path):
                os.remove(local_path)
                logger.info("Cleaned up temporary backup file", local_path=local_path)
    
    except Exception as e:
        logger.error("Backup restoration task failed", error=str(e), tenant_id=user_info.tenant_id, exc_info=True)
        raise