import time

from fastapi import status, Request, Response
from app.core.redis import get_redis
from app.core.config import settings


CAPACITY = 15
REFILL_RATE = CAPACITY / 60  # tokens per second -> full bucket refills every 60s


# Token bucket algorithm for rate limiting
async def rate_limitter_middleware(request: Request, call_next):
    if settings.TESTING == True:
        response = await call_next(request)
        return response

    redis = await get_redis()

    ip_addr = request.client.host
    key = f"rate_limit:{ip_addr}"
    now = time.time()

    try:
        data = await redis.hgetall(key)

        if not data:
            tokens = float(CAPACITY)
        else:
            last_tokens = float(data["tokens"])
            last_refill = float(data["last_refill"])
            refilled = last_tokens + (now - last_refill) * REFILL_RATE
            tokens = min(CAPACITY, refilled)

        if tokens < 1:
            await redis.hset(key, mapping={"tokens": tokens, "last_refill": now})
            await redis.expire(key, int(CAPACITY / REFILL_RATE) + 60)
            return Response(
                content="Limit exceeded, Please try again later.",
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        await redis.hset(key, mapping={"tokens": tokens - 1, "last_refill": now})
        await redis.expire(key, int(CAPACITY / REFILL_RATE) + 60)

        response = await call_next(request)
        return response

    except Exception as e:
        # Fallback for Redis connection issues or other errors
        return Response(
            content=f"Internal Server Error: {str(e)}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
