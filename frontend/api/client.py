import httpx

from frontend.config import settings
from frontend.api.exceptions import ApiError
from frontend.auth import session

_client = httpx.Client(base_url=settings.API_BASE_URL, timeout=settings.REQUEST_TIMEOUT)


def _parse_error(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text or f"HTTP {response.status_code}"
    if isinstance(body, dict):
        return body.get("detail") or body.get("message") or str(body)
    return str(body)


def _send(method: str, path: str, *, auth: bool, **kwargs) -> httpx.Response:
    headers = kwargs.pop("headers", {}) or {}
    if auth:
        token = session.get_access_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
    return _client.request(method, path, headers=headers, **kwargs)


def _try_refresh() -> bool:
    # Local import: api.auth imports this module at load time, so importing
    # it back here (only when actually refreshing) avoids a circular import
    # at module load time.
    from frontend.api import auth as auth_api

    refresh_token = session.get_refresh_token()
    if not refresh_token:
        return False
    try:
        access_token, new_refresh_token = auth_api.refresh(refresh_token)
    except ApiError:
        return False
    session.set_tokens(access_token, new_refresh_token)
    return True


def request(method: str, path: str, *, auth: bool = True, allow_refresh: bool = True, **kwargs) -> dict:
    """Call the API and return the parsed `{success, message, data}` envelope.

    On a 401 with `auth=True`, attempts exactly one silent refresh-and-retry
    (via the rotating refresh token) before giving up. `allow_refresh=False`
    is used by the refresh/login/logout calls themselves to avoid recursion.
    """
    response = _send(method, path, auth=auth, **kwargs)

    if response.status_code == 401 and auth and allow_refresh and session.get_refresh_token():
        if _try_refresh():
            response = _send(method, path, auth=auth, **kwargs)
        else:
            session.clear_session()
            raise ApiError(401, "Session expired. Please log in again.")

    if response.status_code >= 400:
        raise ApiError(response.status_code, _parse_error(response))

    if response.status_code == 204 or not response.content:
        return {"success": True, "message": "", "data": None}

    return response.json()
