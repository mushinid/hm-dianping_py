from datetime import timedelta

from fastapi import Request
from redis.asyncio import Redis
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from hm_dianping_py.config.constants import LOGIN_USER_KEY, LOGIN_USER_TTL_MINUTES
from hm_dianping_py.schema.users import UserDTO


async def load_login_user(redis: Redis, token: str | None) -> UserDTO | None:
    if not token:
        return None

    key = f"{LOGIN_USER_KEY}{token}"
    user_data = await redis.hgetall(key)
    if not user_data or not user_data.get("id"):
        return None

    await redis.expire(key, timedelta(minutes=LOGIN_USER_TTL_MINUTES))
    return UserDTO(
        id=int(user_data["id"]),
        nick_name=user_data.get("nickName"),
        icon=user_data.get("icon"),
    )


async def refresh_login_user(request: Request, call_next: RequestResponseEndpoint) -> Response:
    request.state.current_user = await load_login_user(
        request.app.state.redis,
        request.headers.get("authorization"),
    )
    return await call_next(request)


async def get_current_user(request: Request) -> UserDTO:
    user = getattr(request.state, "current_user", None)
    if user is None:
        raise NotAuthenticated
    return user


class NotAuthenticated(Exception):
    pass
