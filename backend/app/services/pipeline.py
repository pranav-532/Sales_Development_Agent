import logging
import math
import os
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app import discovery
from app.agents import icp, personalisation, research, strategy
from app.db import SessionLocal
from app.models.tables import ActivityEvent, AgentJob, Campaign, CampaignProspect, utcnow
from app.services.campaign_service import ServiceError, _id, set_status
from app.services.guard import can_act, get_kill_switch

log = logging.getLogger("sdr")

MAX_ATTEMPTS = 3
MAX_CANDIDATE_FACTOR = 4
JOB_TIMEOUT_MIN = 5

RETRY_TARGET = {
    "icp_fitment": "ICP_PENDING",
    "research": "RESEARCH_PENDING",
    "strategy": "STRATEGY_PENDING",
    "personalisation": "PERSONALISATION_PENDING",
}
TRANSITIONS = {
    "DISCOVERED": {"ICP_PENDING"},
    "ICP_PENDING": {"ICP_QUALIFIED", "ICP_REJECTED", "SKIPPED_TARGET_MET"},
    "ICP_QUALIFIED": {"RESEARCH_PENDING"},
    "RESEARCH_PENDING": {"RESEARCHED", "HUMAN_REVIEW"},
    "RESEARCHED": {"STRATEGY_PENDING"},
    "HUMAN_REVIEW": {"STRATEGY_PENDING"},
    "STRATEGY_PENDING": {"STRATEGY_READY"},
    "STRATEGY_READY": {"PERSONALISATION_PENDING"},
    "PERSONALISATION_PENDING": {"READY_FOR_REVIEW", "READY_TO_SEND"},
    "READY_FOR_REVIEW": {"READY_TO_SEND"},
    "FAILED": set(RETRY_TARGET.values()),
}
ANYTIME = {"STOPPED", "FAILED"}
SENT = {"OUTREACH_SENT", "WAITING_FOR_RESPONSE", "RESPONSE_RECEIVED", "CONVERSATION_ACTIVE", "FOLLOWUP_DUE",
        "VOICE_PENDING", "MEETING_PENDING", "MEETING_BOOKED", "COMPLETED"}
ENGAGED = {"RESPONSE_RECEIVED", "CONVERSATION_ACTIVE", "VOICE_PENDING", "MEETING_PENDING", "MEETING_BOOKED"}


def move(p: CampaignProspect, new: str) -> None:
    if new == p.state:
        return
    if new not in ANYTIME and new not in TRANSITIONS.get(p.state, set()):
        raise ValueError(f"Invalid transition {p.state} -> {new}")
    p.state = new


def enqueue(db: Session, campaign_id: str, prospect_id: str, agent: str, delay: int = 0) -> None:
    exists = db.scalar(
        select(AgentJob.id).where(
            AgentJob.prospect_id == prospect_id,
            AgentJob.agent == agent,
            AgentJob.status.in_(("queued", "running", "done")),
        ).limit(1)
    )
    if exists:
        return  # idempotent
    db.add(AgentJob(
        id=_id("j"), campaign_id=campaign_id, prospect_id=prospect_id, agent=agent,
        status="queued", attempts=0, max_attempts=MAX_ATTEMPTS, run_after=utcnow() + timedelta(seconds=delay),
    ))


def log_event(db, c, p, agent, action, status, meta, channel=None) -> ActivityEvent:
    ev = ActivityEvent(
        id=_id("e"), campaign_id=c.id, prospect_id=p.id, agent_key=agent, action=action[:500],
        channel=channel, kind="decision", status=status, prompt_version=c.active_prompt_version,
        source=meta.get("source", "local"), mode="sandbox", tokens_in=meta.get("tokens_in", 0),
        tokens_out=meta.get("tokens_out", 0), cost_usd=meta.get("cost_usd", 0.0),
    )
    db.add(ev)
    db.flush()
    return ev


def is_qualified(icp_result: dict | None) -> bool:
    return bool(icp_result and icp_result.get("final_qualified"))


def qualified_count(db: Session, campaign_id: str) -> int:
    rows = db.scalars(select(CampaignProspect.icp).where(CampaignProspect.campaign_id == campaign_id)).all()
    return sum(1 for r in rows if is_qualified(r))


