import json
import pytest
from fastapi import status
from sqlalchemy import select
from app.db.models.user import UserModel
from tests.test_utils import (
    assert_response_structure,
    create_admin_data,
    create_item_data,
    update_item_data,
)
from tests.conftest import global_fake_redis


@pytest.fixture
async def auth_client(client, db):
    """Register, verify, and log in a user, then promote to admin directly in the
    DB (there is no API path to set is_admin, by design)."""
    user_data = create_admin_data()
    email = user_data["email"]

    await client.post("/users/register", json=user_data)

    raw_data = await global_fake_redis.get(f"pending_user:{email}")
    pending_user = json.loads(raw_data)
    otp = pending_user["otp"]

    await client.post(f"/users/verify-otp?email={email}&otp={otp}")

    user = await db.scalar(select(UserModel).where(UserModel.email == email))
    user.is_admin = True
    await db.commit()

    login_data = {"email": email, "password": user_data["password"]}
    response = await client.post("/users/login", json=login_data)

    tokens = response.json()["data"]
    client.headers.update({"Authorization": f"Bearer {tokens['access_token']}"})

    return client


class TestAdmin:
    async def test_create_item_success(self, auth_client):
        """Submit new item data to verify it is saved correctly in the database."""
        item_details = create_item_data()

        response = await auth_client.post("/admin/items", json=item_details)
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

        await auth_client.post("/admin/items", json=item_details)

        response = await auth_client.post("/admin/items", json=duplicate_details)
        assert response.status_code == status.HTTP_409_CONFLICT

        body = response.json()
        assert body["detail"] == "Item already exists"

    async def test_get_all_items_success(self, auth_client):
        """Verify the admin can retrieve a paginated list of all items."""
        await auth_client.post("/admin/items/", json=create_item_data())

        response = await auth_client.get("/admin/items?page=1&size=10")
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert_response_structure(body)

        assert isinstance(body["data"], list)
        assert body["message"] == "Successfully retrieved all items."

    async def test_get_all_users_success(self, auth_client):
        """Verify the admin can retrieve a paginated list of all registered users."""
        response = await auth_client.get("/admin/users?page=1&size=10")
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert_response_structure(body)

        assert isinstance(body["data"], list)
        assert body["message"] == "Successfully retrieved all users."

    async def test_edit_item_success(self, auth_client):
        """Modify an existing item's details to confirm updates are saved properly."""
        item_details = create_item_data()
        response = await auth_client.post("/admin/items", json=item_details)
        body = response.json()
        item_id = body["data"]["id"]

        update_item_details = update_item_data()
        response = await auth_client.patch(
            f"/admin/items/{item_id}", json=update_item_details
        )
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert_response_structure(body)

        assert body["message"] == "Item updated successfully."
        assert body["data"]["title"] == update_item_details["title"]
        assert "desc" in body["data"]

    async def test_delete_item_success(self, auth_client):
        """Remove an item from the database to verify the deletion process works."""
        item_details = create_item_data()
        response = await auth_client.post("/admin/items", json=item_details)
        body = response.json()
        item_id = body["data"]["id"]

        response = await auth_client.delete(f"/admin/items/{item_id}")
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert_response_structure(body)

        assert body["message"] == "Item removed successfully."
        assert body["data"]["title"] == item_details["title"]
        assert body["data"]["desc"] == item_details["desc"]

    async def test_deactivate_user_success(self, auth_client):
        """Modify user fields and verify changes."""
        users_resp = await auth_client.get("/admin/users?page=1&size=1")
        user_id = users_resp.json()["data"][0]["id"]

        update_payload = {"is_active": False}
        response = await auth_client.patch(
            f"/admin/users/{user_id}", json=update_payload
        )

        assert response.status_code == status.HTTP_200_OK
        body = response.json()

        assert body["data"]["is_active"] == False
        assert body["message"] == "User updated successfully."

    async def test_update_user_not_found(self, auth_client):
        """Ensure a 404 is returned when updating a non-existent user."""
        import uuid

        random_id = str(uuid.uuid4())

        response = await auth_client.patch(
            f"/admin/users/{random_id}",
            json={"is_active": True},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "User not found"
