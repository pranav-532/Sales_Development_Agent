from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.conflicts import ResolveIn, RulesIn
from app.services import conflict_service as svc

router = APIRouter(prefix="/conflicts", tags=["conflicts"])


@router.get("")
def list_all(db: Session = Depends(get_db)):
    return svc.list_conflicts(db)


@router.put("/rules")
def rules(body: RulesIn, db: Session = Depends(get_db)):
    svc.set_rules(db, body.max_touches, body.duplicate_window)
    return svc.list_conflicts(db)


@router.post("/{prospect_id}/resolve")
def resolve(prospect_id: str, body: ResolveIn, db: Session = Depends(get_db)):
    return svc.resolve(db, prospect_id, body.action, body.owner_id, body.days, body.note)


@router.post("/{prospect_id}/reopen")
def reopen(prospect_id: str, db: Session = Depends(get_db)):
    return svc.reopen(db, prospect_id)