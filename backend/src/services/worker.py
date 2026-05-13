import os
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional

from celery import Celery, current_task
from celery.exceptions import Retry, SoftTimeLimitExceeded
from sqlalchemy import create_engine, delete, func, text
from sqlmodel import Session, and_, select
from src import configure_logger, get_logger, log_context, tenant_context
from src.backup_artifacts import (
    compress_file,
    decompress_file,
    decrypt_file,
    encrypt_file,
    is_encrypted_file,
    is_gzip_file,
)
from src.backup_destination import BackupDestinationManager
from src.backup_source import BackupManager
from src.base import Credentials
from src.models import (
    Destination,
    Logs,
    RestoreBackupRequest,
    Schedule,
    Source,
    TenantBackupSettings,
    TenantEncryptionKey,
    UserInfo,
)
from src.crypto import decrypt_str
import httpx

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
    task_soft_time_limit=3540,
    worker_hijack_root_logger=False,
    # Scheduler conf
    beat_scheduler="src.services.scheduler:DynamicScheduler",
)


DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(DATABASE_URL)
configure_logger(engine, service_name="worker")
logger = get_logger("worker")

db_session = Session(engine)

BACKUP_MAX_RETRIES = 3
TENANT_JOB_CONCURRENCY = 2


def _log_backup_stage(stage: str, **kwargs) -> None:
    logger.info("backup_stage", stage=stage, persist_db=True, **kwargs)


def _log_restore_stage(stage: str, **kwargs) -> None:
    logger.info("restore_stage", stage=stage, persist_db=True, **kwargs)


def _current_task_id() -> Optional[str]:
    task = current_task
    return task.request.id if task and task.request else None


def _get_tenant_backup_settings(tenant_id: str) -> TenantBackupSettings:
    settings = db_session.exec(
        select(TenantBackupSettings).where(TenantBackupSettings.tenant_id == tenant_id)
    ).first()
    if settings:
        return settings

    settings = TenantBackupSettings(tenant_id=tenant_id)
    db_session.add(settings)
    db_session.commit()
    db_session.refresh(settings)
    return settings


def _get_tenant_encryption_key(tenant_id: str) -> Optional[TenantEncryptionKey]:
    return db_session.exec(
        select(TenantEncryptionKey).where(TenantEncryptionKey.tenant_id == tenant_id)
    ).first()


@contextmanager
def _tenant_job_slot(tenant_id: str):
    lock_conn = engine.connect()
    acquired_key = None
    try:
        for slot in range(TENANT_JOB_CONCURRENCY):
            key = f"backup-service:{tenant_id}:{slot}"
            acquired = lock_conn.execute(
                text("SELECT pg_try_advisory_lock(hashtext(:key))"), {"key": key}
            ).scalar()
            if acquired:
                acquired_key = key
                break

        yield acquired_key is not None
    finally:
        if acquired_key:
            lock_conn.execute(
                text("SELECT pg_advisory_unlock(hashtext(:key))"), {"key": acquired_key}
            )
        lock_conn.close()


def _notify_gotify(
    tenant_id: str,
    title: str,
    message: str,
    priority: int = 5,
) -> None:
    settings = _get_tenant_backup_settings(tenant_id)
    if not settings.gotify_enabled or not settings.gotify_url or not settings.gotify_token:
        return

    try:
        token = decrypt_str(settings.gotify_token)
        url = settings.gotify_url.rstrip("/")
        httpx.post(
            f"{url}/message",
            params={"token": token},
            json={"title": title, "message": message, "priority": priority},
            timeout=10,
        ).raise_for_status()
    except Exception as e:
        logger.warning("gotify_notification_failed", error=str(e))


def _remove_local_paths(paths: list[str]) -> None:
    for path in dict.fromkeys(paths):
        if path and os.path.exists(path):
            os.remove(path)


def _retry_backup_task(self, exc: Exception):
    if self.request.retries < BACKUP_MAX_RETRIES:
        countdown = 60 * (self.request.retries + 1)
        raise self.retry(exc=exc, countdown=countdown)
    raise exc


def _mark_schedule_last_run(schedule_id: Optional[int], tenant_id: str) -> None:
    if schedule_id is None:
        return

    _log_backup_stage("schedule_last_run_update_started")
    schedule = db_session.exec(
        select(Schedule).where(
            and_(Schedule.id == schedule_id, Schedule.tenant_id == tenant_id)
        )
    ).first()

    if not schedule:
        _log_backup_stage("schedule_last_run_update_skipped", reason="schedule_not_found")
        return

    schedule.last_run = datetime.now()
    schedule.updated_at = datetime.now()
    db_session.add(schedule)
    db_session.commit()
    _log_backup_stage("schedule_last_run_update_completed")


