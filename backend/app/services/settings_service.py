import copy
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tables import GlobalState, Suppression
from app.services.campaign_service import CURRENT_USER, ServiceError, _id, _today

CURRENT_USER_ID = "u1"
EMAIL_RE = re.compile(r"^\S+@\S+\.\S+$")
DOMAIN_RE = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$")
DOTS = "\u2022" * 4


def _load(db: Session) -> dict:
    row = db.get(GlobalState, "settings")
    return copy.deepcopy(row.value) if row else {}


def _save(db: Session, data: dict) -> None:
    row = db.get(GlobalState, "settings")
    if row is None:
        db.add(GlobalState(key="settings", value=data))
    else:
        row.value = data
    db.commit()


def _find(items: list[dict], key: str, value: str, what: str) -> dict:
    hit = next((i for i in items if i[key] == value), None)
    if hit is None:
        raise ServiceError(f"{what} not found", 404)
    return hit


def get_all(db: Session) -> dict:
    data = _load(db)
    data["currentUserId"] = CURRENT_USER_ID
    return data


def set_guardrail(db: Session, gid: str, enabled: bool) -> dict:
    data = _load(db)
    g = _find(data["guardrails"], "id", gid, "Guardrail")
    if g.get("locked") and not enabled:
        raise ServiceError("This guardrail is always on", 409)
    g["enabled"] = enabled
    _save(db, data)
    return g


def set_tool(db: Session, tid: str, enabled: bool) -> dict:
    data = _load(db)
    t = _find(data["tools"], "id", tid, "Tool")
    t["enabled"] = enabled
    _save(db, data)
    return t


def set_model(db: Session, mid: str, enabled: bool) -> dict:
    data = _load(db)
    m = _find(data["models"], "id", mid, "Model")
    if not enabled and any(r["modelId"] == mid for r in data["routing"]):
        raise ServiceError("Reassign the tasks that use this model before disabling it", 409)
    m["enabled"] = enabled
    _save(db, data)
    return m


def set_routing(db: Session, task: str, model_id: str) -> dict:
    data = _load(db)
    r = _find(data["routing"], "task", task, "Task")
    m = _find(data["models"], "id", model_id, "Model")
    if not m["enabled"]:
        raise ServiceError("That model is disabled", 422)
    r["modelId"] = model_id
    _save(db, data)
    return r


def set_policies(db: Session, daily_cap, window_start, window_end) -> dict:
    data = _load(db)
    p = data["policies"]
    if daily_cap is not None:
        p["dailyCap"] = daily_cap
    if window_start is not None:
        p["windowStart"] = window_start
    if window_end is not None:
        p["windowEnd"] = window_end
    if p["windowEnd"] <= p["windowStart"]:
        raise ServiceError("The sending window must end after it starts", 422)
    _save(db, data)
    return p


def set_auth(db: Session, sso, mfa) -> dict:
    data = _load(db)
    if sso is not None:
        data["auth"]["sso"] = sso
    if mfa is not None:
        data["auth"]["mfa"] = mfa
    _save(db, data)
    return data["auth"]


def add_kb(db: Session, name: str, description: str) -> dict:
    data = _load(db)
    if any(k["name"].strip().lower() == name.strip().lower() for k in data["knowledge"]):
        raise ServiceError("A knowledge base with this name exists", 409)
    kb = {
        "id": _id("kb"), "name": name.strip(), "description": description.strip(),
        "docs": 0, "updated": _today(), "enabled": True,
    }
    data["knowledge"].append(kb)
    _save(db, data)
    return kb


def set_kb(db: Session, kid: str, enabled: bool) -> dict:
    data = _load(db)
    kb = _find(data["knowledge"], "id", kid, "Knowledge base")
    kb["enabled"] = enabled
    _save(db, data)
    return kb


def remove_kb(db: Session, kid: str) -> None:
    data = _load(db)
    _find(data["knowledge"], "id", kid, "Knowledge base")
    data["knowledge"] = [k for k in data["knowledge"] if k["id"] != kid]
    _save(db, data)


def invite_user(db: Session, name: str, email: str, role: str) -> dict:
    data = _load(db)
    e = email.strip().lower()
    if not EMAIL_RE.match(e):
        raise ServiceError("Enter a valid email", 422)
    if any(u["email"].lower() == e for u in data["users"]):
        raise ServiceError("This email is already on the team", 409)
    user = {"id": _id("u"), "name": name.strip(), "email": e, "role": role}
    data["users"].append(user)
    _save(db, data)
    return user


def set_role(db: Session, uid: str, role: str) -> dict:
    if uid == CURRENT_USER_ID:
        raise ServiceError("You cannot change your own role", 409)
    data = _load(db)
    u = _find(data["users"], "id", uid, "User")
    u["role"] = role
    _save(db, data)
    return u


def remove_user(db: Session, uid: str) -> None:
    if uid == CURRENT_USER_ID:
        raise ServiceError("You cannot remove yourself", 409)
    data = _load(db)
    _find(data["users"], "id", uid, "User")
    data["users"] = [u for u in data["users"] if u["id"] != uid]
    _save(db, data)


def connect_integration(db: Session, iid: str, account: str, key: str) -> dict:
    data = _load(db)
    i = _find(data["integrations"], "id", iid, "Integration")
    i.update(status="connected", account=account.strip(), keyHint=f"{DOTS}{key.strip()[-4:]}", lastSync="Just now")
    i.pop("message", None)
    _save(db, data)  # the key itself is never stored
    return i


def disconnect_integration(db: Session, iid: str) -> dict:
    data = _load(db)
    i = _find(data["integrations"], "id", iid, "Integration")
    if i.get("required"):
        raise ServiceError("This integration is required", 409)
    i.update(status="disconnected", account="", keyHint="", lastSync="Never")
    i.pop("message", None)
    _save(db, data)
    return i


def suppression_dict(s: Suppression) -> dict:
    return {
        "id": s.id, "value": s.value, "type": s.type, "reason": s.reason,
        "addedBy": s.added_by, "addedAt": s.added_at,
    }


def list_suppressions(db: Session) -> list[dict]:
    rows = db.scalars(select(Suppression).order_by(Suppression.added_at.desc(), Suppression.id.desc())).all()
    return [suppression_dict(s) for s in rows]


def add_suppression(db: Session, value: str, reason: str) -> dict:
    v = value.strip().lower()
    if not v:
        raise ServiceError("Enter an email or a domain", 422)
    is_email = "@" in v
    if is_email and not EMAIL_RE.match(v):
        raise ServiceError("That is not a valid email", 422)
    if not is_email and not DOMAIN_RE.match(v):
        raise ServiceError("That is not a valid domain, for example example.com", 422)
    if db.scalar(select(Suppression).where(Suppression.value == v)):
        raise ServiceError("Already on the list", 409)
    row = Suppression(
        id=_id("s"), value=v, type="email" if is_email else "domain",
        reason=reason.strip() or "Added manually", added_by=CURRENT_USER, added_at=_today(),
    )
    db.add(row)
    db.commit()
    return suppression_dict(row)


def remove_suppression(db: Session, sid: str) -> None:
    row = db.get(Suppression, sid)
    if row is None:
        raise ServiceError("Not on the list", 404)
    db.delete(row)
    db.commit()