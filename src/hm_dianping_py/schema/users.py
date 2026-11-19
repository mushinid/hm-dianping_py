from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class LoginForm(BaseModel):
    phone: str | None = None
    code: str | None = None
    password: str | None = None


class UserDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)

    id: int
    nick_name: str | None = None
    icon: str | None = None


class UserInfoBase(BaseModel):
    """Fields exposed by the existing tb_user_info API."""

    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)

    user_id: int
    city: str | None = None
    introduce: str | None = None
    fans: int | None = None
    followee: int | None = None
    gender: bool | None = None
    birthday: date | None = None
    credits: int | None = None
    level: int | None = None


class ApiResult(BaseModel):
    success: bool
    error_msg: str | None = Field(default=None, serialization_alias="errorMsg")
    data: Any = None
    total: int | None = None

    @classmethod
    def ok(cls, data: Any = None) -> "ApiResult":
        return cls(success=True, data=data)

    @classmethod
    def fail(cls, message: str) -> "ApiResult":
        return cls(success=False, error_msg=message)