def _decrypt_credentials(
    source_or_destination, entity_type: str, entity_id: int
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
                error=str(e),
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
                error=str(e),
            )
            raise ValueError(f"Failed to decrypt {entity_type} API key")

    return Credentials(
        url=source_or_destination.url,
        login=source_or_destination.login,
        password=decrypted_password,
        api_key=decrypted_api_key,
    )


@app.task(bind=True, max_retries=BACKUP_MAX_RETRIES, soft_time_limit=3540, time_limit=3600)
def create_backup(
    self,
    backup_source_id: int,
    backup_destination_id: int,
    tenant_id: str,
    schedule_id: Optional[int] = None,
    keep_n: Optional[int] = None,
    triggered_by: Optional[str] = None,
):
    trigger_type = triggered_by or ("scheduled" if schedule_id is not None else "manual")
    with tenant_context(tenant_id=tenant_id, service_name="worker"), log_context(
        backup_operation="create_backup",
        backup_source_id=backup_source_id,
        backup_destination_id=backup_destination_id,
        schedule_id=schedule_id,
        trigger_type=trigger_type,
        task_id=_current_task_id(),
    ):
        _log_backup_stage("started")
        local_paths: list[str] = []

        try:
            with _tenant_job_slot(tenant_id) as slot_acquired:
                if not slot_acquired:
                    _log_backup_stage("concurrency_limit_reached", limit=TENANT_JOB_CONCURRENCY)
                    raise self.retry(countdown=60)

                _mark_schedule_last_run(schedule_id, tenant_id)
                tenant_settings = _get_tenant_backup_settings(tenant_id)

                _log_backup_stage("destination_lookup_started")
                statement = select(Destination).where(
                    and_(
                        Destination.tenant_id == tenant_id,
                        Destination.id == backup_destination_id,
                    )
                )
                backup_destination = db_session.exec(statement).one()
                _log_backup_stage(
                    "destination_lookup_completed",
                    destination_type=backup_destination.destination_type,
                    destination_name=backup_destination.name,
                )

                _log_backup_stage("source_lookup_started")
                statement = select(Source).where(
                    and_(Source.tenant_id == tenant_id, Source.id == backup_source_id)
                )
                backup_source = db_session.exec(statement).one()
                _log_backup_stage(
                    "source_lookup_completed",
                    source_type=backup_source.source_type,
                    source_name=backup_source.name,
                )

                _log_backup_stage("source_credentials_decryption_started")
                source_credentials = _decrypt_credentials(
                    backup_source, "source", backup_source_id
                )
                _log_backup_stage("source_credentials_decryption_completed")

                _log_backup_stage("source_manager_initialization_started")
                backup_manager = BackupManager(source_credentials).create_from_type(
                    backup_source.source_type
                )
                _log_backup_stage("source_manager_initialization_completed")

                _log_backup_stage("destination_credentials_decryption_started")
                destination_credentials = _decrypt_credentials(
                    backup_destination, "destination", backup_destination_id
                )
                _log_backup_stage("destination_credentials_decryption_completed")

                _log_backup_stage("destination_manager_initialization_started")
                backup_destination_manager = BackupDestinationManager(
                    destination_credentials
                ).create_from_type(backup_destination.destination_type)
                _log_backup_stage("destination_manager_initialization_completed")

                _log_backup_stage("local_backup_creation_started", source_type=backup_source.source_type)
                local_path = backup_manager.create_backup(
                    tenant_id=tenant_id,
                    backup_source_id=backup_source_id,
                    schedule_id=schedule_id,
                )
                local_paths.append(local_path)
                local_size = os.path.getsize(local_path) if os.path.exists(local_path) else None
                _log_backup_stage(
                    "local_backup_creation_completed",
                    local_path=local_path,
                    local_size=local_size,
                )

                artifact_path = local_path
                if tenant_settings.compression_enabled:
                    _log_backup_stage("compression_started", local_path=artifact_path)
                    artifact_path = compress_file(artifact_path)
                    local_paths.append(artifact_path)
                    _log_backup_stage("compression_completed", local_path=artifact_path)

                if tenant_settings.encryption_enabled:
                    encryption_key = _get_tenant_encryption_key(tenant_id)
                    if not encryption_key:
                        raise ValueError("Encryption is enabled but no public key is configured")
                    _log_backup_stage("encryption_started", key_fingerprint=encryption_key.key_fingerprint)
                    artifact_path = encrypt_file(artifact_path, encryption_key.public_key)
                    local_paths.append(artifact_path)
                    _log_backup_stage("encryption_completed", local_path=artifact_path)

                _log_backup_stage("upload_started", local_path=artifact_path)
                remote_path = backup_destination_manager.upload_backup(artifact_path)
                _log_backup_stage("upload_completed", remote_path=remote_path)

                _log_backup_stage("retention_listing_started")
                backups = backup_destination_manager.list_backups()
                _log_backup_stage("retention_listing_completed", backup_count=len(backups))

                relevant_backups = sorted(
                    filter(
                        lambda backup: backup.source == backup_source.source_type,
                        backups,
                    ),
                    key=lambda x: x.modified,
                )

                if keep_n:
                    _log_backup_stage("retention_cleanup_started", keep_n=keep_n)
                    deleted_count = 0
                    for extra_backup in relevant_backups[:-keep_n]:
                        backup_destination_manager.delete_backup(extra_backup.path)
                        deleted_count += 1
                        _log_backup_stage(
                            "retention_backup_deleted",
                            backup_path=extra_backup.path,
                            deleted_count=deleted_count,
                        )

                    _log_backup_stage(
                        "retention_cleanup_completed", deleted_count=deleted_count, keep_n=keep_n
                    )
                else:
                    _log_backup_stage("retention_cleanup_skipped", reason="keep_n_not_set")

                _log_backup_stage("completed", remote_path=remote_path)
                return remote_path

        except SoftTimeLimitExceeded as e:
            logger.error("backup_timeout", persist_db=True, exc_info=True)
            _notify_gotify(tenant_id, "Backup failed", "Backup exceeded the 1 hour timeout")
            raise e
        except Retry:
            raise
        except ValueError as e:
            logger.error("backup_failed_decryption_error", error=str(e), persist_db=True, exc_info=True)
            if self.request.retries < BACKUP_MAX_RETRIES:
                _retry_backup_task(self, e)
            _notify_gotify(tenant_id, "Backup failed", str(e))
            raise
        except Exception as e:
            logger.error("backup_failed", error=str(e), persist_db=True, exc_info=True)
            if self.request.retries < BACKUP_MAX_RETRIES:
                _retry_backup_task(self, e)
            _notify_gotify(tenant_id, "Backup failed", str(e))
            raise
        finally:
            if local_paths:
                _log_backup_stage("local_cleanup_started")
                _remove_local_paths(local_paths)
                _log_backup_stage("local_cleanup_completed")


