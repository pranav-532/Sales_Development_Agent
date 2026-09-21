from typing import Literal, Optional

from pydantic import Field

from app.schemas.campaign import CamelModel


class RulesIn(CamelModel):
    max_touches: int = Field(ge=1, le=50)
    duplicate_window: int = Field(ge=1, le=30)


class ResolveIn(CamelModel):
    action: Literal["owner", "cooldown", "dnc", "allow"]
    owner_id: Optional[str] = None
    days: Optional[int] = None
    note: str = ""