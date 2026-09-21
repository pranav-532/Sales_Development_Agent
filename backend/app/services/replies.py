"""Replies, follow-ups and meetings. Runs inside the same job queue as the rest of the pipeline."""
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents import conversation, followup
from app.models.tables import (
    ActivityEvent, AgentJob, Campaign, CampaignProspect, ProspectMessage, Suppression, utcnow,
)
from app.services import outreach, pipeline
from app.services.campaign_service import ServiceError, _id, _today, get_or_404
from app.services.lifecycle import advance, try_advance

PROC = uuid.uuid4().hex  # tells this process's claims apart from ones left behind by a crash


def get_prospect(db: Session, prospect_id: str) -> CampaignProspect:
    p = db.get(CampaignProspect, prospect_id)
    if p is None:
        raise ServiceError("Prospect not found", 404)
    return p


def messages(db: Session, prospect_id: str) -> list[dict]:
    rows = db.scalars(select(ProspectMessage).where(ProspectMessage.prospect_id == prospect_id).order_by(ProspectMessage.created_at)).all()
    return [m.to_dict() for m in rows]


def enqueue_repeatable(db: Session, campaign_id: str, prospect_id: str, agent: str) -> None:
    """Unlike pipeline.enqueue, this can be queued again after an earlier job finished."""
    if db.scalar(select(AgentJob.id).where(AgentJob.prospect_id == prospect_id, AgentJob.agent == agent, AgentJob.status == "queued").limit(1)):
        return
    db.add(AgentJob(
        id=_id("j"), campaign_id=campaign_id, prospect_id=prospect_id, agent=agent, status="queued",
        attempts=0, max_attempts=pipeline.MAX_ATTEMPTS, run_after=utcnow(),
    ))


# ---------- inbound replies ----------
def receive_reply(db: Session, prospect_id: str, channel: str, text: str) -> dict:
    p = get_prospect(db, prospect_id)
    c = get_or_404(db, p.campaign_id)
    text = text.strip()
    if not text:
        raise ServiceError("The reply is empty", 422)
    if not db.scalar(select(ProspectMessage.id).where(
        ProspectMessage.prospect_id == p.id, ProspectMessage.direction == "out", ProspectMessage.status.in_(("sent", "sandbox"))
    ).limit(1)):
        raise ServiceError("Nothing has been sent to this prospect yet, so there is nothing to reply to", 409)

    m = ProspectMessage(id=_id("pm"), campaign_id=c.id, prospect_id=p.id, direction="in", channel=channel,
                        kind="inbound", body=text, status="received", meta={})
    db.add(m)
    if p.state == "STOPPED":
        m.status = "ignored"  # they opted out or were stopped, we keep the record but do nothing
    else:
        try_advance(p, "RESPONSE_RECEIVED")
        enqueue_repeatable(db, c.id, p.id, "conversation")
    db.flush()  # autoflush is off, so write the new state before counting
    pipeline.recompute_funnel(db, c)
    db.commit()
    return {"accepted": m.status == "received", "messageId": m.id, "state": p.state}


def _claim(db: Session, prospect_id: str) -> ProspectMessage | None:
    rows = db.scalars(
        select(ProspectMessage).where(
            ProspectMessage.prospect_id == prospect_id, ProspectMessage.direction == "in",
            ProspectMessage.status.in_(("received", "processing")),
        ).order_by(ProspectMessage.created_at).with_for_update(skip_locked=True)
    ).all()
    for m in rows:
        if m.status == "received" or (m.meta or {}).get("claim") != PROC:
            m.status = "processing"
            m.meta = {**(m.meta or {}), "claim": PROC}
            db.commit()
            return m
    return None


def _history(db: Session, prospect_id: str, exclude: str, limit: int = 8) -> list[dict]:
    rows = db.scalars(select(ProspectMessage).where(
        ProspectMessage.prospect_id == prospect_id, ProspectMessage.id != exclude,
        ProspectMessage.kind.in_(("first_touch", "followup", "reply", "inbound")), ProspectMessage.status != "draft",
    ).order_by(ProspectMessage.created_at.desc()).limit(limit)).all()
    return [{"from": "us" if m.direction == "out" else "prospect", "channel": m.channel, "text": m.body[:700]} for m in reversed(rows)]


def _suppress(db: Session, p: CampaignProspect, reason: str) -> None:
    v = (p.email or "").strip().lower()
    if v and not db.scalar(select(Suppression.id).where(Suppression.value == v)):
        db.add(Suppression(id=_id("s"), value=v, type="email", reason=reason, added_by="Conversation Agent", added_at=_today()))


