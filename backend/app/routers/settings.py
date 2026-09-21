from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.settings import (
    AuthIn, ConnectIn, EnabledIn, InviteIn, KbIn, PoliciesIn, RoleIn, RoutingIn, SuppressIn,
)
from app.services import settings_service as svc

router = APIRouter(tags=["settings"])


@router.get("/settings")
def all_settings(db: Session = Depends(get_db)):
    return svc.get_all(db)


@router.put("/settings/guardrails/{gid}")
def guardrail(gid: str, body: EnabledIn, db: Session = Depends(get_db)):
    return svc.set_guardrail(db, gid, body.enabled)


@router.put("/settings/tools/{tid}")
def tool(tid: str, body: EnabledIn, db: Session = Depends(get_db)):
    return svc.set_tool(db, tid, body.enabled)


@router.put("/settings/models/{mid}")
def model(mid: str, body: EnabledIn, db: Session = Depends(get_db)):
    return svc.set_model(db, mid, body.enabled)


@router.put("/settings/routing")
def routing(body: RoutingIn, db: Session = Depends(get_db)):
    return svc.set_routing(db, body.task, body.model_id)


@router.put("/settings/policies")
def policies(body: PoliciesIn, db: Session = Depends(get_db)):
    return svc.set_policies(db, body.daily_cap, body.window_start, body.window_end)


@router.put("/settings/auth")
def auth(body: AuthIn, db: Session = Depends(get_db)):
    return svc.set_auth(db, body.sso, body.mfa)


@router.post("/settings/knowledge", status_code=201)
def kb_add(body: KbIn, db: Session = Depends(get_db)):
    return svc.add_kb(db, body.name, body.description)


@router.put("/settings/knowledge/{kid}")
def kb_set(kid: str, body: EnabledIn, db: Session = Depends(get_db)):
    return svc.set_kb(db, kid, body.enabled)


@router.delete("/settings/knowledge/{kid}", status_code=204)
def kb_remove(kid: str, db: Session = Depends(get_db)):
    svc.remove_kb(db, kid)


@router.post("/settings/users", status_code=201)
def user_invite(body: InviteIn, db: Session = Depends(get_db)):
    return svc.invite_user(db, body.name, body.email, body.role)


@router.put("/settings/users/{uid}/role")
def user_role(uid: str, body: RoleIn, db: Session = Depends(get_db)):
    return svc.set_role(db, uid, body.role)


@router.delete("/settings/users/{uid}", status_code=204)
def user_remove(uid: str, db: Session = Depends(get_db)):
    svc.remove_user(db, uid)


@router.post("/settings/integrations/{iid}/connect")
def connect(iid: str, body: ConnectIn, db: Session = Depends(get_db)):
    return svc.connect_integration(db, iid, body.account, body.key)


@router.post("/settings/integrations/{iid}/disconnect")
def disconnect(iid: str, db: Session = Depends(get_db)):
    return svc.disconnect_integration(db, iid)


@router.get("/suppressions")
def suppressions(db: Session = Depends(get_db)):
    return svc.list_suppressions(db)


@router.post("/suppressions", status_code=201)
def suppression_add(body: SuppressIn, db: Session = Depends(get_db)):
    return svc.add_suppression(db, body.value, body.reason)


@router.delete("/suppressions/{sid}", status_code=204)
def suppression_remove(sid: str, db: Session = Depends(get_db)):
    svc.remove_suppression(db, sid)