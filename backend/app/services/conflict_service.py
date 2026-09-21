from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tables import Campaign, ConflictResolution, GlobalState, Prospect, Suppression
from app.services.campaign_service import CURRENT_USER, ServiceError, _stamp

DEFAULT_RULES = {"maxTouches": 3, "duplicateWindow": 3}
RANK = {"high": 3, "medium": 2, "low": 1}
LABEL = {"linkedin": "LinkedIn", "email": "Email", "sms": "SMS", "voice": "Voice"}
PAIRS = {
    "c1|c3": "US SaaS CTO sends pricing questions to a human rep, while Voice AI Founders offers a demo and quotes self-serve pricing.",
    "c2|c3": "India BFSI CIO writes in a formal tone, while Voice AI Founders writes casually.",
}


def get_rules(db: Session) -> dict:
    row = db.get(GlobalState, "contact_rules")
    return {**DEFAULT_RULES, **(row.value if row else {})}


def set_rules(db: Session, max_touches: int, duplicate_window: int) -> dict:
    value = {"maxTouches": max_touches, "duplicateWindow": duplicate_window}
    row = db.get(GlobalState, "contact_rules")
    if row is None:
        db.add(GlobalState(key="contact_rules", value=value))
    else:
        row.value = value
    db.commit()
    return value


def find_suppression(db: Session, email: str) -> Suppression | None:
    e = (email or "").strip().lower()
    domain = e.split("@")[-1] if "@" in e else ""
    return db.scalar(select(Suppression).where(Suppression.value.in_([e, domain])))


def active_ids(p: Prospect, camps: dict) -> list[str]:
    return [c for c in p.campaign_ids if c in camps and camps[c].status in ("live", "paused")]


def recent_count(p: Prospect, camps: dict) -> int:
    active = active_ids(p, camps)
    return len([t for t in p.touches if t["daysAgo"] <= 7 and t["campaignId"] in active])


def detect(p: Prospect, camps: dict, rules: dict, suppressed: bool) -> list[dict]:
    active = active_ids(p, camps)
    if not active:
        return []

    def name(cid: str) -> str:
        return camps[cid].name if cid in camps else "Unknown campaign"

    issues: list[dict] = []
    if suppressed:
        issues.append({
            "key": "suppressed", "label": "On do-not-contact list", "severity": "high",
            "detail": f"This prospect opted out, but {' and '.join(name(c) for c in active)} can still contact them.",
        })

    touches = [t for t in p.touches if t["campaignId"] in active]
    dupes: set[str] = set()
    for i in range(len(touches)):
        for j in range(i + 1, len(touches)):
            a, b = touches[i], touches[j]
            if (
                a["campaignId"] != b["campaignId"]
                and a["channel"] == b["channel"]
                and abs(a["daysAgo"] - b["daysAgo"]) <= rules["duplicateWindow"]
            ):
                dupes.add(f"{LABEL[a['channel']]} from {name(a['campaignId'])} and {name(b['campaignId'])}")
    if dupes:
        issues.append({
            "key": "duplicate", "label": "Duplicate outreach", "severity": "high",
            "detail": f"Same channel used by two campaigns within {rules['duplicateWindow']} days: {'; '.join(sorted(dupes))}.",
        })

    if len(active) > 1:
        issues.append({
            "key": "overlap", "label": "In multiple campaigns", "severity": "medium",
            "detail": f"Targeted at the same time by {' and '.join(name(c) for c in active)}.",
        })

    recent = recent_count(p, camps)
    if recent > rules["maxTouches"]:
        issues.append({
            "key": "frequency", "label": "Too many touches", "severity": "medium",
            "detail": f"{recent} touches in the last 7 days. The limit is {rules['maxTouches']}.",
        })

    for i in range(len(active)):
        for j in range(i + 1, len(active)):
            msg = PAIRS.get("|".join(sorted([active[i], active[j]])))
            if msg:
                issues.append({
                    "key": "instructions", "label": "Conflicting instructions",
                    "severity": "low", "detail": msg,
                })
    return issues


def recommend(p: Prospect, camps: dict, issues: list[dict]) -> dict:
    if any(i["key"] == "suppressed" for i in issues):
        return {"action": "dnc"}
    active = active_ids(p, camps)
    if len(active) > 1:
        best = max(active, key=lambda cid: len([t for t in p.touches if t["campaignId"] == cid]))
        return {"action": "owner", "ownerId": best}
    return {"action": "cooldown"}


