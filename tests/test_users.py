import json
import uuid
from unittest.mock import AsyncMock
from fastapi import status
from app.db.models.user import UserModel
from tests.test_utils import assert_response_structure, create_user_data
from tests.conftest import global_fake_redis


class TestUser:
    async def test_register_initiate_success(self, client):
        """Submit user details to trigger an OTP generation and save the pending user to Redis."""
        user_details = create_user_data()

        response = await client.post("/users/register", json=user_details)
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert body["message"] == "OTP sent to your email. Valid for 10 minutes."
        assert await global_fake_redis.exists(f"pending_user:{user_details['email']}")

    async def test_verify_otp_and_register_success(self, client):
        """Retrieve the OTP from Redis and submit it to complete the user registration process."""
        user_details = create_user_data()
        email = user_details["email"]
        await client.post("/users/register", json=user_details)

        # Peek into Redis to get the dynamic OTP
        raw_data = await global_fake_redis.get(f"pending_user:{email}")
        otp = json.loads(raw_data)["otp"]

        response = await client.post(f"/users/verify-otp?email={email}&otp={otp}")
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert_response_structure(body)
        assert body["message"] == "Email verified and user registered successfully."
        assert body["data"]["email"] == email

    async def test_register_duplicate_email_error(self, client):
        """Try registering with an existing email to ensure the system blocks duplicates."""
        user_details = create_user_data(email="duplicate@gmail.com")
        await client.post("/users/register", json=user_details)
        otp = json.loads(
            await global_fake_redis.get(f"pending_user:{user_details['email']}")
        )["otp"]
        await client.post(f"/users/verify-otp?email={user_details['email']}&otp={otp}")

        response = await client.post("/users/register", json=user_details)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "Email already registered"

    async def test_login_success(self, client):
        """Authenticate with valid credentials after verifying email to receive access tokens."""
        user_details = create_user_data(email="login-user@gmail.com")
        email = user_details["email"]

        # Complete 2-step registration
        await client.post("/users/register", json=user_details)
        otp = json.loads(await global_fake_redis.get(f"pending_user:{email}"))["otp"]
        await client.post(f"/users/verify-otp?email={email}&otp={otp}")

        # Attempt Login
        login_payload = {"email": email, "password": user_details["password"]}
        response = await client.post("/users/login", json=login_payload)

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert_response_structure(body)
        assert "access_token" in body["data"]

    async def test_refresh_token_success(self, client):
        """Swap a valid refresh token for a new pair to verify the rotation mechanism."""
        user_details = create_user_data(email="refresher@gmail.com")
        email = user_details["email"]

        # Register and Login
        await client.post("/users/register", json=user_details)
        otp = json.loads(await global_fake_redis.get(f"pending_user:{email}"))["otp"]
        await client.post(f"/users/verify-otp?email={email}&otp={otp}")

        login_res = await client.post(
            "/users/login", json={"email": email, "password": user_details["password"]}
        )
        refresh_token = login_res.json()["data"]["refresh_token"]

        # Refresh tokens
        response = await client.post(f"/users/refresh?refresh_token={refresh_token}")
        assert response.status_code == status.HTTP_200_OK
        assert "access_token" in response.json()["data"]

    async def test_refresh_token_reuse_failure(self, client):
        """Try using the same refresh token twice to confirm the blacklist prevents reuse."""
        user_details = create_user_data(email="reuser@gmail.com")
        email = user_details["email"]

        # Setup: Register and Login
        await client.post("/users/register", json=user_details)
        otp = json.loads(await global_fake_redis.get(f"pending_user:{email}"))["otp"]
        await client.post(f"/users/verify-otp?email={email}&otp={otp}")

        login_res = await client.post(
            "/users/login", json={"email": email, "password": user_details["password"]}
        )
        token = login_res.json()["data"]["refresh_token"]

        # First use succeeds
        await client.post(f"/users/refresh?refresh_token={token}")

        # Second use must fail
        response = await client.post(f"/users/refresh?refresh_token={token}")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["detail"] == "Token has already been used"

    async def test_refresh_token_inactive_user_failure(self, client):
        """Deactivate the user after login and confirm their refresh token stops working."""
        user_details = create_user_data(email="deactivated-refresh@gmail.com")
        email = user_details["email"]

        # Register and Login
        await client.post("/users/register", json=user_details)
        otp = json.loads(await global_fake_redis.get(f"pending_user:{email}"))["otp"]
        await client.post(f"/users/verify-otp?email={email}&otp={otp}")

        login_res = await client.post(
            "/users/login", json={"email": email, "password": user_details["password"]}
        )
        tokens = login_res.json()["data"]

        # Deactivate the account
        client.headers.update({"Authorization": f"Bearer {tokens['access_token']}"})
        await client.delete("/users/me")

        # Refresh must now fail
        response = await client.post(
            f"/users/refresh?refresh_token={tokens['refresh_token']}"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["detail"] == "User not found or inactive"

    async def test_delete_profile_photo_success(self, client, db, monkeypatch):
        """Set a profile photo directly in the DB, then confirm the DELETE endpoint clears it."""
        monkeypatch.setattr(
            "app.api.v1.routes.users.delete_profile_photo", lambda key: None
        )

        user_details = create_user_data(email="photo-delete@gmail.com")
        email = user_details["email"]

        await client.post("/users/register", json=user_details)
        otp = json.loads(await global_fake_redis.get(f"pending_user:{email}"))["otp"]
        await client.post(f"/users/verify-otp?email={email}&otp={otp}")

        login_res = await client.post(
            "/users/login", json={"email": email, "password": user_details["password"]}
        )
        tokens = login_res.json()["data"]
        client.headers.update({"Authorization": f"Bearer {tokens['access_token']}"})

        me_res = await client.get("/users/me")
        user_id = me_res.json()["data"]["id"]

        user = await db.get(UserModel, uuid.UUID(user_id))
        user.profile_photo_key = "profile-photos/user_test.png"
        await db.commit()

        response = await client.delete(f"/users/profile-photo/{user_id}")
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert_response_structure(body)
        assert body["message"] == "Profile photo deleted successfully."

        await db.refresh(user)
        assert user.profile_photo_key is None

    async def test_verify_otp_invalid_otp_error(self, client):
        """Submit the wrong OTP to confirm verification is rejected."""
        user_details = create_user_data(email="bad-otp@gmail.com")
        email = user_details["email"]
        await client.post("/users/register", json=user_details)

        response = await client.post(f"/users/verify-otp?email={email}&otp=000000")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "Invalid OTP"

    async def test_login_invalid_credentials_error(self, client):
        """Attempt login with a wrong password to confirm credentials are rejected."""
        user_details = create_user_data(email="wrong-pass@gmail.com")
        email = user_details["email"]

        await client.post("/users/register", json=user_details)
        otp = json.loads(await global_fake_redis.get(f"pending_user:{email}"))["otp"]
        await client.post(f"/users/verify-otp?email={email}&otp={otp}")

        response = await client.post(
            "/users/login", json={"email": email, "password": "wrong-password"}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["detail"] == "Invalid credentials"

    async def test_logout_success(self, client):
        """Log out with a valid refresh token and confirm it becomes unusable afterward."""
        user_details = create_user_data(email="logout-user@gmail.com")
        email = user_details["email"]

        await client.post("/users/register", json=user_details)
        otp = json.loads(await global_fake_redis.get(f"pending_user:{email}"))["otp"]
        await client.post(f"/users/verify-otp?email={email}&otp={otp}")

        login_res = await client.post(
            "/users/login", json={"email": email, "password": user_details["password"]}
        )
        refresh_token = login_res.json()["data"]["refresh_token"]

        response = await client.post(f"/users/logout?refresh_token={refresh_token}")
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert_response_structure(body)
        assert body["message"] == "Logged out successfully."

        replay = await client.post(f"/users/refresh?refresh_token={refresh_token}")
        assert replay.status_code == status.HTTP_401_UNAUTHORIZED
        assert replay.json()["detail"] == "Token has already been used"

    async def test_logout_invalid_token_error(self, client):
        """Try logging out with a garbage refresh token to confirm it's rejected."""
        response = await client.post("/users/logout?refresh_token=not-a-real-token")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["detail"] == "Invalid or expired refresh token"

    async def test_get_me_success(self, client):
        """Fetch the authenticated user's own profile."""
        user_details = create_user_data(email="get-me@gmail.com")
        email = user_details["email"]

        await client.post("/users/register", json=user_details)
        otp = json.loads(await global_fake_redis.get(f"pending_user:{email}"))["otp"]
        await client.post(f"/users/verify-otp?email={email}&otp={otp}")

        login_res = await client.post(
            "/users/login", json={"email": email, "password": user_details["password"]}
        )
        tokens = login_res.json()["data"]
        client.headers.update({"Authorization": f"Bearer {tokens['access_token']}"})

        response = await client.get("/users/me")
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert_response_structure(body)
        assert body["message"] == "User profile fetched successfully."
        assert body["data"]["email"] == email

    async def test_get_me_invalid_token_error(self, client):
        """Call /users/me with a garbage bearer token to confirm it's rejected."""
        client.headers.update({"Authorization": "Bearer not-a-real-token"})

        response = await client.get("/users/me")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["detail"] == "Could not validate credentials"

    async def test_update_me_success(self, client):
        """Update the authenticated user's own username."""
        user_details = create_user_data(email="update-me@gmail.com")
        email = user_details["email"]

        await client.post("/users/register", json=user_details)
        otp = json.loads(await global_fake_redis.get(f"pending_user:{email}"))["otp"]
        await client.post(f"/users/verify-otp?email={email}&otp={otp}")

        login_res = await client.post(
            "/users/login", json={"email": email, "password": user_details["password"]}
        )
        tokens = login_res.json()["data"]
        client.headers.update({"Authorization": f"Bearer {tokens['access_token']}"})

        response = await client.patch("/users/me", json={"username": "updated-username"})
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert_response_structure(body)
        assert body["message"] == "Profile updated successfully."
        assert body["data"]["username"] == "updated-username"

    async def test_update_me_duplicate_email_error(self, client):
        """Try updating to an email already used by another user to confirm it's blocked."""
        first_user = create_user_data(
            email="taken-email@gmail.com", username="first-user"
        )
        await client.post("/users/register", json=first_user)
        otp = json.loads(
            await global_fake_redis.get(f"pending_user:{first_user['email']}")
        )["otp"]
        await client.post(
            f"/users/verify-otp?email={first_user['email']}&otp={otp}"
        )

        second_user = create_user_data(
            email="second-user@gmail.com", username="second-user"
        )
        await client.post("/users/register", json=second_user)
        otp = json.loads(
            await global_fake_redis.get(f"pending_user:{second_user['email']}")
        )["otp"]
        await client.post(
            f"/users/verify-otp?email={second_user['email']}&otp={otp}"
        )

        login_res = await client.post(
            "/users/login",
            json={"email": second_user["email"], "password": second_user["password"]},
        )
        tokens = login_res.json()["data"]
        client.headers.update({"Authorization": f"Bearer {tokens['access_token']}"})

        response = await client.patch(
            "/users/me", json={"email": first_user["email"]}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "Email already registered"

    async def test_delete_me_success(self, client):
        """Deactivate the authenticated user's own account."""
        user_details = create_user_data(email="delete-me@gmail.com")
        email = user_details["email"]

        await client.post("/users/register", json=user_details)
        otp = json.loads(await global_fake_redis.get(f"pending_user:{email}"))["otp"]
        await client.post(f"/users/verify-otp?email={email}&otp={otp}")

        login_res = await client.post(
            "/users/login", json={"email": email, "password": user_details["password"]}
        )
        tokens = login_res.json()["data"]
        client.headers.update({"Authorization": f"Bearer {tokens['access_token']}"})

        response = await client.delete("/users/me")
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert_response_structure(body)
        assert body["message"] == "Account deactivated successfully."
        assert body["data"]["is_active"] is False

    async def test_login_after_delete_me_forbidden_error(self, client):
        """Confirm a deactivated account can no longer log in."""
        user_details = create_user_data(email="deactivated-login@gmail.com")
        email = user_details["email"]

        await client.post("/users/register", json=user_details)
        otp = json.loads(await global_fake_redis.get(f"pending_user:{email}"))["otp"]
        await client.post(f"/users/verify-otp?email={email}&otp={otp}")

        login_res = await client.post(
            "/users/login", json={"email": email, "password": user_details["password"]}
        )
        tokens = login_res.json()["data"]
        client.headers.update({"Authorization": f"Bearer {tokens['access_token']}"})
        await client.delete("/users/me")

        response = await client.post(
            "/users/login", json={"email": email, "password": user_details["password"]}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["detail"] == "Account is deactivated"

    async def test_upload_photo_success(self, client, monkeypatch):
        """Upload a valid profile photo and confirm the S3 key is saved."""
        monkeypatch.setattr(
            "app.api.v1.routes.users.upload_profile_photo",
            AsyncMock(return_value="profile-photos/user_test.png"),
        )

        user_details = create_user_data(email="photo-upload@gmail.com")
        email = user_details["email"]

        await client.post("/users/register", json=user_details)
        otp = json.loads(await global_fake_redis.get(f"pending_user:{email}"))["otp"]
        await client.post(f"/users/verify-otp?email={email}&otp={otp}")

        login_res = await client.post(
            "/users/login", json={"email": email, "password": user_details["password"]}
        )
        tokens = login_res.json()["data"]
        client.headers.update({"Authorization": f"Bearer {tokens['access_token']}"})

        me_res = await client.get("/users/me")
        user_id = me_res.json()["data"]["id"]

        response = await client.post(
            f"/users/profile-photo/{user_id}",
            files={"file": ("photo.png", b"fake-image-bytes", "image/png")},
        )
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert_response_structure(body)
        assert body["message"] == "Profile photo updated successfully."
        assert body["data"]["s3_key"] == "profile-photos/user_test.png"

    async def test_upload_photo_invalid_type_error(self, client):
        """Try uploading a disallowed file type to confirm it's rejected."""
        user_details = create_user_data(email="photo-bad-type@gmail.com")
        email = user_details["email"]

        await client.post("/users/register", json=user_details)
        otp = json.loads(await global_fake_redis.get(f"pending_user:{email}"))["otp"]
        await client.post(f"/users/verify-otp?email={email}&otp={otp}")

        login_res = await client.post(
            "/users/login", json={"email": email, "password": user_details["password"]}
        )
        tokens = login_res.json()["data"]
        client.headers.update({"Authorization": f"Bearer {tokens['access_token']}"})

        me_res = await client.get("/users/me")
        user_id = me_res.json()["data"]["id"]

        response = await client.post(
            f"/users/profile-photo/{user_id}",
            files={"file": ("notes.txt", b"just text", "text/plain")},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            response.json()["detail"]
            == "Only JPEG, PNG, and WebP images are allowed."
        )

    async def test_download_photo_success(self, client, db, monkeypatch):
        """Fetch a presigned download URL for a user with a saved profile photo."""
        monkeypatch.setattr(
            "app.api.v1.routes.users.get_presigned_download_url",
            lambda key: "https://fake-bucket.s3.amazonaws.com/fake-signed-url",
        )

        user_details = create_user_data(email="photo-download@gmail.com")
        email = user_details["email"]

        await client.post("/users/register", json=user_details)
        otp = json.loads(await global_fake_redis.get(f"pending_user:{email}"))["otp"]
        await client.post(f"/users/verify-otp?email={email}&otp={otp}")

        login_res = await client.post(
            "/users/login", json={"email": email, "password": user_details["password"]}
        )
        tokens = login_res.json()["data"]
        client.headers.update({"Authorization": f"Bearer {tokens['access_token']}"})

        me_res = await client.get("/users/me")
        user_id = me_res.json()["data"]["id"]

        user = await db.get(UserModel, uuid.UUID(user_id))
        user.profile_photo_key = "profile-photos/user_test.png"
        await db.commit()

        response = await client.get(f"/users/profile-photo/{user_id}")
        assert response.status_code == status.HTTP_200_OK

        body = response.json()
        assert_response_structure(body)
        assert body["message"] == "Pre-signed URL generated successfully."
        assert (
            body["data"]["download_url"]
            == "https://fake-bucket.s3.amazonaws.com/fake-signed-url"
        )
        assert body["data"]["expires_in_seconds"] == 3600

    async def test_download_photo_no_photo_error(self, client):
        """Try fetching a download URL for a user with no photo set to confirm it's rejected."""
        user_details = create_user_data(email="photo-none@gmail.com")
        email = user_details["email"]

        await client.post("/users/register", json=user_details)
        otp = json.loads(await global_fake_redis.get(f"pending_user:{email}"))["otp"]
        await client.post(f"/users/verify-otp?email={email}&otp={otp}")

        login_res = await client.post(
            "/users/login", json={"email": email, "password": user_details["password"]}
        )
        tokens = login_res.json()["data"]
        client.headers.update({"Authorization": f"Bearer {tokens['access_token']}"})

        me_res = await client.get("/users/me")
        user_id = me_res.json()["data"]["id"]

        response = await client.get(f"/users/profile-photo/{user_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "No profile photo set."

    async def test_delete_photo_no_photo_error(self, client):
        """Try deleting a profile photo for a user with none set to confirm it's rejected."""
        user_details = create_user_data(email="photo-delete-none@gmail.com")
        email = user_details["email"]

        await client.post("/users/register", json=user_details)
        otp = json.loads(await global_fake_redis.get(f"pending_user:{email}"))["otp"]
        await client.post(f"/users/verify-otp?email={email}&otp={otp}")

        login_res = await client.post(
            "/users/login", json={"email": email, "password": user_details["password"]}
        )
        tokens = login_res.json()["data"]
        client.headers.update({"Authorization": f"Bearer {tokens['access_token']}"})

        me_res = await client.get("/users/me")
        user_id = me_res.json()["data"]["id"]

        response = await client.delete(f"/users/profile-photo/{user_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "No profile photo set."