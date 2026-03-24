from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String
from typing import TYPE_CHECKING
from app.db.models.base import Base

if TYPE_CHECKING:
    from app.db.models.item import ItemModel


class UserModel(Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)

    is_active: Mapped[bool] = mapped_column(default=True)
    is_admin: Mapped[bool] = mapped_column(default=False)
    is_verified: Mapped[bool] = mapped_column(default=True)
    profile_photo_key: Mapped[str | None] = mapped_column(String, nullable=True)

    items: Mapped[list["ItemModel"]] = relationship("ItemModel", back_populates="owner")