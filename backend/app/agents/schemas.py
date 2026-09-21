from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

Channel = Literal["linkedin", "email", "sms", "voice"]


class Lenient(BaseModel):
    model_config = ConfigDict(extra="ignore")

    @field_validator("*", mode="before")
    @classmethod
    def _lists(cls, v, info):
        f = cls.model_fields.get(info.field_name)
        if f is not None and f.annotation == list[str]:
            if v is None:
                return []
            if isinstance(v, str):
                return [v] if v.strip() else []
        return v


def _unit(v):
    if isinstance(v, (int, float)) and 1 < v <= 100:
        return v / 100
    return v


class IcpOut(Lenient):
    qualified: bool
    score: int
    reasons: list[str] = []
    pain_points: list[str] = []
    missing_information: list[str] = []
    requires_human_review: bool = False

    @field_validator("score", mode="before")
    @classmethod
    def _score(cls, v):
        return max(0, min(100, round(v))) if isinstance(v, (int, float)) else v


class ResearchOut(Lenient):
    company_industry: str = ""
    company_summary: str = ""
    professional_context: str = ""
    signals: list[str] = []
    tech_stack_hints: list[str] = []
    sources_used: list[str] = []
    confidence: float = Field(default=0.5, ge=0, le=1)
    missing_information: list[str] = []
    requires_human_review: bool = False

    @field_validator("confidence", mode="before")
    @classmethod
    def _conf(cls, v):
        return _unit(v)


_CHANNEL_ALIASES = {"phone": "voice", "call": "voice", "text": "sms", "linkedin_dm": "linkedin"}


def _channel(v):
    """Models write 'Email', 'Phone' or 'LinkedIn'. Normalise, and let strategy.py drop anything unusable."""
    if isinstance(v, str):
        v = v.strip().lower().replace(" ", "_")
        return _CHANNEL_ALIASES.get(v, v)
    return v


class Step(Lenient):
    step: int = 1
    channel: str
    purpose: str = ""

    @field_validator("channel", mode="before")
    @classmethod
    def _ch(cls, v):
        return _channel(v)


class StrategyOut(Lenient):
    primary_channel: str
    secondary_channel: Optional[str] = None

    @field_validator("primary_channel", "secondary_channel", mode="before")
    @classmethod
    def _ch(cls, v):
        return _channel(v)

    objective: str = ""
    sequence: list[Step] = []
    reasoning: str = ""
    requires_human_review: bool = False


class MessageOut(Lenient):
    subject: str = ""
    body: str
    personalization_points: list[str] = []
    cta: str = ""
    confidence: float = Field(default=0.5, ge=0, le=1)
    knowledge_sources_used: list[str] = []
    requires_human_review: bool = False

    @field_validator("confidence", mode="before")
    @classmethod
    def _conf(cls, v):
        return _unit(v)



# ---------- reply handling, voice and follow-up ----------
Intent = Literal[
    "interested", "wants_meeting", "wants_call", "asking_question", "objection",
    "not_interested", "unsubscribe", "out_of_office", "not_now", "unclear",
]
Sentiment = Literal["positive", "neutral", "negative"]
CallOutcome = Literal["continuing", "meeting_agreed", "callback_requested", "not_interested", "needs_human"]

_INTENT_ALIASES = {
    "wants_demo": "wants_meeting", "meeting": "wants_meeting", "book_meeting": "wants_meeting",
    "question": "asking_question", "asks_question": "asking_question", "not_interest": "not_interested",
    "no_interest": "not_interested", "decline": "not_interested", "stop": "unsubscribe", "opt_out": "unsubscribe",
    "ooo": "out_of_office", "later": "not_now", "neutral": "unclear",
}
_OUTCOME_ALIASES = {
    "meeting": "meeting_agreed", "booked": "meeting_agreed", "callback": "callback_requested",
    "call_back": "callback_requested", "declined": "not_interested", "no": "not_interested",
    "human": "needs_human", "transfer": "needs_human", "escalate": "needs_human",
}


def _norm(v):
    return str(v).strip().lower().replace(" ", "_").replace("-", "_") if isinstance(v, str) else v


class ConversationOut(Lenient):
    intent: Intent
    sentiment: Sentiment = "neutral"
    summary: str = ""
    topics: list[str] = []
    response_required: bool = True
    reply_draft: str = ""
    requires_human_review: bool = False
    confidence: float = Field(default=0.5, ge=0, le=1)

    @field_validator("intent", mode="before")
    @classmethod
    def _intent(cls, v):
        v = _norm(v)
        v = _INTENT_ALIASES.get(v, v)
        return v if v in Intent.__args__ else "unclear"

    @field_validator("sentiment", mode="before")
    @classmethod
    def _sent(cls, v):
        v = _norm(v)
        return v if v in Sentiment.__args__ else "neutral"

    @field_validator("topics", mode="after")
    @classmethod
    def _topics(cls, v):
        return [_norm(t) for t in v]

    @field_validator("confidence", mode="before")
    @classmethod
    def _conf(cls, v):
        return _unit(v)


class VoiceDecisionOut(Lenient):
    should_call: bool = True
    opening_script: str = ""
    talking_points: list[str] = []
    reasoning: str = ""


class _Outcome(Lenient):
    outcome: CallOutcome = "continuing"

    @field_validator("outcome", mode="before")
    @classmethod
    def _out(cls, v):
        v = _norm(v)
        v = _OUTCOME_ALIASES.get(v, v)
        return v if v in CallOutcome.__args__ else "continuing"


class VoiceTurnOut(_Outcome):
    say: str
    end_call: bool = False
    transfer_to_human: bool = False


class VoiceSummaryOut(_Outcome):
    summary: str = ""
    next_step: str = ""
    requires_human_review: bool = False


class FollowupDraftOut(Lenient):
    subject: str = ""
    body: str
    requires_human_review: bool = False