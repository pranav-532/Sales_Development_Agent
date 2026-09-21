from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.ops import PromptActivate, PromptSave
from app.services import prompt_service as svc

router = APIRouter(tags=["prompts"])


@router.get("/prompts")
def all_prompts(campaign_id: Optional[str] = None, db: Session = Depends(get_db)):
    return svc.list_prompts(db, campaign_id)


@router.get("/audit")
def audit(campaign_id: Optional[str] = None, db: Session = Depends(get_db)):
    return svc.list_audit(db, campaign_id)


@router.post("/campaigns/{campaign_id}/prompts", status_code=201)
def save(campaign_id: str, body: PromptSave, db: Session = Depends(get_db)):
    return svc.save_version(db, campaign_id, body.scope, body.content, body.note)


@router.post("/campaigns/{campaign_id}/prompts/activate")
def activate(campaign_id: str, body: PromptActivate, db: Session = Depends(get_db)):
    return svc.activate_version(db, campaign_id, body.scope, body.version)