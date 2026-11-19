import re
import secrets
import string
from datetime import date

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from hm_dianping_py.config.constants import (
    LOGIN_CODE_KEY,
    LOGIN_CODE_TTL_MINUTES,
    LOGIN_USER_KEY,
    LOGIN_USER_TTL_MINUTES,
    USER_NICK_NAME_PREFIX,
    USER_SIGN_KEY,
)
from hm_dianping_py.model.user import User, UserInfo
from hm_dianping_py.schema.users import ApiResult, LoginForm, UserDTO, UserInfoBase

PHONE_PATTERN = r"^1([38][0-9]|4[579]|5[0-3,5-9]|6[6]|7[0135678]|9[89])\d{8}$"


def is_valid_phone(phone: str | None) -> bool:
    return phone is not None and re.fullmatch(PHONE_PATTERN, phone) is not None


async def send_code(phone: str, redis: Redis) -> ApiResult:
    if not is_valid_phone(phone):
        return ApiResult.fail("手机号格式错误")

    code = f"{secrets.randbelow(1_000_000):06d}"
    await redis.set(f"{LOGIN_CODE_KEY}{phone}", code, ex=LOGIN_CODE_TTL_MINUTES * 60)
    # SMS is not configured in this project yet; the code is stored as in the Java service.
    return ApiResult.ok()


async def login(form: LoginForm, session: AsyncSession, redis: Redis) -> ApiResult:
    if not is_valid_phone(form.phone):
        return ApiResult.fail("手机号格式错误")

    cached_code = await redis.get(f"{LOGIN_CODE_KEY}{form.phone}")
    if cached_code is None or cached_code != form.code:
        return ApiResult.fail("验证码错误")

    user = await session.scalar(select(User).where(User.phone == form.phone))
    if user is None:
        nickname = USER_NICK_NAME_PREFIX + "".join(
            secrets.choice(string.ascii_lowercase + string.digits) for _ in range(10)
        )
        user = User(phone=form.phone, nick_name=nickname)
        session.add(user)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            user = await session.scalar(select(User).where(User.phone == form.phone))
            if user is None:
                raise
        else:
            await session.refresh(user)

    token = secrets.token_hex(16)
    user_dto = UserDTO.model_validate(user)
    token_key = f"{LOGIN_USER_KEY}{token}"
    await redis.hset(
        token_key,
        mapping={key: str(value) for key, value in user_dto.model_dump(by_alias=True).items() if value is not None},
    )
    await redis.expire(token_key, LOGIN_USER_TTL_MINUTES * 60)
    return ApiResult.ok(token)


async def get_user(user_id: int, session: AsyncSession) -> ApiResult:
    user = await session.get(User, user_id)
    if user is None:
        return ApiResult.ok()
    return ApiResult.ok(UserDTO.model_validate(user).model_dump(by_alias=True, exclude_none=True))


async def get_user_info(user_id: int, session: AsyncSession) -> ApiResult:
    info = await session.get(UserInfo, user_id)
    if info is None:
        return ApiResult.ok()
    return ApiResult.ok(UserInfoBase.model_validate(info).model_dump(by_alias=True, exclude_none=True))


async def sign(user_id: int, redis: Redis) -> ApiResult:
    today = date.today()
    key = f"{USER_SIGN_KEY}{user_id}:{today:%Y%m}"
    await redis.setbit(key, today.day - 1, 1)
    return ApiResult.ok()


async def sign_count(user_id: int, redis: Redis) -> ApiResult:
    today = date.today()
    key = f"{USER_SIGN_KEY}{user_id}:{today:%Y%m}"
    bits = await redis.execute_command("BITFIELD", key, "GET", f"u{today.day}", 0)
    number = bits[0] if bits else 0
    count = 0
    while number & 1:
        count += 1
        number >>= 1
    return ApiResult.ok(count)
