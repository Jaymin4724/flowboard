from frontend.api.client import request


def list_items(page: int = 1, size: int = 10) -> list[dict]:
    return request("GET", "/items/", params={"page": page, "size": size})["data"]


def create_item(title: str, desc: str | None, status: str) -> dict:
    payload = {"title": title, "desc": desc, "status": status}
    return request("POST", "/items/", json=payload)["data"]


def update_item(item_id: str, **fields) -> dict:
    payload = {k: v for k, v in fields.items() if v is not None}
    return request("PATCH", f"/items/{item_id}", json=payload)["data"]


def delete_item(item_id: str) -> dict:
    return request("DELETE", f"/items/{item_id}")["data"]


def schedule_reminder(item_id: str, remind_at_iso: str) -> dict:
    return request("POST", f"/items/remind/{item_id}", json={"remind_at": remind_at_iso})["data"]
