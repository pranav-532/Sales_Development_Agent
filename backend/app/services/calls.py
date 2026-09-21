"""Web voice calls. The browser does speech-to-text and text-to-speech, this service does the thinking."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents import voice
from app.models.tables import Campaign, CampaignProspect, ProspectMessage
from app.services import pipeline
from app.services.campaign_service import ServiceError, _id, get_or_404
from app.services.guard import can_act
from app.services.lifecycle import advance, can_advance
from app.services.replies import get_prospect

END_STATE = {
    "meeting_agreed": "MEETING_PENDING",
    "callback_requested": "FOLLOWUP_DUE",
    "not_interested": "STOPPED",
    "needs_human": "HUMAN_REVIEW",
    "continuing": "CONVERSATION_ACTIVE",
}


def _guard(db: Session, c: Campaign, p: CampaignProspect) -> None:
    d = can_act(db, c.id, "voice", "voice", p.email or None)
    if not d.allowed:
        raise ServiceError(d.reason, 423)  # a pause or the kill switch also ends a call in progress


def _active(db: Session, prospect_id: str) -> ProspectMessage:
    row = db.scalar(select(ProspectMessage).where(
        ProspectMessage.prospect_id == prospect_id, ProspectMessage.kind == "call", ProspectMessage.status == "in_progress"
    ).order_by(ProspectMessage.created_at.desc()).limit(1))
    if row is None:
        raise ServiceError("There is no call in progress for this prospect", 409)
    return row


def _add_cost(meta: dict, m: dict) -> dict:
    return {**meta, "tokens_in": meta.get("tokens_in", 0) + m.get("tokens_in", 0),
            "tokens_out": meta.get("tokens_out", 0) + m.get("tokens_out", 0),
            "cost_usd": meta.get("cost_usd", 0.0) + m.get("cost_usd", 0.0)}


def start(db: Session, prospect_id: str) -> dict:
    p = get_prospect(db, prospect_id)
    c = get_or_404(db, p.campaign_id)
    if p.state != "VOICE_PENDING" and not can_advance(p, "VOICE_PENDING"):
        raise ServiceError(f"A call cannot start while the prospect is {p.state}", 409)
    _guard(db, c, p)
    last_reply = db.scalar(select(ProspectMessage).where(
        ProspectMessage.prospect_id == p.id, ProspectMessage.direction == "in"
    ).order_by(ProspectMessage.created_at.desc()).limit(1))
    reason = f"They wrote: {last_reply.body[:300]}" if last_reply else "A manager asked for a call"

    out, meta = voice.decide(db, c, p, reason)
    if not out["should_call"] or not out["opening_script"].strip():
        raise ServiceError("The voice agent decided a call is not appropriate right now: " + (out["reasoning"] or "no reason given"), 409)
    advance(p, "VOICE_PENDING")
    row = ProspectMessage(
        id=_id("pm"), campaign_id=c.id, prospect_id=p.id, direction="out", channel="voice", kind="call",
        subject="Web voice call", body="", status="in_progress",
        meta=_add_cost({"turns": [{"role": "agent", "text": out["opening_script"]}]}, meta),
    )
    db.add(row)
    pipeline.log_event(db, c, p, "voice", f"Call started with {p.name}", "completed", meta, channel="voice")
    db.commit()
    return {"callId": row.id, "opening": out["opening_script"], "talkingPoints": out["talking_points"]}


def turn(db: Session, prospect_id: str, said: str) -> dict:
    p = get_prospect(db, prospect_id)
    c = get_or_404(db, p.campaign_id)
    row = _active(db, p.id)
    _guard(db, c, p)
    turns = list(row.meta["turns"]) + [{"role": "prospect", "text": said.strip()}]
    out, meta = voice.turn(db, c, p, turns, said)
    turns.append({"role": "agent", "text": out["say"]})
    row.meta = _add_cost({**row.meta, "turns": turns, "flag_human": row.meta.get("flag_human") or out["transfer_to_human"]}, meta)
    db.commit()
    return {"say": out["say"], "endCall": out["end_call"] or out["transfer_to_human"],
            "transferToHuman": out["transfer_to_human"], "outcome": out["outcome"]}


def end(db: Session, prospect_id: str) -> dict:
    p = get_prospect(db, prospect_id)
    c = get_or_404(db, p.campaign_id)
    row = _active(db, p.id)
    turns = list(row.meta["turns"])
    spoke = any(t["role"] == "prospect" for t in turns)

    meta = row.meta
    if spoke:
        out, m = voice.summarise(db, c, p, turns)
        meta = _add_cost(meta, m)
    else:
        out = {"outcome": "continuing", "summary": "The call ended before the prospect spoke.", "next_step": "Try again later", "requires_human_review": False}
    outcome = "needs_human" if (meta.get("flag_human") or out["requires_human_review"]) else out["outcome"]

    row.status = "completed"
    row.body = "\n".join(f"{'Agent' if t['role'] == 'agent' else 'Prospect'}: {t['text']}" for t in turns)
    row.meta = {**meta, "outcome": outcome, "summary": out["summary"], "next_step": out["next_step"]}
    advance(p, END_STATE[outcome])
    pipeline.log_event(
        db, c, p, "voice", f"Call with {p.name} ended ({outcome.replace('_', ' ')}). {out['summary']}",
        "escalated" if outcome == "needs_human" else "completed", meta, channel="voice",
    )
    db.flush()  # autoflush is off, so write the new state before counting
    pipeline.recompute_funnel(db, c)
    db.commit()
    return {"outcome": outcome, "summary": out["summary"], "nextStep": out["next_step"], "state": p.state}