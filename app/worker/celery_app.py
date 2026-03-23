from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery("worker", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

celery_app.autodiscover_tasks(["app.worker"], force=True)

celery_app.conf.beat_schedule = {
    "dispatch-every-1-min": {
        "task": "dispatch_reminders_batch",
        "schedule": 60.0,
    },
    "deactivate-completed-items-weekly": {
        "task": "deactivate_completed_items",
        "schedule": crontab(
            hour=22, minute=30, day_of_week=6
        ),  # Saturday 22:30 UTC = Sunday 04:00 IST
    },
}

celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
