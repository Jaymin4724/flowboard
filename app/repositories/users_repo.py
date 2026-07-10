import uuid
from typing import Sequence
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.user import UserModel


class UserRepository:
    async def get_by_email(self, db: AsyncSession, email: str):
        """Finds a user by email for login/validation."""
        return await db.scalar(select(UserModel).where(UserModel.email == email))

    async def get_by_id(self, db: AsyncSession, user_id: uuid.UUID):
        """Finds a user by ID for the 'get_current_user' logic."""
        return await db.get(UserModel, user_id)

    async def get_all(
        self, db: AsyncSession, page: int = 1, size: int = 10
    ) -> Sequence[UserModel]:
        """Fetch paginated active users."""
        skip = (page - 1) * size
        result = await db.scalars(
            select(UserModel)
            .where(UserModel.is_active == True)
            .offset(skip)
            .limit(size)
        )
        return result.all()

    async def search(
        self, db: AsyncSession, query: str, page: int = 1, size: int = 10
    ) -> Sequence[UserModel]:
        """Search active users by username or email (case-insensitive, partial match)."""
        skip = (page - 1) * size
        pattern = f"%{query}%"
        result = await db.scalars(
            select(UserModel)
            .where(UserModel.is_active == True)
            .where(
                or_(
                    UserModel.username.ilike(pattern),
                    UserModel.email.ilike(pattern),
                )
            )
            .offset(skip)
            .limit(size)
        )
        return result.all()

    async def create(self, db: AsyncSession, user_data: dict):
        """Saves a new user to the DB."""
        new_user = UserModel(**user_data)
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        return new_user

    async def update(self, db: AsyncSession, user: UserModel, update_data: dict):
        """Applies a partial update to an existing user."""
        try:
            for key, value in update_data.items():
                setattr(user, key, value)
            await db.commit()
            await db.refresh(user)
        except Exception as e:
            await db.rollback()
            raise e
        return user

    async def delete(self, db: AsyncSession, user: UserModel) -> UserModel:
        """Soft delete an existing user."""
        try:
            user.is_active = False
            await db.commit()
            await db.refresh(user)
        except Exception as e:
            await db.rollback()
            raise e
        return user
