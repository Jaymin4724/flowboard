from datetime import datetime, timezone
from fastapi import APIRouter, status, HTTPException, UploadFile, File, Depends
from app.api.v1.dependencies import (
    DBDep,
    RedisDep,
    UserRepoDep,
    AuthDep,
    EmailDep,
    CurrentUserDep,
)
from app.api.v1.schemas.user import (
    UserCreateSchema,
    UserInSchema,
    UserOutSchema,
    UserUpdateMeSchema,
)
from app.api.v1.schemas.response import ResponseSchema, create_response
from app.core.logger import log_func
from app.core.config import settings
from app.service.s3_service import (
    upload_profile_photo,
    get_presigned_download_url,
    delete_profile_photo,
)

import json
from fastapi import BackgroundTasks

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/register", response_model=ResponseSchema)
@log_func
async def register_initiate(
    user_in: UserCreateSchema,
    db: DBDep,
    redis: RedisDep,
    user_repo: UserRepoDep,
    auth_service: AuthDep,
    email_service: EmailDep,
    background_tasks: BackgroundTasks,
):
    if await user_repo.get_by_email(db, user_in.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    hashed = auth_service.hash_password(user_in.password)
    pending_user = user_in.model_dump(exclude={"password"}, mode="json")
    pending_user["hashed_password"] = hashed

    if settings.EMAIL_SERVICE_ACTIVE or settings.TESTING:
        otp = auth_service.generate_otp()

        pending_user["otp"] = otp

        await redis.set(
            f"pending_user:{user_in.email}", json.dumps(pending_user), ex=600
        )

        background_tasks.add_task(email_service.send_otp_email, user_in.email, otp)

        return create_response(None, "OTP sent to your email. Valid for 10 minutes.")

    pending_user["is_verified"] = False
    new_user = await user_repo.create(db, pending_user)
    user_out = UserOutSchema.model_validate(new_user).model_dump(mode="json")
    return create_response(
        user_out, "Email is not verified and user registered successfully."
    )


@router.post("/verify-otp", response_model=ResponseSchema)
@log_func
async def verify_otp(
    email: str,
    otp: str,
    db: DBDep,
    redis: RedisDep,
    user_repo: UserRepoDep,
):
    raw_data = await redis.get(f"pending_user:{email}")
    if not raw_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP expired or email not found",
        )

    pending_user = json.loads(raw_data)

    if pending_user["otp"] != otp:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP"
        )

    # Remove OTP from data before saving
    pending_user.pop("otp")
    new_user = await user_repo.create(db, pending_user)

    await redis.delete(f"pending_user:{email}")

    user_out = UserOutSchema.model_validate(new_user).model_dump(mode="json")
    return create_response(user_out, "Email verified and user registered successfully.")


@router.post("/login", response_model=ResponseSchema)
@log_func
async def login(
    user_in: UserInSchema,
    db: DBDep,
    user_repo: UserRepoDep,
    auth_service: AuthDep,
):
    """Authenticate user credentials and generate a JWT access and refresh token for successful login."""
    user = await user_repo.get_by_email(db, user_in.email)

    if not user or not auth_service.verify_password(
        user_in.password, user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated"
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is not verified"
        )

    # Generate both tokens
    access_token = auth_service.create_access_token(data={"sub": str(user.id)})
    refresh_token = auth_service.create_refresh_token(data={"sub": str(user.id)})

    token_data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }
    return create_response(token_data, "Login successful.")


