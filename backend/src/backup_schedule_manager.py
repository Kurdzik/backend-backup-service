from datetime import datetime
from typing import List, Optional
import os

from sqlmodel import Session, select
from kombu import Connection, Exchange, Queue

from src.models.db import Schedule as ScheduleModel


schedules_exchange = Exchange("schedules_exchange", "direct", durable=True)
schedules_queue = Queue(
    "schedules", exchange=schedules_exchange, routing_key="schedules"
)


class ScheduleManager:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _notify_scheduler_reload(self) -> None:
        """Send message to Celery Beat to reload schedules"""
        with Connection(os.environ["CELERY_BROKER_URL"]) as conn:
            with conn.Producer() as producer:
                producer.publish(
                    {},
                    exchange=schedules_exchange,
                    routing_key="schedules",
                    declare=[schedules_exchange, schedules_queue],
                )

    def create_schedule(
        self,
        tenant_id: str,
        name: str,
        source_id: int,
        destination_id: int,
        keep_n: int,
        schedule: str,
        is_active: bool = True,
    ) -> ScheduleModel:
        """
        Create a new backup schedule

        Args:
            tenant_id: Tenant identifier
            name: Schedule name
            source_id: ID of the backup source
            destination_id: ID of the backup destination
            keep_n: Number of backups to keep
            schedule: Cron expression or schedule format
            is_active: Whether schedule is active

        Returns:
            Created Schedule object
        """
        schedule_obj = ScheduleModel(
            tenant_id=tenant_id,
            name=name,
            source_id=source_id,
            destination_id=destination_id,
            keep_n=keep_n,
            schedule=schedule,
            is_active=is_active,
        )
        self.session.add(schedule_obj)
        self.session.commit()
        self.session.refresh(schedule_obj)
        self._notify_scheduler_reload()
        return schedule_obj

    def get_schedule(self, schedule_id: int, tenant_id: str) -> ScheduleModel:
        """
        Get a schedule by ID

        Args:
            schedule_id: Schedule ID
            tenant_id: Tenant identifier for isolation

        Returns:
            Schedule object or None if not found
        """
        statement = select(ScheduleModel).where(
            (ScheduleModel.id == schedule_id) & (ScheduleModel.tenant_id == tenant_id)
        )
        return self.session.exec(statement).first()  # ty:ignore[invalid-return-type]

    def list_schedules(
        self, tenant_id: str, is_active: Optional[bool] = None
    ) -> List[ScheduleModel]:
        """
        List schedules for a tenant

        Args:
            tenant_id: Tenant identifier
            is_active: Optional filter for active/inactive schedules

        Returns:
            List of Schedule objects
        """
        statement = select(ScheduleModel).where(ScheduleModel.tenant_id == tenant_id)

        if is_active is not None:
            statement = statement.where(ScheduleModel.is_active == is_active)

        return self.session.exec(statement).all()  # ty:ignore[invalid-return-type]

    def update_schedule(
        self,
        schedule_id: int,
        tenant_id: str,
        name: Optional[str] = None,
        source_id: Optional[int] = None,
        destination_id: Optional[int] = None,
        keep_n: Optional[int] = None,
        schedule: Optional[str] = None,
        is_active: Optional[bool] = None,
        next_run: Optional[datetime] = None,
    ) -> Optional[ScheduleModel]:
        """
        Update a schedule

        Args:
            schedule_id: Schedule ID
            tenant_id: Tenant identifier
            name: New schedule name
            source_id: New source ID
            destination_id: New destination ID
            keep_n: New keep_n value
            schedule: New schedule expression
            is_active: New active status
            next_run: New next run time

        Returns:
            Updated Schedule object or None if not found
        """
        schedule_obj = self.get_schedule(schedule_id, tenant_id)

        if not schedule_obj:
            return None

        if name is not None:
            schedule_obj.name = name
        if source_id is not None:
            schedule_obj.source_id = source_id
        if destination_id is not None:
            schedule_obj.destination_id = destination_id
        if keep_n is not None:
            schedule_obj.keep_n = keep_n
        if schedule is not None:
            schedule_obj.schedule = schedule
        if is_active is not None:
            schedule_obj.is_active = is_active
        if next_run is not None:
            schedule_obj.next_run = next_run

        schedule_obj.updated_at = datetime.now()
        self.session.add(schedule_obj)
        self.session.commit()
        self.session.refresh(schedule_obj)
        self._notify_scheduler_reload()
        return schedule_obj

    def delete_schedule(self, schedule_id: int, tenant_id: str) -> bool:
        """
        Delete a schedule

        Args:
            schedule_id: Schedule ID
            tenant_id: Tenant identifier

        Returns:
            True if deleted, False if not found
        """
        schedule_obj = self.get_schedule(schedule_id, tenant_id)

        if not schedule_obj:
            return False

        self.session.delete(schedule_obj)
        self.session.commit()
        self._notify_scheduler_reload()
        return True

    def update_last_run(
        self, schedule_id: int, tenant_id: str, last_run: datetime
    ) -> Optional[ScheduleModel]:
        """
        Update last run time for a schedule

        Args:
            schedule_id: Schedule ID
            tenant_id: Tenant identifier
            last_run: Last run datetime

        Returns:
            Updated Schedule object or None if not found
        """
        schedule_obj = self.get_schedule(schedule_id, tenant_id)

        if not schedule_obj:
            return None

        schedule_obj.last_run = last_run
        schedule_obj.updated_at = datetime.now()
        self.session.add(schedule_obj)
        self.session.commit()
        self.session.refresh(schedule_obj)
        # No reload needed for last_run updates
        return schedule_obj

    def toggle_schedule(
        self, schedule_id: int, tenant_id: str
    ) -> Optional[ScheduleModel]:
        """
        Toggle active status of a schedule

        Args:
            schedule_id: Schedule ID
            tenant_id: Tenant identifier

        Returns:
            Updated Schedule object or None if not found
        """
        schedule_obj = self.get_schedule(schedule_id, tenant_id)

        if not schedule_obj:
            return None

        schedule_obj.is_active = not schedule_obj.is_active
        schedule_obj.updated_at = datetime.now()
        self.session.add(schedule_obj)
        self.session.commit()
        self.session.refresh(schedule_obj)
        self._notify_scheduler_reload()
        return schedule_obj
