from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.tables import Rep
from app.schemas.ops import OffboardIn, RepCampaignsIn, RepCreate, RepUpdate
from app.services import rep_service as svc

router = APIRouter(tags=["reps"])


@router.get("/reps")
def list_reps(db: Session = Depends(get_db)):
    return [r.to_dict() for r in db.scalars(select(Rep).order_by(Rep.id)).all()]


@router.post("/reps", status_code=201)
def create(body: RepCreate, db: Session = Depends(get_db)):
    return svc.create_rep(db, body).to_dict()


@router.patch("/reps/{rep_id}")
def update(rep_id: str, body: RepUpdate, db: Session = Depends(get_db)):
    return svc.update_rep(db, rep_id, body).to_dict()


@router.post("/reps/{rep_id}/reactivate")
def reactivate(rep_id: str, db: Session = Depends(get_db)):
    return svc.reactivate(db, rep_id).to_dict()


@router.get("/reps/{rep_id}/impact")
def impact(rep_id: str, db: Session = Depends(get_db)):
    return svc.impact(db, rep_id)


@router.put("/reps/{rep_id}/campaigns")
def set_campaigns(rep_id: str, body: RepCampaignsIn, db: Session = Depends(get_db)):
    return svc.set_rep_campaigns(db, rep_id, body.campaign_ids)


@router.post("/reps/{rep_id}/offboard")
def offboard(rep_id: str, body: OffboardIn, db: Session = Depends(get_db)):
    return svc.offboard(db, rep_id, body)


@router.post("/campaigns/{campaign_id}/reps/{rep_id}")
def assign(campaign_id: str, rep_id: str, db: Session = Depends(get_db)):
    return svc.assign(db, campaign_id, rep_id).to_dict()