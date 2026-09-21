from pydantic import Field

from app.schemas.campaign import CamelModel


class StartIn(CamelModel):
    target_count: int = Field(ge=1, le=500)
    objective: str = "Book a product discovery meeting"
    cta: str = Field("Would you be open to a 15-minute call next week?", min_length=3)
    tone: str = "Friendly, direct and concise"
    industries: list[str] = []
    pain_points: list[str] = []
    company_size_min: int = Field(0, ge=0)
    company_size_max: int = Field(100000, ge=1)