from frontend.api.client import request
from frontend.api.exceptions import ApiError


def get_me() -> dict:
    return request("GET", "/users/me")["data"]


def update_me(**fields) -> dict:
    payload = {k: v for k, v in fields.items() if v is not None}
    return request("PATCH", "/users/me", json=payload)["data"]


def delete_me() -> dict:
    return request("DELETE", "/users/me")["data"]


def upload_profile_photo(user_id: str, filename: str, file_bytes: bytes, content_type: str) -> str:
    files = {"file": (filename, file_bytes, content_type)}
    data = request("POST", f"/users/profile-photo/{user_id}", files=files)["data"]
    return data["s3_key"]


def get_profile_photo_url(user_id: str) -> str | None:
    try:
        data = request("GET", f"/users/profile-photo/{user_id}")["data"]
    except ApiError as exc:
        if exc.status_code == 404:
            return None
        raise
    return data["download_url"]


def delete_profile_photo(user_id: str) -> None:
    request("DELETE", f"/users/profile-photo/{user_id}")
