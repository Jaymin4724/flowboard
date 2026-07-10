import json
import uuid
import pytest
from datetime import datetime, timedelta, timezone
from fastapi import status
from app.db.models.item import ItemModel
from tests.test_utils import (
    assert_response_structure,
    create_user_data,
    create_item_data,
    update_item_data,
)
from tests.conftest import global_fake_redis


@pytest.fixture
async def auth_client(client):
    """Register, verify, and log in a user to return a client with a valid auth header."""
    user_data = create_user_data()
    email = user_data["email"]

    await client.post("/users/register", json=user_data)

    raw_data = await global_fake_redis.get(f"pending_user:{email}")
    pending_user = json.loads(raw_data)
    otp = pending_user["otp"]

    await client.post(f"/users/verify-otp?email={email}&otp={otp}")

    login_data = {"email": email, "password": user_data["password"]}
    response = await client.post("/users/login", json=login_data)

    tokens = response.json()["data"]
    client.headers.update({"Authorization": f"Bearer {tokens['access_token']}"})

    return client


class TestItem:
    async def test_create_item_success(self, auth_client):
        """Submit new item data to verify it is saved correctly in the database."""
        item_details = create_item_data()

        response = await auth_client.post("/items/", json=item_details)
        assert response.status_code == status.HTTP_201_CREATED

        body = response.json()
        assert_response_structure(body)

        assert body["message"] == "Item added successfully."
        assert body["data"]["title"] == item_details["title"]

    async def test_create_duplicate_item_title_error(self, auth_client):
        """Try creating two items with the same title to ensure the system blocks duplicates."""
        item_details = create_item_data(title="unique-title")
        duplicate_details = create_item_data(
            title="unique-title", desc="different desc"
        )

        await  auth_client.post("/items/", json=item_details)

        response = await auth_client.post("/items/", json=duplicate_details)
        assert response.status_code == status.HTTP_409_CONFLICT

        body = response.json()
        assert body["detail"] == "Item already exists"

    async def test_edit_item_success(self, auth_client):
        """Modify an existing item's details to confirm updates are saved properly."""
        item_details = create_item_data()
        response = await auth_client.post("/items/", json=item_details)
        body = response.json()
        item_id = body["data"]["id"]

        for _ in range(0, 15):
            update_item_details = update_item_data()
            response = await auth_client.patch(f"/items/{item_id}", json=update_item_details)
            assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert_response_structure(body)

        assert body["message"] == "Item updated successfully."
        assert body["data"]["title"] == update_item_details["title"]
        assert "desc" in body["data"]

    async def test_delete_item_success(self, auth_client):
        """Remove an item from the database to verify the deletion process works."""
        item_details = create_item_data()
        response = await auth_client.post("/items/", json=item_details)
        body = response.json()
        item_id = body["data"]["id"]

        response = await auth_client.delete(f"/items/{item_id}")
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert_response_structure(body)

        assert body["message"] == "Item removed successfully."
        assert body["data"]["title"] == item_details["title"]
        assert body["data"]["desc"] == item_details["desc"]

    async def test_update_item_remind_at_resets_stale_flags(self, auth_client, db):
        """PATCHing remind_me_at must clear stale reminded/dispatched flags."""
        item_details = create_item_data()
        response = await auth_client.post("/items/", json=item_details)
        item_id = response.json()["data"]["id"]

        item = await db.get(ItemModel, uuid.UUID(item_id))
        item.reminded = True
        item.dispatched = True
        await db.commit()

        remind_at = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        response = await auth_client.patch(
            f"/items/{item_id}", json={"remind_me_at": remind_at}
        )
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert body["data"]["reminded"] is False
        assert body["data"]["dispatched"] is False
