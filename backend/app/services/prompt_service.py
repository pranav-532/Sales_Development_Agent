from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tables import AuditEntry, PromptVersion
from app.services.campaign_service import (
    CURRENT_USER,
    ServiceError,
    _id,
    _require_editable,
    _stamp,
    _today,
    get_or_404,
)


def prompt_dict(p: PromptVersion) -> dict:
    return {
        "id": p.id,
        "campaignId": p.campaign_id,
        "agentKey": p.agent_key,
        "version": p.version,
        "content": p.content,
        "author": p.author,
        "createdAt": p.created_at,
        "isActive": p.is_active,
        "note": p.note,
    }


def list_prompts(db: Session, campaign_id: str | None = None) -> list[dict]:
    q = select(PromptVersion)
    if campaign_id:
        q = q.where(PromptVersion.campaign_id == campaign_id)
    rows = db.scalars(q.order_by(PromptVersion.campaign_id, PromptVersion.agent_key, PromptVersion.version)).all()
    return [prompt_dict(p) for p in rows]


def list_audit(db: Session, campaign_id: str | None = None) -> list[dict]:
    q = select(AuditEntry)
    if campaign_id:
        q = q.where(AuditEntry.campaign_id == campaign_id)
    rows = db.scalars(q.order_by(AuditEntry.time.desc(), AuditEntry.id.desc())).all()
    return [a.to_dict() for a in rows]


def _scope_rows(db: Session, campaign_id: str, scope: str) -> list[PromptVersion]:
    return list(
        db.scalars(
            select(PromptVersion)
            .where(PromptVersion.campaign_id == campaign_id, PromptVersion.agent_key == scope)
            .order_by(PromptVersion.version)
        ).all()
    )


def _check_scope(campaign, scope: str) -> None:
    valid = {"system"} | {a["key"] for a in campaign.agents}
    if scope not in valid:
        raise ServiceError(f"Unknown prompt scope: {scope}", 422)


def save_version(db: Session, campaign_id: str, scope: str, content: str, note: str) -> dict:
    c = get_or_404(db, campaign_id)
    _require_editable(c)
    _check_scope(c, scope)

    text = content.strip()
    if not text:
        raise ServiceError("A prompt cannot be empty", 422)

    rows = _scope_rows(db, campaign_id, scope)
    if rows and rows[-1].content.strip() == text:
        raise ServiceError("This is identical to the latest version", 409)

    version = (rows[-1].version if rows else 0) + 1
    first = not rows
    stamp = _stamp()

    p = PromptVersion(
        id=_id("p"), campaign_id=campaign_id, agent_key=scope, version=version, content=text,
        author=CURRENT_USER, created_at=stamp, is_active=first, note=note.strip(),
    )
    db.add(p)
    db.add(
        AuditEntry(
            id=_id("a"), campaign_id=campaign_id, scope=scope, action="created", version=version,
            author=CURRENT_USER, time=stamp, note=note.strip(),
        )
    )
    if first and scope == "system":
        c.active_prompt_version = version
        c.updated_at = _today()
    db.commit()
    return prompt_dict(p)


def activate_version(db: Session, campaign_id: str, scope: str, version: int) -> dict:
    c = get_or_404(db, campaign_id)
    _require_editable(c)
    _check_scope(c, scope)

    rows = _scope_rows(db, campaign_id, scope)
    target = next((r for r in rows if r.version == version), None)
    if target is None:
        raise ServiceError("That version does not exist", 404)

    current = next((r for r in rows if r.is_active), None)
    if current is not None and current.version == version:
        return prompt_dict(target)

    action = "rolled_back" if current is not None and version < current.version else "activated"
    for r in rows:
        r.is_active = r.version == version
    if scope == "system":
        c.active_prompt_version = version
        c.updated_at = _today()

    db.add(
        AuditEntry(
            id=_id("a"), campaign_id=campaign_id, scope=scope, action=action, version=version,
            author=CURRENT_USER, time=_stamp(), note="",
        )
    )
    db.commit()
    return prompt_dict(target)