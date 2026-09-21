from typing import Literal, Optional

from pydantic import Field

from app.schemas.campaign import CamelModel


class EnabledIn(CamelModel):
    enabled: bool


class RoutingIn(CamelModel):
    task: str
    model_id: str


class PoliciesIn(CamelModel):
    daily_cap: Optional[int] = Field(None, ge=1, le=1000000)
    window_start: Optional[int] = Field(None, ge=0, le=22)
    window_end: Optional[int] = Field(None, ge=1, le=23)


class AuthIn(CamelModel):
    sso: Optional[bool] = None
    mfa: Optional[bool] = None


class KbIn(CamelModel):
    name: str = Field(min_length=1)
    description: str = ""


class InviteIn(CamelModel):
    name: str = Field(min_length=1)
    email: str
    role: Literal["admin", "manager", "viewer"] = "manager"


class RoleIn(CamelModel):
    role: Literal["admin", "manager", "viewer"]


class ConnectIn(CamelModel):
    account: str = Field(min_length=1)
    key: str = Field(min_length=4)


class SuppressIn(CamelModel):
    value: str
    reason: str = ""