# ---------- discovery ----------
def discover(db: Session, c: Campaign, count: int) -> int:
    cfg = c.pipeline_config or {}
    existing = db.scalars(select(CampaignProspect).where(CampaignProspect.campaign_id == c.id)).all()
    seen = {(x.name.lower(), x.domain.lower()) for x in existing}
    added = 0
    for cand in discovery.get_source().fetch(c, cfg, offset=len(existing), count=count):
        key = (cand["name"].lower(), cand["domain"].lower())
        if key in seen:
            continue
        seen.add(key)
        p = CampaignProspect(id=_id("cp"), campaign_id=c.id, state="ICP_PENDING", **cand)
        db.add(p)
        db.flush()
        enqueue(db, c.id, p.id, "icp_fitment")
        added += 1
    log.info("[DISCOVERY] %s: %d new candidates", c.id, added)
    return added


_discover_lock = threading.Lock()


def maybe_discover_more(db: Session, c: Campaign) -> None:
    """Keep discovering until qualified >= target or the source is exhausted."""
    target = int((c.pipeline_config or {}).get("targetCount", 0))
    if not target:
        return
    with _discover_lock:
        db.refresh(c)
        if c.status != "live" or get_kill_switch(db):
            return
        rows = db.execute(
            select(CampaignProspect.state, CampaignProspect.icp).where(CampaignProspect.campaign_id == c.id)
        ).all()
        qualified = sum(1 for _, i in rows if is_qualified(i))
        pending = sum(1 for s, _ in rows if s in ("DISCOVERED", "ICP_PENDING"))
        if qualified >= target or pending > 0:
            return
        if len(rows) >= target * MAX_CANDIDATE_FACTOR:
            log.info("[DISCOVERY] %s: candidate cap reached, stopping", c.id)
            return
        discover(db, c, min(max(math.ceil((target - qualified) / 0.6), 5), 50))
        db.commit()


# ---------- stage handlers ----------
def h_icp(db, c, p):
    target = int((c.pipeline_config or {}).get("targetCount", 0))
    if target and qualified_count(db, c.id) >= target:
        move(p, "SKIPPED_TARGET_MET")
        return
    out, meta = icp.run(db, c, p)
    ok = out.qualified and out.score >= c.qualify_threshold
    p.score = out.score
    p.icp = {**out.model_dump(), "final_qualified": ok, "threshold": c.qualify_threshold}
    verdict = "Qualified" if ok else "Rejected"
    why = "; ".join(out.reasons[:2])
    log_event(db, c, p, "icp_fitment", f"{verdict} {p.name} ({p.title}, {p.company}), score {out.score}. {why}", "completed", meta)
    if ok:
        move(p, "ICP_QUALIFIED")
        move(p, "RESEARCH_PENDING")
        enqueue(db, c.id, p.id, "research")
    else:
        move(p, "ICP_REJECTED")
    log.info("[ICP] %s %s score=%s", p.id, verdict.lower(), out.score)


def h_research(db, c, p):
    result, meta = research.run(db, c, p)
    p.research = result
    low = result["confidence"] * 100 < c.confidence_threshold or result["requires_human_review"]
    if low:
        move(p, "HUMAN_REVIEW")
        log_event(db, c, p, "research",
                  f"Research on {p.name} is uncertain (confidence {result['confidence']:.2f}), needs review",
                  "pending_approval", meta)
    else:
        move(p, "RESEARCHED")
        move(p, "STRATEGY_PENDING")
        enqueue(db, c.id, p.id, "strategy")
        log_event(db, c, p, "research", f"Researched {p.name} at {p.company} (confidence {result['confidence']:.2f})", "completed", meta)
    log.info("[RESEARCH] %s completed", p.id)


def h_strategy(db, c, p):
    result, meta = strategy.run(db, c, p)
    p.strategy = result
    move(p, "STRATEGY_READY")
    move(p, "PERSONALISATION_PENDING")
    enqueue(db, c.id, p.id, "personalisation")
    log_event(db, c, p, "strategy", f"{result['primary_channel'].title()} first for {p.name}, then {result['secondary_channel'] or 'stop'}",
              "completed", meta, channel=result["primary_channel"])
    log.info("[STRATEGY] %s %s-first", p.id, result["primary_channel"])


