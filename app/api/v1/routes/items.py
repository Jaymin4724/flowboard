from fastapi import APIRouter, status, HTTPException, Query, Body
from typing import Annotated
from app.api.v1.dependencies import DBDep, ItemRepoDep, CurrentUserDep
from app.api.v1.schemas.response import ResponseSchema, create_response
from app.api.v1.schemas.item import (
    ItemOutSchema,
    ItemCreateSchema,
    ItemUpdateSchema,
    ItemStatus,
    DeactivationType,
)
from app.api.v1.schemas.pagination import PaginationSchema
from app.core.logger import log_func
import uuid
from datetime import datetime, timezone

router = APIRouter(prefix="/items", tags=["Items"])


@router.get("/", status_code=status.HTTP_200_OK, response_model=ResponseSchema)
@log_func
async def get_items(
    db: DBDep,
    current_user: CurrentUserDep,
    item_repo: ItemRepoDep,
    pagination: Annotated[PaginationSchema, Query()],
):
    """Get all the items of current user."""
    items = await item_repo.get_all(
        owner_id=current_user.id, db=db, page=pagination.page, size=pagination.size
    )
    items_data = [
        ItemOutSchema.model_validate(item).model_dump(mode="json") for item in items
    ]
    return create_response(items_data, "Successfully retrieved all items.")


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=ResponseSchema)
@log_func
async def create_item(
    item: ItemCreateSchema,
    db: DBDep,
    current_user: CurrentUserDep,
    item_repo: ItemRepoDep,
):
    """Create a new item and check it doesn't already exist."""
    if await item_repo.get_by_title(item.title, current_user.id, db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Item already exists"
        )
    new_item = await item_repo.create(item, owner_id=current_user.id, db=db)
    item_data = ItemOutSchema.model_validate(new_item).model_dump(mode="json")
    return create_response(item_data, "Item added successfully.")


@router.patch(
    "/{item_id}", status_code=status.HTTP_200_OK, response_model=ResponseSchema
)
@log_func
async def update_item(
    item_id: uuid.UUID,
    item: ItemUpdateSchema,
    db: DBDep,
    item_repo: ItemRepoDep,
    current_user: CurrentUserDep,
):
    """Update specific fields of an item (Partial update)."""
    existing_item = await item_repo.get_by_id(item_id, db)
    if not existing_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item not found"
        )
    if existing_item.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to edit this item",
        )

    update_data = item.model_dump(exclude_unset=True)
    if "status" in update_data:
        if update_data["status"] == ItemStatus.deactivated:
            update_data["deactivation_type"] = DeactivationType.manual
        else:
            update_data["deactivation_type"] = DeactivationType.none

    if "remind_me_at" in update_data:
        update_data["reminded"] = False
        update_data["dispatched"] = False

    updated_item = await item_repo.update(item_id, update_data, db)
    updated_item_data = ItemOutSchema.model_validate(updated_item).model_dump(
        mode="json"
    )

    return create_response(updated_item_data, "Item updated successfully.")


@router.delete(
    "/{item_id}", status_code=status.HTTP_200_OK, response_model=ResponseSchema
)
@log_func
async def delete_item(
    item_id: uuid.UUID, db: DBDep, item_repo: ItemRepoDep, current_user: CurrentUserDep
):
    """Delete an item if it exists."""
    item = await item_repo.get_by_id(item_id, db)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item not found"
        )
    if item.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this item",
        )
    deleted_item_data = ItemOutSchema.model_validate(item).model_dump(mode="json")

    await item_repo.delete(item_id, db)
    return create_response(deleted_item_data, "Item removed successfully.")


@router.post(
    "/remind/{item_id}",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ResponseSchema,
)
@log_func
async def schedule_item_reminder(
    item_id: uuid.UUID,
    remind_at: Annotated[datetime, Body(embed=True)],
    db: DBDep,
    item_repo: ItemRepoDep,
    current_user: CurrentUserDep,
):
    """
    Saves a background email reminder for a specific item.
    """
    item = await item_repo.get_by_id(item_id, db)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item not found"
        )

    if item.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not yours!")

    now = datetime.now(timezone.utc)
    if remind_at.tzinfo is None:
        remind_at = remind_at.replace(tzinfo=timezone.utc)

    if remind_at <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reminder time must be in the future",
        )

    updated_item = await item_repo.update_reminder(item_id, remind_at, db)

    item_data = ItemOutSchema.model_validate(updated_item).model_dump(mode="json")
    return create_response(
        item_data, f"Reminder saved for {remind_at.strftime('%Y-%m-%d %H:%M:%S UTC')}."
    )
