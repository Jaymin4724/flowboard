from fastapi import status, Request, Response
from app.core.redis import get_redis
from app.core.config import settings


# Implemented token bucket algorithm for ratelimitting
async def rate_limitter_middleware(request: Request, call_next):
    if settings.TESTING == True:
        response = await call_next(request)
        return response

    redis = await get_redis()

    ip_addr = request.client.host
    key = f"rate_limit:{ip_addr}"

    limit = 15
    ttl = 60  # window

    try:
        # Increment the counter (Redis creates it if it doesn't exist)
        current_count = await redis.incr(key)

        # If this is the first hit, set the expiration window
        if current_count == 1:
            await redis.expire(key, ttl)

        # Check if limit is exceeded
        if current_count > limit:
            return Response(
                content="Limit exceeded, Please try again later.",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        response = await call_next(request)
        return response

    except Exception as e:
        # Fallback for Redis connection issues or other errors
        return Response(
            content=f"Internal Server Error: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
