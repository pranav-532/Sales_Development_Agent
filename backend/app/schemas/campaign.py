from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

Status = Literal["draft", "live", "paused", "completed", "archived"]
ChannelKey = Literal["linkedin", "email", "sms", "voice"]
Approval = Literal["none", "first_touch", "all"]


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class AgentIn(CamelModel):
    key: str
    name: str
    enabled: bool = True
    paused: bool = False


class ChannelIn(CamelModel):
    channel: ChannelKey
    enabled: bool
    paused: bool = False
    daily_limit: int = Field(ge=0)


class CampaignCreate(CamelModel):
    name: str = Field(min_length=1)
    description: str = ""
    owner: str = Field(min_length=1)
    icp: str = Field(min_length=1)
    geography: str = ""
    target_roles: list[str] = []
    company_criteria: str = ""
    exclusions: str = ""
    reference_profiles: str = ""
    approval_mode: Approval = "first_touch"
    qualify_threshold: int = Field(70, ge=0, le=100)
    confidence_threshold: int = Field(60, ge=0, le=100)
    escalate_on: list[str] = []
    agents: list[AgentIn]
    channels: list[ChannelIn]
    rep_ids: list[str] = []
    system_prompt: str = ""
    go_live: bool = False


class CampaignUpdate(CamelModel):
    name: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
    owner: Optional[str] = None
    icp: Optional[str] = Field(None, min_length=1)
    geography: Optional[str] = None
    target_roles: Optional[list[str]] = None
    company_criteria: Optional[str] = None
    exclusions: Optional[str] = None
    reference_profiles: Optional[str] = None
    approval_mode: Optional[Approval] = None
    qualify_threshold: Optional[int] = Field(None, ge=0, le=100)
    confidence_threshold: Optional[int] = Field(None, ge=0, le=100)
    escalate_on: Optional[list[str]] = None
    agents: Optional[list[AgentIn]] = None
    channels: Optional[list[ChannelIn]] = None
    rep_ids: Optional[list[str]] = None


class StatusIn(CamelModel):
    status: Status


class KillSwitchIn(CamelModel):
    on: bool


class CheckIn(CamelModel):
    campaign_id: str
    agent_key: str
    channel: Optional[ChannelKey] = None
    prospect_email: Optional[str] = None