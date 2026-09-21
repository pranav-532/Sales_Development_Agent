"""Prospect states after the first message is ready to send. Before that, services/pipeline.py owns the states."""
from app.models.tables import CampaignProspect

POST_SEND = {
    "READY_TO_SEND": {"OUTREACH_SENT"},
    "OUTREACH_SENT": {"WAITING_FOR_RESPONSE", "RESPONSE_RECEIVED", "COMPLETED"},
    "WAITING_FOR_RESPONSE": {"RESPONSE_RECEIVED", "FOLLOWUP_DUE", "COMPLETED", "VOICE_PENDING"},
    "FOLLOWUP_DUE": {"OUTREACH_SENT", "RESPONSE_RECEIVED", "COMPLETED", "VOICE_PENDING"},
    "RESPONSE_RECEIVED": {"CONVERSATION_ACTIVE"},
    "CONVERSATION_ACTIVE": {"MEETING_PENDING", "VOICE_PENDING", "FOLLOWUP_DUE", "HUMAN_REVIEW", "RESPONSE_RECEIVED", "COMPLETED"},
    "VOICE_PENDING": {"MEETING_PENDING", "FOLLOWUP_DUE", "HUMAN_REVIEW", "CONVERSATION_ACTIVE", "RESPONSE_RECEIVED"},
    "MEETING_PENDING": {"MEETING_BOOKED", "CONVERSATION_ACTIVE", "VOICE_PENDING", "RESPONSE_RECEIVED"},
    "MEETING_BOOKED": {"COMPLETED", "RESPONSE_RECEIVED"},
    "HUMAN_REVIEW": {"CONVERSATION_ACTIVE", "MEETING_PENDING", "RESPONSE_RECEIVED"},
    "COMPLETED": {"RESPONSE_RECEIVED"},
}
ANYTIME = {"STOPPED", "FAILED"}


def can_advance(p: CampaignProspect, new: str) -> bool:
    return new == p.state or new in ANYTIME or new in POST_SEND.get(p.state, set())


def advance(p: CampaignProspect, new: str) -> None:
    if not can_advance(p, new):
        raise ValueError(f"Invalid transition {p.state} -> {new}")
    p.state = new


def try_advance(p: CampaignProspect, new: str) -> bool:
    if can_advance(p, new):
        p.state = new
        return True
    return False