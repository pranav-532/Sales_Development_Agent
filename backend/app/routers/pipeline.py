from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.tables import CampaignProspect
from app.schemas.pipeline import StartIn
from app.services import pipeline
from app.services.campaign_service import ServiceError, get_or_404

router = APIRouter(tags=["pipeline"])


@router.post("/campaigns/{campaign_id}/start", status_code=202)
def start(campaign_id: str, body: StartIn, db: Session = Depends(get_db)):
    c = get_or_404(db, campaign_id)
    return pipeline.start(db, c, body.model_dump(by_alias=True))


@router.get("/campaigns/{campaign_id}/pipeline")
def summary(campaign_id: str, db: Session = Depends(get_db)):
    return pipeline.summary(db, get_or_404(db, campaign_id))


@router.get("/campaigns/{campaign_id}/prospects")
def prospects(campaign_id: str, state: Optional[str] = None, limit: int = 200, db: Session = Depends(get_db)):
    get_or_404(db, campaign_id)
    q = select(CampaignProspect).where(CampaignProspect.campaign_id == campaign_id)
    if state:
        q = q.where(CampaignProspect.state == state)
    rows = db.scalars(q.order_by(CampaignProspect.created_at, CampaignProspect.id).limit(max(1, min(limit, 1000)))).all()
    return [p.to_dict() for p in rows]


@router.get("/prospects/{prospect_id}")
def prospect(prospect_id: str, db: Session = Depends(get_db)):
    p = db.get(CampaignProspect, prospect_id)
    if p is None:
        raise ServiceError("Prospect not found", 404)
    return p.to_dict(full=True)


@router.post("/prospects/{prospect_id}/retry")
def retry(prospect_id: str, db: Session = Depends(get_db)):
    return pipeline.retry(db, prospect_id).to_dict()