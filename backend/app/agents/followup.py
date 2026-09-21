import json
import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.base import build_system
from app.agents.personalisation import _flags
from app.agents.schemas import FollowupDraftOut
from app.llm import generate_json, model_for
from app.models.tables import Campaign, CampaignProspect, ProspectMessage, utcnow
from app.rag import retrieve

ROLE = "Follow-up Agent. Write one short follow-up that adds something new. Never repeat the previous message."

GAPS = (3, 5, 7)  # days to wait after touch 1, 2, 3
MAX_TOUCHES = 3
DEFERRABLE = {"out_of_office", "not_now"}
SKIP_STATES = {
    "STOPPED", "COMPLETED", "MEETING_PENDING", "MEETING_BOOKED", "VOICE_PENDING",
    "HUMAN_REVIEW", "FAILED", "CONVERSATION_ACTIVE", "RESPONSE_RECEIVED",
}


def _history(db: Session, pid: str) -> list[ProspectMessage]:
    return list(db.scalars(select(ProspectMessage).where(ProspectMessage.prospect_id == pid).order_by(ProspectMessage.created_at)))


def pick_channel(c: Campaign, p: CampaignProspect, sent_so_far: int) -> str | None:
    """Follows the strategy sequence, and falls back to a channel that can really be used."""
    strat = p.strategy or {}
    seq = strat.get("sequence") or []
    wanted = seq[sent_so_far]["channel"] if sent_so_far < len(seq) else strat.get("primary_channel", "email")
    open_channels = {ch["channel"] for ch in c.channels if ch["enabled"] and not ch["paused"]}
    for ch in (wanted, strat.get("primary_channel"), "email", "linkedin"):
        if ch in open_channels and ch != "voice" and (ch != "email" or p.email):
            return ch
    return None


def decide(db: Session, c: Campaign, p: CampaignProspect, now=None) -> dict:
    """Plain rules decide WHEN to follow up, so nobody pays a model to do date arithmetic."""
    now = now or utcnow()
    if p.state in SKIP_STATES:
        return {"action": "skip", "reason": f"Prospect is {p.state}"}
    msgs = _history(db, p.id)
    sent = [m for m in msgs if m.direction == "out" and m.kind in ("first_touch", "followup") and m.status in ("sent", "sandbox")]
    if not sent:
        return {"action": "skip", "reason": "Nothing has been sent yet"}

    last = sent[-1]
    ref, gap, deferred = last.created_at, None, False
    later_replies = [m for m in msgs if m.direction == "in" and m.created_at > last.created_at]
    if later_replies:
        if (later_replies[-1].meta or {}).get("intent") in DEFERRABLE:
            ref, gap, deferred = later_replies[-1].created_at, 5, True
        else:
            return {"action": "skip", "reason": "Prospect replied, the Conversation agent handles it"}

    touches = len(sent)
    limit = int((c.pipeline_config or {}).get("maxTouches", MAX_TOUCHES)) + (1 if deferred else 0)
    if touches >= limit:
        return {"action": "stop", "reason": f"Sequence finished after {touches} messages with no reply"}

    gap = gap if gap is not None else GAPS[min(touches - 1, len(GAPS) - 1)]
    days = (now - ref).total_seconds() / 86400
    if days < gap:
        return {"action": "wait", "reason": f"Next follow-up is due in {math.ceil(gap - days)} day(s)", "daysUntil": math.ceil(gap - days)}

    channel = pick_channel(c, p, touches)
    if channel is None:
        return {"action": "stop", "reason": "No channel is available for a follow-up"}
    return {"action": "send", "touch": touches + 1, "channel": channel, "last": touches + 1 >= limit}


def draft(db: Session, c: Campaign, p: CampaignProspect, touch: int, channel: str, last: bool) -> tuple[dict, dict]:
    cfg = c.pipeline_config or {}
    msgs = [m for m in _history(db, p.id) if m.kind in ("first_touch", "followup", "inbound")][-4:]
    docs = retrieve(db, c.id, f"{(p.research or {}).get('company_summary', '')} {cfg.get('objective', '')}", k=2)
    payload = {
        "prospect": {"name": p.name, "job_title": p.title, "company": p.company},
        "previous_messages": [{"from": "us" if m.direction == "out" else "prospect", "text": m.body[:600]} for m in msgs],
        "research": {"context": (p.research or {}).get("professional_context")},
        "knowledge": [{"title": d["title"], "content": d["content"]} for d in docs],
        "campaign": {"tone": cfg.get("tone", ""), "cta": cfg.get("cta", "")},
        "touch_number": touch, "channel": channel, "sender_name": c.owner,
    }
    user = (
        f"Write follow-up number {touch} on {channel}. Under 60 words. Add one new angle taken from research or knowledge, "
        "do not repeat the earlier message, no guilt-tripping. Sign off with sender_name. "
        + ("This is the last follow-up, so close politely and say you will not keep writing. " if last else "")
        + 'Return JSON: {"subject": str, "body": str, "requires_human_review": bool}\n\nINPUT:\n' + json.dumps(payload)
    )
    model, tier = model_for(db, "Personalised email writing")
    out, meta = generate_json(model, tier, build_system(db, c.id, "followup", ROLE), user, FollowupDraftOut, temperature=0.5)
    result = out.model_dump()
    result["flags"] = _flags(f"{out.subject} {out.body}", json.dumps(payload["knowledge"]) + json.dumps(payload["previous_messages"]))
    meta.update(source="local")
    return result, meta