@app.task
def cleanup_old_logs(
    tenant_id: str,
    log_retention_period_d: int,
    log_size: int,
):
    with tenant_context(tenant_id=tenant_id, service_name="worker"), log_context(
        maintenance_operation="cleanup_old_logs",
        task_id=_current_task_id(),
    ):
        logger.info(
            "log_cleanup_started",
            log_retention_period_d=log_retention_period_d,
            log_size=log_size,
            persist_db=True,
        )
        cutoff = datetime.now() - timedelta(days=log_retention_period_d)

        old_result = db_session.execute(
            delete(Logs).where(
                and_(Logs.tenant_id == tenant_id, Logs.timestamp < cutoff)
            )
        )
        deleted_old = old_result.rowcount or 0
        db_session.commit()

        remaining_count = db_session.exec(
            select(func.count(Logs.id)).where(Logs.tenant_id == tenant_id)
        ).one()
        deleted_excess = 0

        if remaining_count > log_size:
            excess_count = remaining_count - log_size
            excess_ids = (
                select(Logs.id)
                .where(Logs.tenant_id == tenant_id)
                .order_by(Logs.timestamp.asc())
                .limit(excess_count)
            )
            excess_result = db_session.execute(
                delete(Logs).where(Logs.id.in_(excess_ids))
            )
            deleted_excess = excess_result.rowcount or 0
            db_session.commit()

        logger.info(
            "log_cleanup_completed",
            deleted_old=deleted_old,
            deleted_excess=deleted_excess,
            persist_db=True,
        )
        return {"deleted_old": deleted_old, "deleted_excess": deleted_excess}


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
                backup_destination, "destination", backup_destination_id
            )

            backup_destination_manager = BackupDestinationManager(
                destination_credentials
            ).create_from_type(backup_destination.destination_type)

            backups = backup_destination_manager.list_backups()
            logger.info("backups_listed", count=len(backups))
            return backups

        except ValueError as e:
            logger.error(
                "list_backups_failed_decryption_error", error=str(e), exc_info=True
            )
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
                backup_destination, "destination", backup_destination_id
            )

            backup_destination_manager = BackupDestinationManager(
                destination_credentials
            ).create_from_type(backup_destination.destination_type)

            backup_destination_manager.delete_backup(backup_path)
            logger.info("backup_deleted", backup_path=backup_path)

        except ValueError as e:
            logger.error(
                "delete_backup_failed_decryption_error", error=str(e), exc_info=True
            )
            raise
        except Exception as e:
            logger.error("delete_backup_failed", error=str(e), exc_info=True)
            raise


