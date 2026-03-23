import uuid
from typing import Sequence, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.item import ItemModel
from datetime import datetime, timezone
from sqlalchemy.orm import selectinload


class ItemRepository:
    async def get_by_id(
        self, item_id: uuid.UUID, db: AsyncSession
    ) -> Optional[ItemModel]:
        """Fetch a single item by UUID."""
        return await db.get(ItemModel, item_id)

    async def get_all(
        self, owner_id: uuid.UUID, db: AsyncSession, page: int = 1, size: int = 10
    ) -> Sequence[ItemModel]:
        """Fetch paginated items with current user's owner_id."""
        skip = (page - 1) * size

        result = await db.scalars(
            select(ItemModel)
            .where(ItemModel.owner_id == owner_id)
            .offset(skip)
            .limit(size)
        )
        return result.all()

    async def get_by_title(
        self, title: str, owner_id: uuid.UUID, db: AsyncSession
    ) -> Optional[ItemModel]:
        """Fetch a single item by Title."""
        result = await db.scalar(
            select(ItemModel).where(
                ItemModel.title == title, ItemModel.owner_id == owner_id
            )
        )
        return result

    async def create(self, item, owner_id: uuid.UUID, db: AsyncSession) -> ItemModel:
        """Add a new item to the list."""
        new_item = ItemModel(**item.model_dump(), owner_id=owner_id)
        db.add(new_item)
        await db.commit()
        await db.refresh(new_item)
        return new_item

    async def update(
        self, item_id: uuid.UUID, update_data: dict, db: AsyncSession
    ) -> Optional[ItemModel]:
        """Update an existing item (Partial update)."""
        item = await self.get_by_id(item_id, db)
        if item:
            for key, value in update_data.items():
                setattr(item, key, value)
            await db.commit()
            await db.refresh(item)
        return item

    async def delete(self, item_id: uuid.UUID, db: AsyncSession) -> Optional[ItemModel]:
        """Remove an item from the list."""
        item = await self.get_by_id(item_id, db)
        if item:
            await db.delete(item)
            await db.commit()
        return item

    async def update_reminder(
        self, item_id: uuid.UUID, remind_at: datetime, db: AsyncSession
    ) -> Optional[ItemModel]:
        """
        Updates the reminder time for an item.
        Ensures timezone awareness and resets the reminded flag.
        """
        if remind_at.tzinfo is None:
            remind_at = remind_at.replace(tzinfo=timezone.utc)
        else:
            remind_at = remind_at.astimezone(timezone.utc)

        item = await self.get_by_id(item_id, db)

        if item:
            item.remind_me_at = remind_at
            item.reminded = False
            item.dispatched = False
            try:
                await db.commit()
                await db.refresh(item)
            except Exception as e:
                await db.rollback()
                raise e
        return item

    async def get_all_pending_reminders(self, window_end: datetime, db: AsyncSession):
        """
        Fetches ALL items where reminded is False and the time is
        anywhere in the past OR up to 10 minutes in the future.
        """
        result = await db.execute(
            select(ItemModel)
            .options(selectinload(ItemModel.owner))
            .where(ItemModel.remind_me_at != None)
            .where(ItemModel.reminded == False)
            .where(ItemModel.dispatched == False)
            .where(ItemModel.remind_me_at <= window_end)
            .with_for_update(skip_locked=True)
        )
        return result.scalars().all()