def h_personalisation(db, c, p):
    msg, meta = personalisation.run(db, c, p)
    p.message = msg
    reasons = list(msg["flags"])
    if c.approval_mode != "none":
        reasons.append(f"Campaign approval mode is '{c.approval_mode}'")
    if msg["requires_human_review"]:
        reasons.append("Agent asked for review")
    if msg["confidence"] * 100 < c.confidence_threshold:
        reasons.append("Low confidence")
    p.message = {**msg, "review_reasons": reasons}
    if reasons:
        move(p, "READY_FOR_REVIEW")
        log_event(db, c, p, "personalisation", f"Drafted {msg['channel']} message to {p.name}, waiting for review",
                  "pending_approval", meta, channel=msg["channel"])
    else:
        move(p, "READY_TO_SEND")
        log_event(db, c, p, "personalisation", f"Drafted {msg['channel']} message to {p.name}", "completed", meta, channel=msg["channel"])
    log.info("[PERSONALISATION] %s completed", p.id)


HANDLERS = {
    "icp_fitment": h_icp,
    "research": h_research,
    "strategy": h_strategy,
    "personalisation": h_personalisation,
}


def on_review_decision(db: Session, ev: ActivityEvent, decision: str) -> None:
    """Called when a manager approves or rejects a pending item from the dashboard."""
    if not ev.prospect_id:
        return
    p = db.get(CampaignProspect, ev.prospect_id)
    if p is None:
        return
    if decision == "approved":
        if p.state == "HUMAN_REVIEW":
            move(p, "STRATEGY_PENDING")
            enqueue(db, p.campaign_id, p.id, "strategy")
        elif p.state == "READY_FOR_REVIEW":
            move(p, "READY_TO_SEND")
    else:
        move(p, "STOPPED")
        p.error = "Rejected by reviewer"


# ---------- funnel and summary ----------
def recompute_funnel(db: Session, c: Campaign) -> None:
    rows = db.execute(
        select(CampaignProspect.state, CampaignProspect.icp, CampaignProspect.research).where(CampaignProspect.campaign_id == c.id)
    ).all()
    if not rows:
        return  # seeded demo campaigns keep their sample numbers until they run
    c.funnel = {
        "discovered": len(rows),
        "researched": sum(1 for r in rows if r.research),
        "qualified": sum(1 for r in rows if is_qualified(r.icp)),
        "contacted": sum(1 for r in rows if r.state in SENT),
        "engaged": sum(1 for r in rows if r.state in ENGAGED),
        "meeting": sum(1 for r in rows if r.state == "MEETING_BOOKED"),
        "opportunity": sum(1 for r in rows if r.state == "MEETING_BOOKED"),
    }
    c.outreach_count = c.funnel["contacted"]
    c.meetings = c.funnel["meeting"]


