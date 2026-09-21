from pydantic import Field

from app.schemas.campaign import CamelModel, ChannelKey


class ReplyIn(CamelModel):
    channel: ChannelKey = "email"
    text: str = Field(min_length=1, max_length=5000)


class DaysIn(CamelModel):
    days: int = Field(ge=1, le=30)


class CallTurnIn(CamelModel):
    said: str = Field(min_length=1, max_length=2000)