@app.task(bind=True)
def restore_from_backup(self, request: RestoreBackupRequest, user_info: UserInfo):
    request = RestoreBackupRequest(**request)  # type:ignore[arg-type]
    user_info = UserInfo(**user_info)  # type:ignore[arg-type]

    with tenant_context(tenant_id=user_info.tenant_id, service_name="worker"), log_context(
        backup_operation="restore_backup",
        backup_source_id=request.backup_source_id,
        backup_destination_id=request.backup_destination_id,
        backup_path=request.backup_path,
        trigger_type="manual",
        task_id=_current_task_id(),
    ):
        _log_restore_stage("started")
        local_paths: list[str] = []

        try:
            with _tenant_job_slot(user_info.tenant_id) as slot_acquired:
                if not slot_acquired:
                    _log_restore_stage("concurrency_limit_reached", limit=TENANT_JOB_CONCURRENCY)
                    raise self.retry(countdown=60)

                _log_restore_stage("destination_lookup_started")
                statement = select(Destination).where(
                    and_(
                        Destination.tenant_id == user_info.tenant_id,
                        Destination.id == request.backup_destination_id,
                    )
                )
                backup_destination = db_session.exec(statement).one()
                _log_restore_stage(
                    "destination_lookup_completed",
                    destination_type=backup_destination.destination_type,
                    destination_name=backup_destination.name,
                )

                _log_restore_stage("source_lookup_started")
                statement = select(Source).where(
                    and_(
                        Source.tenant_id == user_info.tenant_id,
                        Source.id == request.backup_source_id,
                    )
                )
                backup_source = db_session.exec(statement).one()
                _log_restore_stage(
                    "source_lookup_completed",
                    source_type=backup_source.source_type,
                    source_name=backup_source.name,
                )

                _log_restore_stage("source_credentials_decryption_started")
                source_credentials = _decrypt_credentials(
                    backup_source, "source", request.backup_source_id
                )
                _log_restore_stage("source_credentials_decryption_completed")

                _log_restore_stage("source_manager_initialization_started")
                backup_manager = BackupManager(source_credentials).create_from_type(
                    backup_source.source_type
                )
                _log_restore_stage("source_manager_initialization_completed")

                _log_restore_stage("destination_credentials_decryption_started")
                destination_credentials = _decrypt_credentials(
                    backup_destination, "destination", request.backup_destination_id
                )
                _log_restore_stage("destination_credentials_decryption_completed")

                _log_restore_stage("destination_manager_initialization_started")
                backup_destination_manager = BackupDestinationManager(
                    destination_credentials
                ).create_from_type(backup_destination.destination_type)
                _log_restore_stage("destination_manager_initialization_completed")

                _log_restore_stage("download_started")
                local_path = backup_destination_manager.get_backup(request.backup_path)
                local_paths.append(local_path)
                local_size = os.path.getsize(local_path) if os.path.exists(local_path) else None
                _log_restore_stage(
                    "download_completed", local_path=local_path, local_size=local_size
                )

                restore_path = local_path
                if is_encrypted_file(restore_path):
                    if not request.private_key:
                        raise ValueError("Private key is required to restore encrypted backup")
                    _log_restore_stage("decryption_started")
                    restore_path = decrypt_file(restore_path, request.private_key)
                    local_paths.append(restore_path)
                    _log_restore_stage("decryption_completed", local_path=restore_path)

                if is_gzip_file(restore_path):
                    _log_restore_stage("decompression_started", local_path=restore_path)
                    restore_path = decompress_file(restore_path)
                    local_paths.append(restore_path)
                    _log_restore_stage("decompression_completed", local_path=restore_path)

                try:
                    _log_restore_stage("source_restore_started", local_path=restore_path)
                    backup_manager.restore_from_backup(restore_path)
                    _log_restore_stage("completed")
                    _notify_gotify(
                        user_info.tenant_id,
                        "Restore completed",
                        f"Restore completed for backup {request.backup_path}",
                    )
                    return True

                except Exception as e:
                    logger.error("restore_failed", error=str(e), persist_db=True, exc_info=True)
                    _notify_gotify(user_info.tenant_id, "Restore failed", str(e))
                    return False

        except Retry:
            raise
        except ValueError as e:
            logger.error(
                "restore_task_failed_decryption_error", error=str(e), persist_db=True, exc_info=True
            )
            _notify_gotify(user_info.tenant_id, "Restore failed", str(e))
            return False
        except Exception as e:
            logger.error("restore_task_failed", error=str(e), persist_db=True, exc_info=True)
            _notify_gotify(user_info.tenant_id, "Restore failed", str(e))
            return False
        finally:
            if local_paths:
                _log_restore_stage("local_cleanup_started")
                _remove_local_paths(local_paths)
                _log_restore_stage("local_cleanup_completed")
