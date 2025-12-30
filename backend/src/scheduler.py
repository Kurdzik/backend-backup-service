# scheduler.py
from celery.beat import Scheduler
from celery.schedules import crontab
from sqlmodel import select, Session
from src.models.db import Schedule
from src.middleware import engine
from kombu import Connection
import threading
import os
from src.backup_schedule_manager import schedules_queue
from src.worker import app


def parse_cron_exp(exp: str):
    parts = exp.split(" ")
    if len(parts) != 5:
        raise ValueError(
            f"Invalid cron expression. Expected 5 fields, got {len(parts)}"
        )

    minute, hour, day_of_month, month, day_of_week = parts
    return crontab(
        minute=minute,
        hour=hour,
        day_of_month=day_of_month,
        month_of_year=month,
        day_of_week=day_of_week,
    )


def load_schedules_from_db():
    schedule_dict = {}
    with Session(engine) as db_session:
        schedules = db_session.exec(select(Schedule)).all()
        for schedule in schedules:
            schedule_dict[f"backup-schedule-{schedule.id}-{schedule.tenant_id}"] = {
                "task": "src.worker.create_backup",
                "schedule": parse_cron_exp(schedule.schedule),
                "kwargs": {
                    "backup_source_id": schedule.source_id,
                    "backup_destination_id": schedule.destination_id,
                    "tenant_id": schedule.tenant_id,
                    "schedule_id": schedule.id,
                    "keep_n": schedule.keep_n
                },
            }
    return schedule_dict


class DynamicScheduler(Scheduler):
    def setup_schedule(self):
        self.merge_inplace(load_schedules_from_db())
        threading.Thread(target=self._listen_for_updates, daemon=True).start()

    def _listen_for_updates(self):
        with Connection(os.environ["CELERY_BROKER_URL"]) as conn:
            with conn.Consumer(schedules_queue, callbacks=[self._reload]) as consumer:
                while True:
                    conn.drain_events()

    def _reload(self, body: str, message: str):
        self.schedule.clear()
        self.merge_inplace(load_schedules_from_db())
        message.ack()  # ty:ignore[unresolved-attribute]
