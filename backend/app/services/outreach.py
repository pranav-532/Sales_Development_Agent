"""Sending. Agents write messages, this module delivers them, and only after the guard allows it."""
import os
import smtplib
import ssl
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tables import ActivityEvent, Campaign, CampaignProspect, ProspectMessage, utcnow
from app.services import pipeline
from app.services.campaign_service import ServiceError, _id
from app.services.guard import can_act
from app.services.lifecycle import advance

SENDABLE = ("email", "linkedin", "sms")
LABEL = {"first_touch": "First message", "followup": "Follow-up", "reply": "Reply"}
AGENT = {"first_touch": "personalisation", "followup": "followup", "reply": "conversation"}
# When these come back, sending more to other prospects will fail for the same reason, so stop the batch.
HALT = {"kill_switch", "not_found", "daily_limit", "platform_cap", "agent_paused", "agent_disabled",
        "campaign_draft", "campaign_paused", "campaign_completed", "campaign_archived"}


def channel_mode(channel: str) -> str:
    return os.getenv(f"CHANNEL_MODE_{channel.upper()}", "sandbox").strip().lower()


def recipient_allowed(addr: str) -> bool:
    """Real mail may only go to inboxes you listed in DEMO_INBOXES (plus-tags allowed)."""
    if os.getenv("ALLOW_ANY_RECIPIENT", "0") == "1":
        return True
    inboxes = {i.strip().lower() for i in os.getenv("DEMO_INBOXES", "").split(",") if "@" in i}
    local, _, domain = addr.strip().lower().partition("@")
    return f"{local.split('+')[0]}@{domain}" in inboxes


def smtp_send(to: str, subject: str, body: str) -> tuple[str, str]:
    host, user, password = os.getenv("SMTP_HOST", ""), os.getenv("SMTP_USER", ""), os.getenv("SMTP_PASS", "")
    if not (host and user and password):
        return "unavailable", "SMTP is not configured (SMTP_HOST, SMTP_USER, SMTP_PASS)"
    port = int(os.getenv("SMTP_PORT", "587"))
    msg = EmailMessage()
    msg["Subject"] = subject or "(no subject)"
    msg["From"] = os.getenv("SMTP_FROM", "") or user
    msg["To"] = to
    msg.set_content(body)
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=20, context=ssl.create_default_context()) as s:
                s.login(user, password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=20) as s:
                s.starttls(context=ssl.create_default_context())
                s.login(user, password)
                s.send_message(msg)
        return "sent", ""
    except Exception as e:  # never let a mail server problem crash a worker
        return "failed", f"{type(e).__name__}"


def deliver(db: Session, c: Campaign, p: CampaignProspect, *, channel: str, subject: str, body: str,
            kind: str, existing: ProspectMessage | None = None) -> dict:
    agent = AGENT[kind]
    d = can_act(db, c.id, agent, channel, p.email or None)
    if not d.allowed:
        if d.code == "suppressed":
            advance(p, "STOPPED")
            p.error = d.reason
            pipeline.log_event(db, c, p, agent, f"Blocked send to {p.name}: {d.reason}", "failed", {}, channel=channel)
        return {"sent": False, "code": d.code, "reason": d.reason}

    status, note = "sandbox", ""
    if channel == "email":
        if not p.email:
            status, note = "unavailable", "This prospect has no email address"
        elif channel_mode("email") == "live":
            if recipient_allowed(p.email):
                status, note = smtp_send(p.email, subject, body)
            else:
                status, note = "blocked", "Recipient is not in DEMO_INBOXES"
    elif channel_mode(channel) == "live":
        status, note = "unavailable", f"No live provider is connected for {channel}"
    ok = status in ("sent", "sandbox")

    row = existing or ProspectMessage(
        id=_id("pm"), campaign_id=c.id, prospect_id=p.id, direction="out", channel=channel, kind=kind,
        subject=subject or "", body=body,
    )
    row.status = status
    row.created_at = utcnow()
    row.meta = {**(row.meta or {}), "note": note, "mode": "live" if status == "sent" else "sandbox"}
    if existing is None:
        db.add(row)

    what = "sent" if status == "sent" else ("recorded in sandbox" if status == "sandbox" else f"not sent ({status})")
    db.add(ActivityEvent(
        id=_id("e"), campaign_id=c.id, prospect_id=p.id, agent_key=agent, channel=channel, kind="send",
        action=f"{LABEL[kind]} to {p.name} via {channel}: {what}" + (f". {note}" if note else ""),
        status="completed" if ok else "failed", prompt_version=c.active_prompt_version, source="local",
        mode="live" if status == "sent" else "sandbox",
    ))
    if ok and kind in ("first_touch", "followup") and p.state in ("READY_TO_SEND", "FOLLOWUP_DUE"):
        advance(p, "OUTREACH_SENT")
        advance(p, "WAITING_FOR_RESPONSE")
    return {"sent": ok, "code": "ok" if ok else status, "reason": note, "status": status, "channel": channel, "messageId": row.id}


def _channel_for(p: CampaignProspect, wanted: str) -> str | None:
    if wanted in SENDABLE:
        return wanted
    return "email" if p.email else None  # voice is a call, not a message


def send_first_touch(db: Session, c: Campaign, p: CampaignProspect) -> dict:
    if p.state != "READY_TO_SEND":
        raise ServiceError(f"This prospect is {p.state}, not ready to send", 409)
    m = p.message or {}
    channel = _channel_for(p, m.get("channel") or (p.strategy or {}).get("primary_channel") or "email")
    if channel is None:
        raise ServiceError("No usable channel for this prospect", 422)
    result = deliver(db, c, p, channel=channel, subject=m.get("subject", ""), body=m.get("body", ""), kind="first_touch")
    db.flush()  # autoflush is off, so write the new state before counting
    pipeline.recompute_funnel(db, c)
    db.commit()
    return result


def send_existing(db: Session, c: Campaign, p: CampaignProspect, m: ProspectMessage) -> dict:
    """Sends a stored draft, for example a reply or follow-up that a manager just approved."""
    result = deliver(db, c, p, channel=m.channel, subject=m.subject, body=m.body, kind=m.kind, existing=m)
    db.flush()  # autoflush is off, so write the new state before counting
    pipeline.recompute_funnel(db, c)
    return result


def send_ready(db: Session, c: Campaign, limit: int = 50) -> dict:
    rows = db.scalars(
        select(CampaignProspect)
        .where(CampaignProspect.campaign_id == c.id, CampaignProspect.state == "READY_TO_SEND")
        .order_by(CampaignProspect.created_at).limit(max(1, min(limit, 200)))
    ).all()
    sent = not_sent = 0
    halted = ""
    for p in rows:
        r = send_first_touch(db, c, p)
        if r["sent"]:
            sent += 1
            continue
        not_sent += 1
        if r["code"] in HALT:
            halted = r["reason"]
            break
    return {"sent": sent, "notSent": not_sent, "stoppedBecause": halted}