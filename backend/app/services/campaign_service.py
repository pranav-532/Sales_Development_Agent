import secrets
import time
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tables import Campaign, PromptVersion
from app.schemas.campaign import CampaignCreate, CampaignUpdate
from app.services.guard import get_kill_switch

CURRENT_USER = "Aarav Mehta"  # replaced when real auth is added

MOVES = {
    "draft": {"live", "archived"},
    "live": {"paused", "completed", "archived"},
    "paused": {"live", "completed", "archived"},
    "completed": {"archived"},
    "archived": {"completed"},
}

EMPTY_FUNNEL = {
    "discovered": 0, "researched": 0, "qualified": 0,
    "contacted": 0, "engaged": 0, "meeting": 0, "opportunity": 0,
}


class ServiceError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def _id(prefix: str) -> str:
    return f"{prefix}{int(time.time() * 1000)}{secrets.token_hex(2)}"


def _today() -> str:
    return date.today().isoformat()


def _stamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M")


def get_or_404(db: Session, campaign_id: str) -> Campaign:
    c = db.get(Campaign, campaign_id)
    if c is None:
        raise ServiceError("Campaign not found", 404)
    return c


def _name_taken(db: Session, name: str, exclude_id: str | None = None) -> bool:
    rows = db.scalars(select(Campaign)).all()
    return any(r.id != exclude_id and r.name.strip().lower() == name.strip().lower() for r in rows)


def _require_editable(c: Campaign) -> None:
    if c.status in ("completed", "archived"):
        raise ServiceError(f"Campaign is {c.status}, so it is read-only", 409)


def create_campaign(db: Session, body: CampaignCreate) -> Campaign:
    if _name_taken(db, body.name):
        raise ServiceError("Another campaign already uses this name", 409)

    text = body.system_prompt.strip()
    go_live = body.go_live and not get_kill_switch(db)
    cid = _id("c")

    c = Campaign(
        id=cid,
        name=body.name.strip(),
        description=body.description.strip(),
        owner=body.owner,
        status="live" if go_live else "draft",
        icp=body.icp.strip(),
        geography=body.geography.strip(),
        target_roles=body.target_roles,
        company_criteria=body.company_criteria.strip(),
        exclusions=body.exclusions.strip(),
        reference_profiles=body.reference_profiles.strip(),
        approval_mode=body.approval_mode,
        qualify_threshold=body.qualify_threshold,
        confidence_threshold=body.confidence_threshold,
        escalate_on=body.escalate_on,
        agents=[a.model_dump(by_alias=True) for a in body.agents],
        channels=[ch.model_dump(by_alias=True) for ch in body.channels],
        rep_ids=body.rep_ids,
        funnel=dict(EMPTY_FUNNEL),
        outreach_count=0,
        meetings=0,
        active_prompt_version=1 if text else 0,
        created_at=_today(),
        updated_at=_today(),
    )
    db.add(c)
    if text:
        db.add(
            PromptVersion(
                id=_id("p"), campaign_id=cid, agent_key="system", version=1, content=text,
                author=CURRENT_USER, created_at=_stamp(), is_active=True, note="Initial version",
            )
        )
    db.commit()
    return c


def update_campaign(db: Session, campaign_id: str, body: CampaignUpdate) -> Campaign:
    c = get_or_404(db, campaign_id)
    _require_editable(c)

    fields = body.model_dump(exclude_unset=True)
    if "name" in fields and fields["name"] is not None:
        if _name_taken(db, fields["name"], exclude_id=c.id):
            raise ServiceError("Another campaign already uses this name", 409)
        c.name = fields["name"].strip()

    for key in (
        "description", "owner", "icp", "geography", "target_roles", "company_criteria",
        "exclusions", "reference_profiles", "approval_mode", "qualify_threshold",
        "confidence_threshold", "escalate_on", "rep_ids",
    ):
        if key in fields and fields[key] is not None:
            setattr(c, key, fields[key])

    if body.agents is not None:
        c.agents = [a.model_dump(by_alias=True) for a in body.agents]
    if body.channels is not None:
        c.channels = [ch.model_dump(by_alias=True) for ch in body.channels]

    c.updated_at = _today()
    db.commit()
    return c


def set_status(db: Session, campaign_id: str, status: str) -> Campaign:
    c = get_or_404(db, campaign_id)
    if status == c.status:
        return c
    if status not in MOVES[c.status]:
        raise ServiceError(f"A {c.status} campaign cannot become {status}", 409)
    if status == "live" and get_kill_switch(db):
        raise ServiceError("Release the global kill switch before going live", 423)
    c.status = status
    c.updated_at = _today()
    db.commit()
    return c


def duplicate_campaign(db: Session, campaign_id: str) -> Campaign:
    src = get_or_404(db, campaign_id)
    new_id = _id("c")

    name = f"{src.name} (copy)"
    n = 2
    while _name_taken(db, name):
        name = f"{src.name} (copy {n})"
        n += 1

    active = db.scalars(
        select(PromptVersion).where(
            PromptVersion.campaign_id == src.id, PromptVersion.is_active.is_(True)
        )
    ).all()
    has_system = any(p.agent_key == "system" for p in active)

    copy = Campaign(
        id=new_id, name=name, description=src.description, owner=src.owner, status="draft",
        icp=src.icp, geography=src.geography, target_roles=list(src.target_roles),
        company_criteria=src.company_criteria, exclusions=src.exclusions,
        reference_profiles=src.reference_profiles, approval_mode=src.approval_mode,
        qualify_threshold=src.qualify_threshold, confidence_threshold=src.confidence_threshold,
        escalate_on=list(src.escalate_on),
        agents=[dict(a) for a in src.agents], channels=[dict(ch) for ch in src.channels],
        rep_ids=list(src.rep_ids), funnel=dict(EMPTY_FUNNEL), outreach_count=0, meetings=0,
        active_prompt_version=1 if has_system else 0,
        created_at=_today(), updated_at=_today(),
    )
    db.add(copy)
    for p in active:
        db.add(
            PromptVersion(
                id=_id("p"), campaign_id=new_id, agent_key=p.agent_key, version=1, content=p.content,
                author=CURRENT_USER, created_at=_stamp(), is_active=True,
                note=f"Copied from {src.name} v{p.version}",
            )
        )
    db.commit()
    return copy


def toggle_agent(db: Session, campaign_id: str, agent_key: str) -> Campaign:
    c = get_or_404(db, campaign_id)
    _require_editable(c)
    agents = [dict(a) for a in c.agents]
    hit = next((a for a in agents if a["key"] == agent_key), None)
    if hit is None or not hit["enabled"]:
        raise ServiceError("Agent is not enabled for this campaign", 404)
    hit["paused"] = not hit["paused"]
    c.agents = agents
    c.updated_at = _today()
    db.commit()
    return c


def toggle_channel(db: Session, campaign_id: str, channel: str) -> Campaign:
    c = get_or_404(db, campaign_id)
    _require_editable(c)
    channels = [dict(ch) for ch in c.channels]
    hit = next((ch for ch in channels if ch["channel"] == channel), None)
    if hit is None or not hit["enabled"]:
        raise ServiceError("Channel is not enabled for this campaign", 404)
    hit["paused"] = not hit["paused"]
    c.channels = channels
    c.updated_at = _today()
    db.commit()
    return c