def summary(db: Session, c: Campaign) -> dict:
    cfg = c.pipeline_config or {}
    rows = db.execute(
        select(CampaignProspect.state, CampaignProspect.icp, CampaignProspect.research,
               CampaignProspect.strategy, CampaignProspect.message).where(CampaignProspect.campaign_id == c.id)
    ).all()
    states = Counter(r.state for r in rows)
    qualified = sum(1 for r in rows if is_qualified(r.icp))
    jobs: dict[str, dict[str, int]] = {}
    for agent, status, n in db.execute(
        select(AgentJob.agent, AgentJob.status, func.count()).where(AgentJob.campaign_id == c.id).group_by(AgentJob.agent, AgentJob.status)
    ).all():
        jobs.setdefault(agent, {})[status] = n
    usd, tin, tout = db.execute(
        select(func.coalesce(func.sum(ActivityEvent.cost_usd), 0.0), func.coalesce(func.sum(ActivityEvent.tokens_in), 0),
               func.coalesce(func.sum(ActivityEvent.tokens_out), 0)).where(ActivityEvent.campaign_id == c.id, ActivityEvent.prospect_id.is_not(None))
    ).one()
    active = sum(v.get("queued", 0) + v.get("running", 0) for v in jobs.values())
    return {
        "targetCount": cfg.get("targetCount", 0),
        "config": cfg,
        "discovered": len(rows),
        "qualified": qualified,
        "rejected": states.get("ICP_REJECTED", 0),
        "researched": sum(1 for r in rows if r.research),
        "strategised": sum(1 for r in rows if r.strategy),
        "personalised": sum(1 for r in rows if r.message),
        "awaitingReview": states.get("READY_FOR_REVIEW", 0) + states.get("HUMAN_REVIEW", 0),
        "readyToSend": states.get("READY_TO_SEND", 0),
        "sent": sum(1 for r in rows if r.state in SENT),
        "failed": states.get("FAILED", 0),
        "stopped": states.get("STOPPED", 0),
        "byState": dict(states),
        "jobs": jobs,
        "running": {a: v.get("running", 0) for a, v in jobs.items() if v.get("running")},
        "active": active > 0,
        "cost": {
            "usd": round(float(usd), 4), "tokensIn": int(tin), "tokensOut": int(tout),
            "perProspect": round(float(usd) / len(rows), 5) if rows else 0.0,
            "perQualified": round(float(usd) / qualified, 5) if qualified else 0.0,
        },
    }


# ---------- campaign start / retry ----------
def start(db: Session, c: Campaign, cfg: dict) -> dict:
    if c.status not in ("draft", "live"):
        raise ServiceError(f"A {c.status} campaign cannot be started", 409)
    if get_kill_switch(db):
        raise ServiceError("Release the global kill switch first", 423)
    if not any(ch["enabled"] for ch in c.channels):
        raise ServiceError("Enable at least one channel first", 422)
    if int(cfg["companySizeMin"]) > int(cfg["companySizeMax"]):
        raise ServiceError("Company size minimum is above the maximum", 422)
    if db.scalar(select(func.count()).select_from(CampaignProspect).where(CampaignProspect.campaign_id == c.id)):
        raise ServiceError("This campaign already has a run. Use pause and resume instead.", 409)

    c.pipeline_config = cfg
    set_status(db, c.id, "live")
    first = min(max(5, math.ceil(cfg["targetCount"] / 0.6)), 40)
    added = discover(db, c, first)
    db.commit()
    log.info("[CAMPAIGN] %s started, target=%s", c.id, cfg["targetCount"])
    return {"campaignId": c.id, "status": c.status, "targetCount": cfg["targetCount"], "candidates": added}


def retry(db: Session, prospect_id: str) -> CampaignProspect:
    p = db.get(CampaignProspect, prospect_id)
    if p is None:
        raise ServiceError("Prospect not found", 404)
    if p.state != "FAILED":
        raise ServiceError("Only failed prospects can be retried", 409)
    job = db.scalar(
        select(AgentJob).where(AgentJob.prospect_id == p.id, AgentJob.status == "dead").order_by(AgentJob.finished_at.desc()).limit(1)
    )
    if job is None:
        raise ServiceError("No failed step found for this prospect", 409)
    move(p, RETRY_TARGET[job.agent])
    p.error = ""
    enqueue(db, p.campaign_id, p.id, job.agent)
    db.commit()
    return p


# ---------- worker ----------
def _fail(job_id: str, e: Exception) -> None:
    with SessionLocal() as db:
        job = db.get(AgentJob, job_id)
        if job is None:
            return
        msg = f"{type(e).__name__}: {str(e)[:250]}"
        job.error = msg
        if job.attempts >= job.max_attempts:
            job.status = "dead"
            job.finished_at = utcnow()
            p = db.get(CampaignProspect, job.prospect_id)
            c = db.get(Campaign, job.campaign_id)
            if p:
                p.state = "FAILED"
                p.error = msg
            if p and c:
                log_event(db, c, p, job.agent, f"{job.agent} failed for {p.name}: {msg}", "failed", {})
            log.warning("[%s] %s FAILED: %s", job.agent, job.prospect_id, msg)
        else:
            job.status = "queued"
            job.run_after = utcnow() + timedelta(seconds=min(300, 5 * 2**job.attempts))
            log.warning("[%s] %s retry %d: %s", job.agent, job.prospect_id, job.attempts, msg)
        db.commit()


