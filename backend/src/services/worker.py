import os

from celery import Celery
from sqlalchemy import create_engine
from sqlmodel import Session, and_, select
from typing import Optional
from src import configure_logger, get_logger, tenant_context
from src.backup_destination import BackupDestinationManager
from src.backup_source import BackupManager
from src.base import Credentials
from src.models import UserInfo, Destination, Source, RestoreBackupRequest
from src.crypto import decrypt_str

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
    beat_scheduler="src.services.scheduler:DynamicScheduler",
)


DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(DATABASE_URL)
configure_logger(engine, service_name="worker")
logger = get_logger("worker")

db_session = Session(engine)


def _decrypt_credentials(
    source_or_destination, 
    entity_type: str, 
    entity_id: int
) -> Credentials:
    """
    Helper function to decrypt credentials from Source or Destination objects.
    
    Args:
        source_or_destination: Source or Destination object with encrypted credentials
        entity_type: String describing the entity type for logging (e.g., "source", "destination")
        entity_id: ID of the entity for logging
    
    Returns:
        Credentials object with decrypted password and api_key
    """
    decrypted_password = None
    if source_or_destination.password:
        try:
            decrypted_password = decrypt_str(source_or_destination.password)
        except ValueError as e:
            logger.error(
                f"{entity_type}_password_decryption_failed",
                entity_id=entity_id,
                error=str(e)
            )
            raise ValueError(f"Failed to decrypt {entity_type} password")
    
    decrypted_api_key = None
    if source_or_destination.api_key:
        try:
            decrypted_api_key = decrypt_str(source_or_destination.api_key)
        except ValueError as e:
            logger.error(
                f"{entity_type}_api_key_decryption_failed",
                entity_id=entity_id,
                error=str(e)
            )
            raise ValueError(f"Failed to decrypt {entity_type} API key")
    
    return Credentials(
        url=source_or_destination.url,
        login=source_or_destination.login,
        password=decrypted_password,
        api_key=decrypted_api_key,
    )


@app.task
def create_backup(
    backup_source_id: int,
    backup_destination_id: int,
    tenant_id: str,
    schedule_id: Optional[int] = None,
    keep_n: Optional[int] = None,
):
    with tenant_context(tenant_id=tenant_id, service_name="worker"):
        logger.info(
            "backup_started",
            backup_source_id=backup_source_id,
            backup_destination_id=backup_destination_id,
            schedule_id=schedule_id,
        )

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

            source_credentials = _decrypt_credentials(
                backup_source, 
                "source", 
                backup_source_id
            )
            
            backup_manager = BackupManager(source_credentials).create_from_type(
                backup_source.source_type
            )

            destination_credentials = _decrypt_credentials(
                backup_destination,
                "destination",
                backup_destination_id
            )
            
            backup_destination_manager = BackupDestinationManager(
                destination_credentials
            ).create_from_type(backup_destination.destination_type)

            logger.info("creating_local_backup", source_type=backup_source.source_type)
            local_path = backup_manager.create_backup(
                tenant_id=tenant_id,
                backup_source_id=backup_source_id,
                schedule_id=schedule_id,
            )

            try:
                logger.info("uploading_backup", local_path=local_path)
                remote_path = backup_destination_manager.upload_backup(local_path)

                backups = backup_destination_manager.list_backups()

                relevant_backups = sorted(
                    filter(
                        lambda backup: backup.source == backup_source.source_type,
                        backups,
                    ),
                    key=lambda x: x.modified,
                )

                if keep_n:
                    deleted_count = 0
                    for extra_backup in relevant_backups[:-keep_n]:
                        backup_destination_manager.delete_backup(extra_backup.path)
                        deleted_count += 1

                    if deleted_count > 0:
                        logger.info(
                            "old_backups_deleted", count=deleted_count, keep_n=keep_n
                        )

                logger.info("backup_completed", remote_path=remote_path)
                return remote_path

            finally:
                if os.path.exists(local_path):
                    os.remove(local_path)
                    logger.info("local_backup_cleaned", local_path=local_path)

        except ValueError as e:
            logger.error("backup_failed_decryption_error", error=str(e), exc_info=True)
            raise
        except Exception as e:
            logger.error("backup_failed", error=str(e), exc_info=True)
            raise