def _event(db, c, p, agent, action, status, meta, channel=None, ref=None) -> ActivityEvent:
    ev = pipeline.log_event(db, c, p, agent, action, status, meta, channel=channel)
    if ref:
        ev.ref_id = ref
    return ev


def _route(db: Session, c: Campaign, p: CampaignProspect, m: ProspectMessage, r: dict, meta: dict) -> None:
    """The agent only reports what the reply means. What happens next is decided here, by rules."""
    intent, topics, esc = r["intent"], set(r["topics"]), set(c.escalate_on or [])
    who, ch = p.name, m.channel

    if intent == "unsubscribe":
        _suppress(db, p, "Opted out by reply")
        advance(p, "STOPPED")
        _event(db, c, p, "conversation", f"{who} asked to stop. Added to the do-not-contact list", "completed", meta, ch)
        return
    if intent == "not_interested":
        advance(p, "STOPPED")
        _event(db, c, p, "conversation", f"{who} is not interested, sequence stopped. {r['summary']}", "completed", meta, ch)
        return

    advance(p, "CONVERSATION_ACTIVE")
    reasons = []
    if "pricing" in esc and topics & {"pricing", "contract"}:
        reasons.append("asked about pricing or a contract")
    if "human_request" in esc and "human_request" in topics:
        reasons.append("asked for a person")
    if "objection" in esc and (intent == "objection" or topics & {"security", "legal", "compliance"}):
        reasons.append("raised an objection or a security, legal or compliance question")
    if r["requires_human_review"] or intent == "unclear":
        reasons.append("the agent was not sure")
    if reasons:
        advance(p, "HUMAN_REVIEW")
        _event(db, c, p, "conversation", f"{who} {' and '.join(reasons)}, handed to a human rep. {r['summary']}", "escalated", meta, ch)
        return

    if intent in ("out_of_office", "not_now"):
        advance(p, "FOLLOWUP_DUE")
        _event(db, c, p, "conversation", f"{who} asked to hear back later, follow-up scheduled. {r['summary']}", "completed", meta, ch)
        return
    if intent == "wants_call":
        if any(x["channel"] == "voice" and x["enabled"] for x in c.channels):
            advance(p, "VOICE_PENDING")
            _event(db, c, p, "conversation", f"{who} asked for a call, voice call ready", "completed", meta, ch)
        else:
            advance(p, "HUMAN_REVIEW")
            _event(db, c, p, "conversation", f"{who} asked for a call but voice is off for this campaign, handed to a rep", "escalated", meta, ch)
        return

    draft = None
    if r["response_required"] and r["reply_draft"].strip():
        last_subject = db.scalar(select(ProspectMessage.subject).where(
            ProspectMessage.prospect_id == p.id, ProspectMessage.direction == "out", ProspectMessage.subject != ""
        ).order_by(ProspectMessage.created_at.desc()).limit(1)) or ""
        draft = ProspectMessage(
            id=_id("pm"), campaign_id=c.id, prospect_id=p.id, direction="out", channel=ch, kind="reply",
            subject=last_subject if last_subject.lower().startswith("re:") else (f"Re: {last_subject}" if last_subject else ""),
            body=r["reply_draft"].strip(), status="draft", meta={"in_reply_to": m.id, "flags": r["flags"]},
        )
        db.add(draft)
    if intent in ("interested", "wants_meeting"):
        advance(p, "MEETING_PENDING")
    _event(
        db, c, p, "conversation",
        f"{who} replied ({intent.replace('_', ' ')}). {r['summary']}" + (" Reply drafted, waiting for approval" if draft else ""),
        "pending_approval" if draft else "completed", meta, ch, ref=f"msg:{draft.id}" if draft else None,
    )


def h_conversation(db: Session, c: Campaign, p: CampaignProspect) -> None:
    m = _claim(db, p.id)
    if m is None:
        return
    try:
        result, meta = conversation.run(db, c, p, _history(db, p.id, exclude=m.id), m.body)
        _route(db, c, p, m, result, meta)
        m.status = "processed"
        m.meta = {**(m.meta or {}), "intent": result["intent"], "sentiment": result["sentiment"],
                  "summary": result["summary"], "topics": result["topics"]}
    except Exception:
        db.rollback()
        row = db.get(ProspectMessage, m.id)
        row.status = "received"  # put it back so a retry can pick it up
        db.commit()
        raise
    if db.scalar(select(ProspectMessage.id).where(ProspectMessage.prospect_id == p.id, ProspectMessage.status == "received").limit(1)):
        enqueue_repeatable(db, c.id, p.id, "conversation")