def run_job(job_id: str) -> None:
    with SessionLocal() as db:
        job = db.get(AgentJob, job_id)
        if job is None:
            return
        try:
            c = db.get(Campaign, job.campaign_id)
            p = db.get(CampaignProspect, job.prospect_id)
            if c is None or p is None:
                raise ValueError("Missing campaign or prospect")
            d = can_act(db, c.id, job.agent)
            if not d.allowed:  # paused agent, kill switch, etc.: wait, do not burn an attempt
                job.status = "queued"
                job.attempts = max(0, job.attempts - 1)
                job.run_after = utcnow() + timedelta(seconds=10)
                db.commit()
                return
            HANDLERS[job.agent](db, c, p)
            job.status = "done"
            job.error = ""
            job.finished_at = utcnow()
            db.commit()
        except Exception as e:
            db.rollback()
            _fail(job_id, e)
            return

        try:
            if job.agent == "icp_fitment":
                maybe_discover_more(db, c)
            recompute_funnel(db, c)
            db.commit()
        except Exception:
            db.rollback()
            log.exception("post-job update failed")


class Worker:
    def __init__(self) -> None:
        self.concurrency = int(os.getenv("AGENT_CONCURRENCY", "4"))
        self.pool = ThreadPoolExecutor(max_workers=self.concurrency)
        self.inflight: set[str] = set()
        self.lock = threading.Lock()
        self.stop_flag = threading.Event()

    def start(self) -> None:
        with SessionLocal() as db:  # resume after a crash or restart
            for j in db.scalars(select(AgentJob).where(AgentJob.status == "running")).all():
                j.status = "queued"
                j.attempts = max(0, j.attempts - 1)
            db.commit()
        threading.Thread(target=self._loop, daemon=True).start()
        log.info("[WORKER] started, concurrency=%d", self.concurrency)

    def stop(self) -> None:
        self.stop_flag.set()
        self.pool.shutdown(wait=False, cancel_futures=True)

    def _loop(self) -> None:
        while not self.stop_flag.is_set():
            try:
                self._tick()
            except Exception:
                log.exception("worker tick failed")
            self.stop_flag.wait(1.5)

    def _done(self, job_id: str) -> None:
        with self.lock:
            self.inflight.discard(job_id)

    def _tick(self) -> None:
        with self.lock:
            free = self.concurrency - len(self.inflight)
            inflight = set(self.inflight)
        ids: list[str] = []
        with SessionLocal() as db:
            if get_kill_switch(db):
                return
            now = utcnow()
            for j in db.scalars(select(AgentJob).where(AgentJob.status == "running", AgentJob.started_at < now - timedelta(minutes=JOB_TIMEOUT_MIN))).all():
                if j.id not in inflight:
                    j.status = "queued"  # timed out
            if free > 0:
                prio = case({"personalisation": 0, "strategy": 1, "research": 2}, value=AgentJob.agent, else_=3)
                per: dict[str, list[AgentJob]] = {}
                for cid in db.scalars(select(Campaign.id).where(Campaign.status == "live")).all():
                    per[cid] = list(db.scalars(
                        select(AgentJob).where(AgentJob.campaign_id == cid, AgentJob.status == "queued", AgentJob.run_after <= now)
                        .order_by(prio, AgentJob.created_at).limit(free)
                    ))
                picked: list[AgentJob] = []
                while len(picked) < free and any(per.values()):  # round-robin so campaigns share capacity
                    for cid in list(per):
                        if per[cid] and len(picked) < free:
                            picked.append(per[cid].pop(0))
                for j in picked:
                    j.status = "running"
                    j.started_at = now
                    j.attempts += 1
                    ids.append(j.id)
            db.commit()
        for jid in ids:
            with self.lock:
                self.inflight.add(jid)
            self.pool.submit(run_job, jid).add_done_callback(lambda _f, jid=jid: self._done(jid))


worker = Worker()