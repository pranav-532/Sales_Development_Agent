from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.tables import ActivityEvent, Campaign, GlobalState, Suppression, utcnow


@dataclass
class Decision:
    allowed: bool
    code: str
    reason: str

    def to_dict(self) -> dict:
        return {"allowed": self.allowed, "code": self.code, "reason": self.reason}


def get_kill_switch(db: Session) -> bool:
    row = db.get(GlobalState, "kill_switch")
    return bool(row and row.value.get("on"))


def set_kill_switch(db: Session, on: bool) -> bool:
    row = db.get(GlobalState, "kill_switch")
    if row is None:
        row = GlobalState(key="kill_switch", value={"on": on})
        db.add(row)
    else:
        row.value = {"on": on}
    db.commit()
    return on


def _deny(code: str, reason: str) -> Decision:
    return Decision(False, code, reason)


def _platform_cap(db: Session) -> int:
    row = db.get(GlobalState, "settings")
    return int(row.value.get("policies", {}).get("dailyCap", 0)) if row else 0


def can_act(
    db: Session,
    campaign_id: str,
    agent_key: str,
    channel: str | None = None,
    prospect_email: str | None = None,
) -> Decision:
    """The single gate every agent action passes through.

    Checks, in order: global kill switch, campaign state, agent pause,
    channel pause, channel daily limit, platform daily cap, then the
    global do-not-contact list. Only the requested campaign is affected,
    so pausing one campaign never blocks another.
    """
    if get_kill_switch(db):
        return _deny("kill_switch", "The global kill switch is on")

    c = db.get(Campaign, campaign_id)
    if c is None:
        return _deny("not_found", "Campaign does not exist")
    if c.status != "live":
        return _deny(f"campaign_{c.status}", f"Campaign is {c.status}, not live")

    agent = next((a for a in c.agents if a["key"] == agent_key), None)
    if agent is None or not agent["enabled"]:
        return _deny("agent_disabled", "This agent is not enabled for the campaign")
    if agent["paused"]:
        return _deny("agent_paused", "This agent is paused")

    if channel:
        ch = next((x for x in c.channels if x["channel"] == channel), None)
        if ch is None or not ch["enabled"]:
            return _deny("channel_disabled", f"{channel} is not enabled for the campaign")
        if ch["paused"]:
            return _deny("channel_paused", f"{channel} is paused for the campaign")

        start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        sent_today = db.scalar(
            select(func.count())
            .select_from(ActivityEvent)
            .where(
                ActivityEvent.campaign_id == campaign_id,
                ActivityEvent.channel == channel,
                ActivityEvent.kind == "send",
                ActivityEvent.status == "completed",
                ActivityEvent.created_at >= start,
            )
        )
        if (sent_today or 0) >= ch["dailyLimit"]:
            return _deny("daily_limit", f"Daily limit of {ch['dailyLimit']} reached for {channel}")

        cap = _platform_cap(db)
        if cap:
            total_today = db.scalar(
                select(func.count())
                .select_from(ActivityEvent)
                .where(
                    ActivityEvent.kind == "send",
                    ActivityEvent.status == "completed",
                    ActivityEvent.created_at >= start,
                )
            )
            if (total_today or 0) >= cap:
                return _deny("platform_cap", f"Platform daily cap of {cap} reached")

    if prospect_email:
        email = prospect_email.strip().lower()
        domain = email.split("@")[-1] if "@" in email else ""
        hit = db.scalar(select(Suppression).where(Suppression.value.in_([email, domain])))
        if hit:
            return _deny("suppressed", f"Prospect is on the do-not-contact list ({hit.reason or hit.type})")

    return Decision(True, "ok", "Allowed")