# ---------- follow-ups ----------
def _finish_sequence(db: Session, c: Campaign, p: CampaignProspect, reason: str) -> None:
    advance(p, "COMPLETED")
    _event(db, c, p, "followup", f"{p.name}: {reason}", "completed", {})


def h_followup(db: Session, c: Campaign, p: CampaignProspect) -> None:
    d = followup.decide(db, c, p)
    if d["action"] == "stop":
        _finish_sequence(db, c, p, d["reason"])
        return
    if d["action"] != "send":
        return
    result, meta = followup.draft(db, c, p, d["touch"], d["channel"], d["last"])
    needs_review = c.approval_mode == "all" or result["requires_human_review"] or bool(result["flags"])
    label = f"Follow-up {d['touch']} for {p.name}"
    if needs_review:
        row = ProspectMessage(id=_id("pm"), campaign_id=c.id, prospect_id=p.id, direction="out", channel=d["channel"],
                              kind="followup", subject=result["subject"], body=result["body"], status="draft",
                              meta={"flags": result["flags"]})
        db.add(row)
        _event(db, c, p, "followup", f"{label} drafted, waiting for approval", "pending_approval", meta, d["channel"], ref=f"msg:{row.id}")
        return
    _event(db, c, p, "followup", f"{label} drafted", "completed", meta, d["channel"])
    outreach.deliver(db, c, p, channel=d["channel"], subject=result["subject"], body=result["body"], kind="followup")


def run_followups(db: Session, c: Campaign) -> dict:
    rows = db.scalars(select(CampaignProspect).where(
        CampaignProspect.campaign_id == c.id, CampaignProspect.state.in_(("WAITING_FOR_RESPONSE", "FOLLOWUP_DUE"))
    )).all()
    counts = {"send": 0, "wait": 0, "stop": 0, "skip": 0}
    for p in rows:
        d = followup.decide(db, c, p)
        counts[d["action"]] += 1
        if d["action"] == "send":
            enqueue_repeatable(db, c.id, p.id, "followup")
        elif d["action"] == "stop":
            _finish_sequence(db, c, p, d["reason"])
    db.flush()  # autoflush is off, so write the new state before counting
    pipeline.recompute_funnel(db, c)
    db.commit()
    return counts


def simulate_days(db: Session, c: Campaign, days: int) -> dict:
    """Demo helper: moves every message back in time so follow-up rules see the days as passed."""
    rows = db.scalars(select(ProspectMessage).where(ProspectMessage.campaign_id == c.id)).all()
    for m in rows:
        m.created_at = m.created_at - timedelta(days=days)
    db.commit()
    return {"shifted": len(rows), "days": days}


# ---------- meetings ----------
def book_meeting(db: Session, prospect_id: str) -> dict:
    p = get_prospect(db, prospect_id)
    c = get_or_404(db, p.campaign_id)
    if p.state != "MEETING_PENDING":
        raise ServiceError(f"A meeting can only be booked once the prospect wants one, this prospect is {p.state}", 409)
    advance(p, "MEETING_BOOKED")
    _event(db, c, p, "conversation", f"Meeting booked with {p.name}", "completed", {}, ref=None)
    db.flush()  # autoflush is off, so write the new state before counting
    pipeline.recompute_funnel(db, c)
    db.commit()
    return {"state": p.state}


# ---------- wiring ----------
_original_review = pipeline.on_review_decision


def _on_review(db: Session, ev: ActivityEvent, decision: str) -> None:
    """Approve or reject buttons on the dashboard also handle message drafts."""
    if ev.ref_id and ev.ref_id.startswith("msg:"):
        m = db.get(ProspectMessage, ev.ref_id[4:])
        if m is None or m.status != "draft":
            return
        if decision == "approved":
            p = db.get(CampaignProspect, m.prospect_id)
            c = db.get(Campaign, m.campaign_id)
            outreach.send_existing(db, c, p, m)
        else:
            m.status = "rejected"
        return
    _original_review(db, ev, decision)


def register() -> None:
    pipeline.HANDLERS["conversation"] = h_conversation
    pipeline.HANDLERS["followup"] = h_followup
    pipeline.RETRY_TARGET["conversation"] = "RESPONSE_RECEIVED"
    pipeline.RETRY_TARGET["followup"] = "FOLLOWUP_DUE"
    pipeline.TRANSITIONS.setdefault("FAILED", set()).update(pipeline.RETRY_TARGET.values())
    pipeline.on_review_decision = _on_review