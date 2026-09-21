from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.tables import Campaign
from app.schemas.campaign import CampaignCreate, CampaignUpdate, StatusIn
from app.services import campaign_service as svc

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("")
def list_campaigns(db: Session = Depends(get_db)):
    rows = db.scalars(select(Campaign).order_by(Campaign.created_at, Campaign.id)).all()
    return [c.to_dict() for c in rows]


@router.post("", status_code=201)
def create(body: CampaignCreate, db: Session = Depends(get_db)):
    return svc.create_campaign(db, body).to_dict()


@router.get("/{campaign_id}")
def get_one(campaign_id: str, db: Session = Depends(get_db)):
    return svc.get_or_404(db, campaign_id).to_dict()


@router.patch("/{campaign_id}")
def update(campaign_id: str, body: CampaignUpdate, db: Session = Depends(get_db)):
    return svc.update_campaign(db, campaign_id, body).to_dict()


@router.post("/{campaign_id}/status")
def change_status(campaign_id: str, body: StatusIn, db: Session = Depends(get_db)):
    return svc.set_status(db, campaign_id, body.status).to_dict()


@router.post("/{campaign_id}/duplicate", status_code=201)
def duplicate(campaign_id: str, db: Session = Depends(get_db)):
    return svc.duplicate_campaign(db, campaign_id).to_dict()


@router.post("/{campaign_id}/agents/{agent_key}/toggle")
def toggle_agent(campaign_id: str, agent_key: str, db: Session = Depends(get_db)):
    return svc.toggle_agent(db, campaign_id, agent_key).to_dict()


@router.post("/{campaign_id}/channels/{channel}/toggle")
def toggle_channel(campaign_id: str, channel: str, db: Session = Depends(get_db)):
    return svc.toggle_channel(db, campaign_id, channel).to_dict()