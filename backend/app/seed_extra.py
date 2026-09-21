from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tables import ActivityEvent, AuditEntry, CampaignStats, PromptVersion, Rep, utcnow

REPS = [
    ("r1", "Rohan Iyer", "rohan@company.com", 60, "9:00 to 18:00 EST", ["linkedin", "email", "voice"]),
    ("r2", "Sara Khan", "sara@company.com", 50, "9:00 to 17:00 PST", ["linkedin", "email"]),
    ("r3", "Vikram Shah", "vikram@company.com", 40, "10:00 to 19:00 IST", ["email", "voice", "linkedin"]),
]

# (id, campaign, agent, version, content, author, created_at, active, note)
PROMPTS = [
    ("p-c1-s1", "c1", "system", 1, "You are an SDR for our product. Be concise and helpful.", "Aarav Mehta", "2026-09-10 11:20", False, "Initial draft"),
    ("p-c1-s2", "c1", "system", 2, "You are an SDR selling to US SaaS CTOs.\nLead with engineering productivity.\nNever claim features we do not have.", "Aarav Mehta", "2026-09-14 15:05", False, "Added ICP and guardrail"),
    ("p-c1-s3", "c1", "system", 3, "You are an SDR selling to US SaaS CTOs.\nLead with engineering productivity and cite a relevant case study retrieved from the knowledge base.\nNever claim features we do not have.\nEscalate pricing questions to a human rep.", "Priya Nair", "2026-09-18 16:40", True, "Added RAG citation and escalation rule"),
    ("p-c1-p1", "c1", "personalisation", 1, "Write a short email that references the prospect's role and company.\nKeep it under 120 words.", "Aarav Mehta", "2026-09-11 10:00", False, "First version"),
    ("p-c1-p2", "c1", "personalisation", 2, "Write a short email that references the prospect's role, company and one recent public signal from the research notes.\nKeep it under 120 words.\nEnd with a single low-pressure question.\nNever invent facts that are not in the research notes.", "Aarav Mehta", "2026-09-16 12:30", True, "Grounded in research notes"),
    ("p-c1-c1", "c1", "conversation", 1, "Read the reply and classify it as positive, neutral or negative.\nIf the prospect asks about pricing or a contract, escalate to a human rep.\nIf they ask to stop, add them to the do-not-contact list.", "Priya Nair", "2026-09-12 09:15", True, "Reply handling rules"),
    ("p-c2-s1", "c2", "system", 1, "You are an SDR for our product selling to banks and insurers in India. Be formal and concise.", "Priya Nair", "2026-09-08 14:00", False, "Initial draft"),
    ("p-c2-s2", "c2", "system", 2, "You are an SDR selling to CIOs and heads of IT at Indian banks, insurers and NBFCs.\nBe formal and concise.\nAddress data residency and RBI compliance concerns using approved answers from the knowledge base.\nNever claim certifications we do not hold.", "Priya Nair", "2026-09-15 17:20", True, "Added compliance handling"),
    ("p-c2-p1", "c2", "personalisation", 1, "Write a formal email to a BFSI technology leader.\nReference a compliance or modernisation priority from the research notes.\nKeep it under 130 words.", "Priya Nair", "2026-09-09 11:45", True, "First version"),
    ("p-c3-s1", "c3", "system", 1, "You are an SDR reaching founders of early stage Voice AI startups.\nBe casual and direct.\nLead with latency and cost per minute.\nOffer a short demo call as the next step.", "Aarav Mehta", "2026-09-12 13:10", True, "Initial version"),
    ("p-c3-v1", "c3", "voice", 1, "Open by confirming you are speaking to the right person.\nQualify on stage, team size and current voice stack.\nIf the prospect asks for a human, transfer the call immediately.", "Aarav Mehta", "2026-09-12 13:40", True, "Call flow"),
    ("p-c4-s1", "c4", "system", 1, "You are an account manager assistant reaching existing customers about expansion.\nReference their current plan and usage from the CRM notes.\nNever offer discounts without human approval.", "Priya Nair", "2026-09-17 10:30", True, "Initial draft"),
]

