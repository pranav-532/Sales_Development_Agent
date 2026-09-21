from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.campaign import CheckIn, KillSwitchIn
from app.services.guard import can_act, get_kill_switch, set_kill_switch

router = APIRouter(prefix="/control", tags=["control"])


@router.get("/state")
def state(db: Session = Depends(get_db)):
    return {"killSwitch": get_kill_switch(db)}


@router.post("/kill-switch")
def kill_switch(body: KillSwitchIn, db: Session = Depends(get_db)):
    return {"killSwitch": set_kill_switch(db, body.on)}


@router.post("/check")
def check(body: CheckIn, db: Session = Depends(get_db)):
    """Ask the guard whether an agent may act. Agents call this before every action."""
    return can_act(db, body.campaign_id, body.agent_key, body.channel, body.prospect_email).to_dict()