from typing import Literal, Optional

from pydantic import Field

from app.schemas.campaign import CamelModel, ChannelKey


class PromptSave(CamelModel):
    scope: str
    content: str
    note: str = ""


class PromptActivate(CamelModel):
    scope: str
    version: int = Field(ge=1)


class RepCreate(CamelModel):
    name: str = Field(min_length=1)
    email: str = Field(pattern=r"^\S+@\S+\.\S+$")
    daily_limit: int = Field(ge=1)
    working_hours: str = Field(min_length=1)
    channels: list[ChannelKey] = Field(min_length=1)


class RepUpdate(CamelModel):
    name: Optional[str] = Field(None, min_length=1)
    email: Optional[str] = Field(None, pattern=r"^\S+@\S+\.\S+$")
    daily_limit: Optional[int] = Field(None, ge=1)
    working_hours: Optional[str] = Field(None, min_length=1)
    channels: Optional[list[ChannelKey]] = Field(None, min_length=1)


class RepCampaignsIn(CamelModel):
    campaign_ids: list[str]


class OffboardIn(CamelModel):
    replacements: dict[str, str] = {}


class DecisionIn(CamelModel):
    decision: Literal["approved", "rejected"]