STATS = {
    "c1": {"outreach": {"linkedin": 150, "email": 210, "sms": 30, "voice": 36}, "followups": 118,
           "outcomes": {"positive": 52, "negative": 21, "neutral": 15},
           "workflows": {"active": 14, "completed": 392, "failed": 9}},
    "c2": {"outreach": {"linkedin": 70, "email": 120, "sms": 0, "voice": 21}, "followups": 64,
           "outcomes": {"positive": 24, "negative": 10, "neutral": 6},
           "workflows": {"active": 6, "completed": 205, "failed": 4}},
    "c3": {"outreach": {"linkedin": 45, "email": 70, "sms": 0, "voice": 27}, "followups": 39,
           "outcomes": {"positive": 19, "negative": 7, "neutral": 5},
           "workflows": {"active": 8, "completed": 133, "failed": 3}},
}

# (id, campaign, agent, action, channel, prompt_version, minutes_ago, status)
EVENTS = [
    ("e1", "c1", "personalisation", "Drafted email to Dana Whitfield (CTO, Northwind Labs)", "email", 3, 3, "completed"),
    ("e2", "c1", "conversation", "Marcus Lee asked about pricing, handed to a human rep", "email", 3, 12, "escalated"),
    ("e3", "c1", "strategy", "Chose LinkedIn first for Priya Raman (VP Eng, Stackly)", "linkedin", 3, 25, "completed"),
    ("e4", "c1", "icp_fitment", "Rejected Orbit Foods: not a SaaS company", None, 3, 41, "completed"),
    ("e5", "c1", "personalisation", "Email to Tom Becker cites a case study, waiting for review", "email", 3, 60, "pending_approval"),
    ("e6", "c1", "research", "Enrichment failed for Helio Systems: Apollo rate limit", None, 2, 120, "failed"),
    ("e7", "c1", "followup", "Scheduled day-3 follow-up to Jenna Cole", "email", 2, 180, "completed"),
    ("e8", "c2", "conversation", "Positive reply from Anil Deshmukh (CIO, Meridian Bank), meeting proposed", "email", 2, 1500, "completed"),
    ("e9", "c2", "voice", "Call with Kavita Rao (Head of IT, SafeLife): handled data residency objection", "voice", 2, 1560, "completed"),
    ("e10", "c2", "strategy", "Skipped Rajesh Iyer: already contacted by another campaign 2 days ago", None, 2, 1620, "completed"),
    ("e11", "c2", "personalisation", "Email to Sunita Menon is waiting for review", "email", 2, 1680, "pending_approval"),
    ("e12", "c2", "research", "Enrichment failed for Apex Finserv: company page unreachable", None, 1, 2900, "failed"),
    ("e13", "c3", "voice", "Qualified call with Sam Ortiz (Founder, Echo Voice), asked for a demo", "voice", 1, 8, "completed"),
    ("e14", "c3", "personalisation", "Drafted LinkedIn note to Lena Fischer (CEO, Talkwave)", "linkedin", 1, 18, "completed"),
    ("e15", "c3", "conversation", "Negative reply from Chris Wu, added to do-not-contact list", "email", 1, 34, "completed"),
    ("e16", "c3", "icp_fitment", "Qualified Nova Speech (seed stage, 12 employees)", None, 1, 52, "completed"),
    ("e17", "c3", "voice", "Mia Torres asked to speak to a human, call transferred", "voice", 1, 60, "escalated"),
    ("e18", "c3", "followup", "Stopped follow-ups for Ivy Chen after 3 touches with no reply", "email", 1, 120, "completed"),
]


def seed_extra(db: Session) -> None:
    if db.scalar(select(Rep.id).limit(1)) is not None:
        return

    for rid, name, email, limit, hours, channels in REPS:
        db.add(Rep(id=rid, name=name, email=email, status="active", daily_limit=limit,
                   working_hours=hours, channels=channels))

    for pid, cid, agent, version, content, author, created, active, note in PROMPTS:
        db.add(PromptVersion(id=pid, campaign_id=cid, agent_key=agent, version=version, content=content,
                             author=author, created_at=created, is_active=active, note=note))
        db.add(AuditEntry(id=f"a-c-{pid}", campaign_id=cid, scope=agent, action="created",
                          version=version, author=author, time=created, note=note))
        if active and version > 1:
            db.add(AuditEntry(id=f"a-a-{pid}", campaign_id=cid, scope=agent, action="activated",
                              version=version, author=author, time=created, note=""))

    for cid, data in STATS.items():
        db.add(CampaignStats(campaign_id=cid, data=data))

    now = utcnow()
    for eid, cid, agent, action, channel, pv, mins, status in EVENTS:
        db.add(ActivityEvent(id=eid, campaign_id=cid, agent_key=agent, action=action, channel=channel,
                             prompt_version=pv, status=status, created_at=now - timedelta(minutes=mins)))
    db.commit()