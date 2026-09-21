from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.tables import Campaign, CampaignProspect, ProspectMessage
from app.schemas.replies import CallTurnIn, DaysIn, ReplyIn
from app.services import calls, outreach, replies
from app.services.campaign_service import ServiceError, get_or_404

router = APIRouter(tags=["conversations"])


@router.post("/prospects/{prospect_id}/send")
def send_one(prospect_id: str, db: Session = Depends(get_db)):
    p = replies.get_prospect(db, prospect_id)
    return outreach.send_first_touch(db, get_or_404(db, p.campaign_id), p)


@router.post("/campaigns/{campaign_id}/send-ready")
def send_ready(campaign_id: str, limit: int = 50, db: Session = Depends(get_db)):
    return outreach.send_ready(db, get_or_404(db, campaign_id), limit)


@router.get("/prospects/{prospect_id}/messages")
def list_messages(prospect_id: str, db: Session = Depends(get_db)):
    replies.get_prospect(db, prospect_id)
    return replies.messages(db, prospect_id)


@router.post("/prospects/{prospect_id}/reply", status_code=202)
def reply(prospect_id: str, body: ReplyIn, db: Session = Depends(get_db)):
    return replies.receive_reply(db, prospect_id, body.channel, body.text)


@router.post("/messages/{message_id}/send")
def send_draft(message_id: str, db: Session = Depends(get_db)):
    m = db.get(ProspectMessage, message_id)
    if m is None:
        raise ServiceError("Message not found", 404)
    if m.status != "draft":
        raise ServiceError("Only drafts can be sent", 409)
    r = outreach.send_existing(db, db.get(Campaign, m.campaign_id), db.get(CampaignProspect, m.prospect_id), m)
    db.commit()
    return r


@router.post("/campaigns/{campaign_id}/followups/run")
def run_followups(campaign_id: str, db: Session = Depends(get_db)):
    return replies.run_followups(db, get_or_404(db, campaign_id))


@router.post("/campaigns/{campaign_id}/simulate-days")
def simulate_days(campaign_id: str, body: DaysIn, db: Session = Depends(get_db)):
    return replies.simulate_days(db, get_or_404(db, campaign_id), body.days)


@router.post("/prospects/{prospect_id}/meeting")
def book_meeting(prospect_id: str, db: Session = Depends(get_db)):
    return replies.book_meeting(db, prospect_id)


@router.post("/prospects/{prospect_id}/call/start")
def call_start(prospect_id: str, db: Session = Depends(get_db)):
    return calls.start(db, prospect_id)


@router.post("/prospects/{prospect_id}/call/turn")
def call_turn(prospect_id: str, body: CallTurnIn, db: Session = Depends(get_db)):
    return calls.turn(db, prospect_id, body.said)


@router.post("/prospects/{prospect_id}/call/end")
def call_end(prospect_id: str, db: Session = Depends(get_db)):
    return calls.end(db, prospect_id)