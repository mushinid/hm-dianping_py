from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from hm_dianping_py.config.constants import LOGIN_USER_KEY
from hm_dianping_py.controller.dependencies import get_current_user
from hm_dianping_py.db import get_session
from hm_dianping_py.schema.users import ApiResult, LoginForm, UserDTO
from hm_dianping_py.service import users as user_service

router = APIRouter(prefix="/user", tags=["user"])


@router.post("/code", response_model=ApiResult, response_model_exclude_none=True)
async def send_code(phone: str, request: Request) -> ApiResult:
    return await user_service.send_code(phone, request.app.state.redis)


@router.post("/login", response_model=ApiResult, response_model_exclude_none=True)
async def login(
    form: LoginForm,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ApiResult:
    return await user_service.login(form, session, request.app.state.redis)


@router.post("/logout", response_model=ApiResult, response_model_exclude_none=True)
async def logout(
    request: Request,
    _current_user: UserDTO = Depends(get_current_user),
    authorization: str | None = Header(default=None),
) -> ApiResult:
    if authorization:
        await request.app.state.redis.delete(f"{LOGIN_USER_KEY}{authorization}")
    return ApiResult.ok()


@router.get("/me", response_model=ApiResult, response_model_exclude_none=True)
async def me(current_user: UserDTO = Depends(get_current_user)) -> ApiResult:
    return ApiResult.ok(current_user.model_dump(by_alias=True, exclude_none=True))


@router.get("/info/{user_id}", response_model=ApiResult, response_model_exclude_none=True)
async def user_info(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    _current_user: UserDTO = Depends(get_current_user),
) -> ApiResult:
    return await user_service.get_user_info(user_id, session)


@router.get("/sign/count", response_model=ApiResult, response_model_exclude_none=True)
async def sign_count(
    request: Request,
    current_user: UserDTO = Depends(get_current_user),
) -> ApiResult:
    return await user_service.sign_count(current_user.id, request.app.state.redis)


@router.post("/sign", response_model=ApiResult, response_model_exclude_none=True)
async def sign(
    request: Request,
    current_user: UserDTO = Depends(get_current_user),
) -> ApiResult:
    return await user_service.sign(current_user.id, request.app.state.redis)


@router.get("/{user_id}", response_model=ApiResult, response_model_exclude_none=True)
async def get_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    _current_user: UserDTO = Depends(get_current_user),
) -> ApiResult:
    return await user_service.get_user(user_id, session)
