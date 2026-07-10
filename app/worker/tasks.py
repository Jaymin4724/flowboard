import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.worker.celery_app import celery_app
from app.repositories.item_repo import ItemRepository
from app.service.email_service import EmailService
from app.db.models.item import ItemModel, ItemStatus, DeactivationType
from app.db.models.user import UserModel


def make_session_factory():
    """Creates a fresh engine + session factory bound to the current event loop."""
    engine = create_async_engine(
        settings.DB_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


@celery_app.task(
    name="execute_reminder_email",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def execute_reminder_email(self, item_id: str):
    """Worker task: Runs at the exact ETA provided by Redis."""

    async def send_logic():
        AsyncSessionLocal = make_session_factory()
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ItemModel)
                .where(ItemModel.id == item_id)
                .options(selectinload(ItemModel.owner))
            )
            item = result.scalar_one_or_none()
            if not item or item.reminded or item.remind_me_at is None:
                return

            email_service = EmailService()
            await email_service.send_reminder_email(
                email_to=item.owner.email,
                subject=f"Reminder: {item.title}",
                body=f"This is a reminder for your task: {item.title}",
            )
            item.remind_me_at = None
            item.reminded = False
            item.dispatched = False
            await db.commit()

    asyncio.run(send_logic())


@celery_app.task(name="dispatch_reminders_batch")
def dispatch_reminders_batch():
    """Beat task: Runs every 1 minute to fill the Redis queue."""

    async def dispatch_logic():
        AsyncSessionLocal = make_session_factory()
        async with AsyncSessionLocal() as db:
            repo = ItemRepository()

            now = datetime.now(timezone.utc)
            window_end = now + timedelta(seconds=60)

            pending_items = await repo.get_all_pending_reminders(window_end, db)
            if pending_items:
                for item in pending_items:
                    item.dispatched = True
                await db.commit()

                for item in pending_items:
                    execute_reminder_email.apply_async(
                        args=[str(item.id)], eta=item.remind_me_at.replace(tzinfo=None)
                    )

    asyncio.run(dispatch_logic())


@celery_app.task(name="deactivate_completed_items")
def deactivate_completed_items():
    """Beat task: Every Sunday 4 AM IST — bulk-deactivates all completed items."""

    async def deactivate_logic():
        AsyncSessionLocal = make_session_factory()
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ItemModel)
                .where(ItemModel.status == ItemStatus.completed)
                .with_for_update(skip_locked=True)
            )
            items = result.scalars().all()
            if not items:
                return

            for item in items:
                item.status = ItemStatus.deactivated
                item.deactivation_type = DeactivationType.automatic

            await db.commit()

    asyncio.run(deactivate_logic())