@router.post("/refresh", response_model=ResponseSchema)
@log_func
async def refresh_token(
    refresh_token: str,
    auth_service: AuthDep,
    redis: RedisDep,
    db: DBDep,
    user_repo: UserRepoDep,
):
    """Swap an old refresh token for a brand-new access AND refresh token."""

    payload = auth_service.decode_token(refresh_token, is_refresh=True)

    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    if await redis.exists(f"blacklist:{refresh_token}"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has already been used",
        )

    user_id = payload.get("sub")

    user = await user_repo.get_by_id(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    new_access_token = auth_service.create_access_token(data={"sub": user_id})
    new_refresh_token = auth_service.create_refresh_token(data={"sub": user_id})

    exp_timestamp = payload.get("exp")
    now = datetime.now(timezone.utc).timestamp()
    ttl = int(exp_timestamp - now)

    if ttl > 0:
        await redis.set(f"blacklist:{refresh_token}", "used", ex=ttl)

    token_data = {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }

    return create_response(token_data, "Tokens rotated successfully.")


@router.post("/logout", response_model=ResponseSchema)
@log_func
async def logout(
    refresh_token: str,
    auth_service: AuthDep,
    redis: RedisDep,
    access_token: str | None = None,
):
    """Blacklist a refresh token (and optionally its paired access token) to log the user out."""

    payload = auth_service.decode_token(refresh_token, is_refresh=True)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    now = datetime.now(timezone.utc).timestamp()

    ttl = int(payload.get("exp") - now)
    if ttl > 0:
        await redis.set(f"blacklist:{refresh_token}", "used", ex=ttl)

    if access_token:
        access_payload = auth_service.decode_token(access_token)
        if access_payload:
            access_ttl = int(access_payload.get("exp") - now)
            if access_ttl > 0:
                await redis.set(f"blacklist:{access_token}", "used", ex=access_ttl)

    return create_response(None, "Logged out successfully.")


@router.get("/me", response_model=ResponseSchema)
@log_func
async def get_me(current_user: CurrentUserDep):
    """Return the authenticated user's own profile."""
    user_out = UserOutSchema.model_validate(current_user).model_dump(mode="json")
    return create_response(user_out, "User profile fetched successfully.")


@router.patch("/me", response_model=ResponseSchema)
@log_func
async def update_me(
    user_in: UserUpdateMeSchema,
    db: DBDep,
    user_repo: UserRepoDep,
    auth_service: AuthDep,
    current_user: CurrentUserDep,
):
    """Update the authenticated user's own username, email, and/or password."""
    update_data = user_in.model_dump(exclude_unset=True, exclude_none=True)

    if "email" in update_data and update_data["email"] != current_user.email:
        if await user_repo.get_by_email(db, update_data["email"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

    if "password" in update_data:
        update_data["hashed_password"] = auth_service.hash_password(
            update_data.pop("password")
        )

    updated_user = await user_repo.update(db, current_user, update_data)
    user_out = UserOutSchema.model_validate(updated_user).model_dump(mode="json")
    return create_response(user_out, "Profile updated successfully.")


@router.delete("/me", response_model=ResponseSchema)
@log_func
async def delete_me(
    db: DBDep,
    user_repo: UserRepoDep,
    current_user: CurrentUserDep,
):
    """Deactivate (soft-delete) the authenticated user's own account."""
    updated_user = await user_repo.delete(db, current_user)
    user_out = UserOutSchema.model_validate(updated_user).model_dump(mode="json")
    return create_response(user_out, "Account deactivated successfully.")


@router.post("/profile-photo/{user_id}")
@log_func
async def upload_photo(
    user_id: str,
    db: DBDep,
    user_repo: UserRepoDep,
    current_user: CurrentUserDep,
    file: UploadFile = File(...),
):
    user = await user_repo.get_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if user.profile_photo_key:
        delete_profile_photo(user.profile_photo_key)

    key = await upload_profile_photo(user_id, file)

    user.profile_photo_key = key
    await db.commit()

    return create_response({"s3_key": key}, "Profile photo updated successfully.")


@router.delete("/profile-photo/{user_id}")
@log_func
async def delete_photo(
    user_id: str,
    db: DBDep,
    user_repo: UserRepoDep,
    current_user: CurrentUserDep,
):
    user = await user_repo.get_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if not user.profile_photo_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No profile photo set."
        )

    delete_profile_photo(user.profile_photo_key)
    user.profile_photo_key = None
    await db.commit()

    return create_response(None, "Profile photo deleted successfully.")


@router.get("/profile-photo/{user_id}")
@log_func
async def download_photo(
    user_id: str,
    db: DBDep,
    user_repo: UserRepoDep,
    current_user: CurrentUserDep,
):
    user = await user_repo.get_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if not user.profile_photo_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No profile photo set."
        )

    url = get_presigned_download_url(user.profile_photo_key)
    return create_response(
        {"download_url": url, "expires_in_seconds": 3600},
        "Pre-signed URL generated successfully.",
    )