@app.task
def list_backups(backup_destination_id: int, user_info: UserInfo):
    user_info = UserInfo(**user_info)  # type:ignore[arg-type]

    with tenant_context(tenant_id=user_info.tenant_id, service_name="worker"):
        logger.info("listing_backups", backup_destination_id=backup_destination_id)

        try:
            statement = select(Destination).where(
                and_(
                    Destination.tenant_id == user_info.tenant_id,
                    Destination.id == backup_destination_id,
                )
            )
            backup_destination = db_session.exec(statement).one()

            destination_credentials = _decrypt_credentials(
                backup_destination,
                "destination",
                backup_destination_id
            )
            
            backup_destination_manager = BackupDestinationManager(
                destination_credentials
            ).create_from_type(backup_destination.destination_type)

            backups = backup_destination_manager.list_backups()
            logger.info("backups_listed", count=len(backups))
            return backups

        except ValueError as e:
            logger.error("list_backups_failed_decryption_error", error=str(e), exc_info=True)
            raise
        except Exception as e:
            logger.error("list_backups_failed", error=str(e), exc_info=True)
            raise


@app.task
def delete_backup(backup_destination_id: int, backup_path: str, user_info: UserInfo):
    user_info = UserInfo(**user_info)  # type:ignore[arg-type]

    with tenant_context(tenant_id=user_info.tenant_id, service_name="worker"):
        logger.info(
            "deleting_backup",
            backup_destination_id=backup_destination_id,
            backup_path=backup_path,
        )

        try:
            statement = select(Destination).where(
                and_(
                    Destination.tenant_id == user_info.tenant_id,
                    Destination.id == backup_destination_id,
                )
            )
            backup_destination = db_session.exec(statement).one()

            destination_credentials = _decrypt_credentials(
                backup_destination,
                "destination",
                backup_destination_id
            )
            
            backup_destination_manager = BackupDestinationManager(
                destination_credentials
            ).create_from_type(backup_destination.destination_type)

            backup_destination_manager.delete_backup(backup_path)
            logger.info("backup_deleted", backup_path=backup_path)

        except ValueError as e:
            logger.error("delete_backup_failed_decryption_error", error=str(e), exc_info=True)
            raise
        except Exception as e:
            logger.error("delete_backup_failed", error=str(e), exc_info=True)
            raise


@app.task
def restore_from_backup(request: RestoreBackupRequest, user_info: UserInfo):
    request = RestoreBackupRequest(**request)  # type:ignore[arg-type]
    user_info = UserInfo(**user_info)  # type:ignore[arg-type]

    with tenant_context(tenant_id=user_info.tenant_id, service_name="worker"):
        logger.info(
            "restore_started",
            backup_source_id=request.backup_source_id,
            backup_destination_id=request.backup_destination_id,
            backup_path=request.backup_path,
        )

        try:
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

            source_credentials = _decrypt_credentials(
                backup_source,
                "source",
                request.backup_source_id
            )
            
            backup_manager = BackupManager(source_credentials).create_from_type(
                backup_source.source_type
            )

            destination_credentials = _decrypt_credentials(
                backup_destination,
                "destination",
                request.backup_destination_id
            )
            
            backup_destination_manager = BackupDestinationManager(
                destination_credentials
            ).create_from_type(backup_destination.destination_type)

            logger.info("downloading_backup", backup_path=request.backup_path)
            local_path = backup_destination_manager.get_backup(request.backup_path)

            try:
                logger.info("restoring_backup", local_path=local_path)
                backup_manager.restore_from_backup(local_path)
                logger.info("restore_completed")
                return True

            except Exception as e:
                logger.error("restore_failed", error=str(e), exc_info=True)
                return False

            finally:
                if os.path.exists(local_path):
                    os.remove(local_path)
                    logger.info("local_backup_cleaned", local_path=local_path)

        except ValueError as e:
            logger.error("restore_task_failed_decryption_error", error=str(e), exc_info=True)
            return False
        except Exception as e:
            logger.error("restore_task_failed", error=str(e), exc_info=True)
            return False