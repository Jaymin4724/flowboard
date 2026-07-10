from fastapi import status
from tests.test_utils import assert_response_structure
from tests.conftest import global_fake_redis


async def test_root_success(client):
    """Test root endpoint."""
    response = await client.get("/")

    assert response.status_code == status.HTTP_200_OK

    body = response.json()
    assert_response_structure(body)

    assert body["message"] == "Server is running!"
    assert body["data"] == []


async def _fake_get_redis():
    """Stand-in for app.core.redis.get_redis that the rate-limit middleware calls directly."""
    return global_fake_redis


def _enable_rate_limiting(monkeypatch):
    """The middleware is a no-op whenever settings.TESTING is True, so flip it off
    for the duration of the test and point it at the fake Redis instance instead
    of the real one it would otherwise connect to."""
    monkeypatch.setattr(
        "app.middleware.rate_limitting_middleware.settings.TESTING", False
    )
    monkeypatch.setattr(
        "app.middleware.rate_limitting_middleware.get_redis", _fake_get_redis
    )


async def test_rate_limit_within_limit_success(client, monkeypatch):
    """A handful of requests under the 15-req/60s limit should all succeed normally."""
    _enable_rate_limiting(monkeypatch)

    for _ in range(5):
        response = await client.get("/")
        assert response.status_code == status.HTTP_200_OK


async def test_rate_limit_exceeded_error(client, monkeypatch):
    """Exceeding the 15-req/60s limit on a single route should return 429."""
    _enable_rate_limiting(monkeypatch)

    for _ in range(15):
        response = await client.get("/")
        assert response.status_code == status.HTTP_200_OK

    response = await client.get("/")
    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert response.text == "Limit exceeded, Please try again later."