def _prospect(p: Prospect, suppressed: bool) -> dict:
    return {
        "id": p.id, "name": p.name, "title": p.title, "company": p.company, "email": p.email,
        "campaignIds": p.campaign_ids, "touches": p.touches, "suppressed": suppressed,
    }


def _resolution(r: ConflictResolution) -> dict:
    return {
        "action": r.action, "ownerId": r.owner_id, "days": r.days, "note": r.note,
        "by": r.by, "time": r.time, "prevCampaignIds": r.prev_campaign_ids,
    }


def list_conflicts(db: Session) -> dict:
    camps = {c.id: c for c in db.scalars(select(Campaign)).all()}
    rules = get_rules(db)
    resolutions = {r.prospect_id: r for r in db.scalars(select(ConflictResolution)).all()}
    prospects = db.scalars(select(Prospect).order_by(Prospect.id)).all()

    open_items: list[dict] = []
    resolved: list[dict] = []
    for p in prospects:
        supp = find_suppression(db, p.email) is not None
        if p.id in resolutions:
            resolved.append({
                "prospect": _prospect(p, supp),
                "resolution": _resolution(resolutions[p.id]),
                "activeCampaignIds": active_ids(p, camps),
            })
            continue
        issues = detect(p, camps, rules, supp)
        if not issues:
            continue
        open_items.append({
            "prospect": _prospect(p, supp),
            "issues": issues,
            "severity": max((i["severity"] for i in issues), key=RANK.get),
            "activeCampaignIds": active_ids(p, camps),
            "recentTouches": recent_count(p, camps),
            "recommended": recommend(p, camps, issues),
        })

    open_items.sort(key=lambda i: (-RANK[i["severity"]], not i["prospect"]["suppressed"]))
    resolved.sort(key=lambda r: r["resolution"]["time"], reverse=True)
    return {"monitored": len(prospects), "rules": rules, "open": open_items, "resolved": resolved}


def resolve(db: Session, prospect_id: str, action: str, owner_id: str | None, days: int | None, note: str) -> dict:
    p = db.get(Prospect, prospect_id)
    if p is None:
        raise ServiceError("Prospect not found", 404)
    if db.get(ConflictResolution, prospect_id):
        raise ServiceError("This conflict is already resolved", 409)

    camps = {c.id: c for c in db.scalars(select(Campaign)).all()}
    supp = find_suppression(db, p.email)
    if not detect(p, camps, get_rules(db), supp is not None):
        raise ServiceError("This prospect has no open conflict", 409)

    active = active_ids(p, camps)
    if supp is not None and action != "dnc":
        raise ServiceError("A do-not-contact prospect can only be stopped, not overridden", 422)
    if action == "owner":
        if len(active) < 2:
            raise ServiceError("Only prospects in several campaigns can be assigned to one", 422)
        if owner_id not in active:
            raise ServiceError("Pick one of the prospect's active campaigns", 422)
    if action == "cooldown" and days not in (3, 7, 14):
        raise ServiceError("Cool-down must be 3, 7 or 14 days", 422)

    prev = list(p.campaign_ids)
    added_id = None
    if action == "owner":
        p.campaign_ids = [c for c in p.campaign_ids if c == owner_id or c not in active]
    elif action == "dnc":
        if supp is None and p.email:
            from app.services.campaign_service import _id, _today

            row = Suppression(
                id=_id("s"), value=p.email.strip().lower(), type="email",
                reason="Do not contact (conflict resolution)", added_by=CURRENT_USER, added_at=_today(),
            )
            db.add(row)
            added_id = row.id
        p.campaign_ids = [c for c in p.campaign_ids if c not in active]

    db.add(ConflictResolution(
        prospect_id=prospect_id, action=action, owner_id=owner_id if action == "owner" else None,
        days=days if action == "cooldown" else None, note=note.strip(), by=CURRENT_USER,
        time=_stamp(), prev_campaign_ids=prev, added_suppression_id=added_id,
    ))
    db.commit()
    return list_conflicts(db)


def reopen(db: Session, prospect_id: str) -> dict:
    r = db.get(ConflictResolution, prospect_id)
    if r is None:
        raise ServiceError("This conflict is not resolved", 404)
    p = db.get(Prospect, prospect_id)
    if p is not None:
        p.campaign_ids = list(r.prev_campaign_ids)
    if r.added_suppression_id:
        row = db.get(Suppression, r.added_suppression_id)
        if row is not None:
            db.delete(row)
    db.delete(r)
    db.commit()
    return list_conflicts(db)