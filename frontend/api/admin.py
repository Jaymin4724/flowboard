from frontend.api.client import request
from frontend.api.exceptions import ApiError


def list_items(page: int = 1, size: int = 10) -> list[dict]:
    return request("GET", "/admin/items", params={"page": page, "size": size})["data"]


def list_items_detailed(page: int = 1, size: int = 10) -> list[dict]:
    return request("GET", "/admin/items/detailed", params={"page": page, "size": size})["data"]


def list_users(page: int = 1, size: int = 10) -> list[dict]:
    return request("GET", "/admin/users", params={"page": page, "size": size})["data"]


def create_item(title: str, desc: str | None, status: str) -> dict:
    payload = {"title": title, "desc": desc, "status": status}
    return request("POST", "/admin/items", json=payload)["data"]


def update_item(item_id: str, **fields) -> dict:
    payload = {k: v for k, v in fields.items() if v is not None}
    return request("PATCH", f"/admin/items/{item_id}", json=payload)["data"]


def delete_item(item_id: str) -> dict:
    return request("DELETE", f"/admin/items/{item_id}")["data"]


def update_user(user_id: str, **fields) -> dict:
    payload = {k: v for k, v in fields.items() if v is not None}
    return request("PATCH", f"/admin/users/{user_id}", json=payload)["data"]


def deactivate_user(user_id: str) -> dict:
    # The route's handler always soft-deletes (is_active=False) and ignores
    # the request body's contents, but it requires a JSON body to validate.
    return request("DELETE", f"/admin/users/{user_id}", json={})["data"]


def probe_is_admin() -> bool:
    """There's no `is_admin` field on the user profile response, so the only
    way to know if the current user is an admin is to try an admin-only
    endpoint and see whether it 403s."""
    try:
        request("GET", "/admin/items", params={"page": 1, "size": 1})
    except ApiError as exc:
        if exc.status_code == 403:
            return False
        raise
    return True
