from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tables import Campaign, Rep
from app.schemas.ops import OffboardIn, RepCreate, RepUpdate
from app.services.campaign_service import ServiceError, _id, _require_editable, _today, get_or_404

OPEN = {"draft", "live", "paused"}


def get_rep(db: Session, rep_id: str) -> Rep:
    r = db.get(Rep, rep_id)
    if r is None:
        raise ServiceError("Rep not found", 404)
    return r


def _email_taken(db: Session, email: str, exclude_id: str | None = None) -> bool:
    rows = db.scalars(select(Rep)).all()
    return any(r.id != exclude_id and r.email.lower() == email.strip().lower() for r in rows)


def _open_campaigns(db: Session) -> list[Campaign]:
    return [c for c in db.scalars(select(Campaign)).all() if c.status in OPEN]


def create_rep(db: Session, body: RepCreate) -> Rep:
    if _email_taken(db, body.email):
        raise ServiceError("Another rep uses this email", 409)
    r = Rep(
        id=_id("r"), name=body.name.strip(), email=body.email.strip(), status="active",
        daily_limit=body.daily_limit, working_hours=body.working_hours, channels=list(body.channels),
    )
    db.add(r)
    db.commit()
    return r


def update_rep(db: Session, rep_id: str, body: RepUpdate) -> Rep:
    r = get_rep(db, rep_id)
    if r.status == "offboarded":
        raise ServiceError("Reactivate this rep before editing", 409)
    f = body.model_dump(exclude_unset=True)
    if f.get("email") and _email_taken(db, f["email"], exclude_id=r.id):
        raise ServiceError("Another rep uses this email", 409)
    for key in ("name", "email", "daily_limit", "working_hours", "channels"):
        if f.get(key) is not None:
            setattr(r, key, f[key])
    db.commit()
    return r


def reactivate(db: Session, rep_id: str) -> Rep:
    r = get_rep(db, rep_id)
    r.status = "active"
    db.commit()
    return r


def impact(db: Session, rep_id: str) -> list[dict]:
    get_rep(db, rep_id)
    return [
        {"id": c.id, "name": c.name, "status": c.status, "repCount": len(c.rep_ids)}
        for c in _open_campaigns(db)
        if rep_id in c.rep_ids
    ]


def assign(db: Session, campaign_id: str, rep_id: str) -> Campaign:
    c = get_or_404(db, campaign_id)
    _require_editable(c)
    r = get_rep(db, rep_id)
    if r.status != "active":
        raise ServiceError("Only active reps can be assigned", 409)
    if rep_id not in c.rep_ids:
        c.rep_ids = [*c.rep_ids, rep_id]
        c.updated_at = _today()
        db.commit()
    return c


def set_rep_campaigns(db: Session, rep_id: str, campaign_ids: list[str]) -> list[dict]:
    r = get_rep(db, rep_id)
    if r.status != "active":
        raise ServiceError("Only active reps can be assigned", 409)
    for c in _open_campaigns(db):
        has = rep_id in c.rep_ids
        want = c.id in campaign_ids
        if has == want:
            continue
        c.rep_ids = [*c.rep_ids, rep_id] if want else [x for x in c.rep_ids if x != rep_id]
        c.updated_at = _today()
    db.commit()
    return impact(db, rep_id)


def offboard(db: Session, rep_id: str, body: OffboardIn) -> dict:
    r = get_rep(db, rep_id)
    if r.status == "offboarded":
        raise ServiceError("This rep is already offboarded", 409)

    for target in body.replacements.values():
        if target == "none":
            continue
        rep = db.get(Rep, target)
        if rep is None or rep.status != "active" or rep.id == rep_id:
            raise ServiceError(f"Cannot use {target} as a replacement", 422)

    uncovered = []
    for c in _open_campaigns(db):
        if rep_id not in c.rep_ids:
            continue
        nxt = [x for x in c.rep_ids if x != rep_id]
        replacement = body.replacements.get(c.id)
        if replacement and replacement != "none" and replacement not in nxt:
            nxt.append(replacement)
        c.rep_ids = nxt
        c.updated_at = _today()
        if not nxt and c.status != "draft":
            uncovered.append({"id": c.id, "name": c.name, "status": c.status})

    r.status = "offboarded"
    db.commit()
    return {"rep": r.to_dict(), "campaignsWithoutRep": uncovered}