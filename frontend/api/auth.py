from frontend.api.client import request


def register(email: str, username: str, password: str) -> str:
    """Initiates registration. Returns the response message, which tells the
    caller whether an OTP was sent or the account was created directly
    (depends on the backend's EMAIL_SERVICE_ACTIVE setting)."""
    payload = {"email": email, "username": username, "password": password}
    envelope = request("POST", "/users/register", json=payload, auth=False)
    return envelope["message"]


def verify_otp(email: str, otp: str) -> dict:
    envelope = request(
        "POST", "/users/verify-otp", params={"email": email, "otp": otp}, auth=False
    )
    return envelope["data"]


def login(email: str, password: str) -> tuple[str, str]:
    envelope = request(
        "POST", "/users/login", json={"email": email, "password": password}, auth=False
    )
    data = envelope["data"]
    return data["access_token"], data["refresh_token"]


def refresh(refresh_token: str) -> tuple[str, str]:
    envelope = request(
        "POST",
        "/users/refresh",
        params={"refresh_token": refresh_token},
        auth=False,
        allow_refresh=False,
    )
    data = envelope["data"]
    return data["access_token"], data["refresh_token"]


def logout(refresh_token: str, access_token: str | None = None) -> None:
    params = {"refresh_token": refresh_token}
    if access_token:
        params["access_token"] = access_token
    request("POST", "/users/logout", params=params, auth=False, allow_refresh=False)
