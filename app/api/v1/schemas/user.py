import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserBaseSchema(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    is_active: bool = True
    model_config = ConfigDict(from_attributes=True)


class UserCreateSchema(UserBaseSchema):
    password: str = Field(..., min_length=8, description="Plain text password")


class UserOutSchema(UserBaseSchema):
    id: uuid.UUID
    is_verified: bool
    created_at: datetime
    last_updated_at: datetime
    profile_photo_key: Optional[str] = None


class UserInDBSchema(UserOutSchema):
    hashed_password: str


class UserInSchema(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Plain text password")


class UserUpdateSchema(BaseModel):
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    profile_photo_key: Optional[str] = None


class UserUpdateMeSchema(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8, description="Plain text password")