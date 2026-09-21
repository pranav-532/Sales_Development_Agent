from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.ops import DecisionIn
from app.services import activity_service as svc

router = APIRouter(tags=["activity"])


@router.get("/campaigns/{campaign_id}/activity")
def activity(campaign_id: str, limit: int = 100, db: Session = Depends(get_db)):
    return svc.list_events(db, campaign_id, limit)


@router.get("/campaigns/{campaign_id}/stats")
def stats(campaign_id: str, db: Session = Depends(get_db)):
    return svc.get_stats(db, campaign_id)


@router.post("/activity/{event_id}/decision")
def decision(event_id: str, body: DecisionIn, db: Session = Depends(get_db)):
    return svc.decide(db, event_id, body.decision)