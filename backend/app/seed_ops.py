from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tables import GlobalState, Prospect

DOTS = "\u2022" * 4

# (id, name, title, company, email, campaigns, touches as (campaign, channel, daysAgo), )
PROSPECTS = [
    ("pr1", "Dana Whitfield", "CTO", "Northwind Labs", "dana.whitfield@northwindlabs.io", ["c1", "c3"],
     [("c1", "email", 1), ("c3", "email", 2), ("c1", "linkedin", 4), ("c3", "linkedin", 5)]),
    ("pr2", "Marcus Lee", "VP Engineering", "Stackly", "marcus.lee@stackly.io", ["c1"],
     [("c1", "email", 1), ("c1", "email", 3), ("c1", "linkedin", 4), ("c1", "sms", 6)]),
    ("pr3", "Sam Ortiz", "Founder", "Echo Voice", "sam@echovoice.ai", ["c1", "c3"],
     [("c3", "voice", 1), ("c1", "email", 2)]),
    ("pr4", "Rajesh Iyer", "CTO", "Finvoice AI", "rajesh.iyer@finvoice.ai", ["c2", "c3"],
     [("c2", "email", 3), ("c3", "email", 2)]),
    ("pr5", "Chris Wu", "Founder", "Pulse Voice", "chris.wu@pulsevoice.com", ["c1", "c3"],
     [("c3", "email", 6), ("c1", "linkedin", 1)]),
    ("pr6", "Lena Fischer", "CEO", "Talkwave", "lena@talkwave.ai", ["c3"], [("c3", "linkedin", 2)]),
    ("pr7", "Kavita Rao", "Head of IT", "SafeLife", "kavita.rao@safelife.in", ["c2"], [("c2", "voice", 1)]),
    ("pr8", "Tom Becker", "CTO", "Helio Systems", "tom.becker@heliosystems.io", ["c1"], [("c1", "email", 2)]),
    ("pr9", "Anil Deshmukh", "CIO", "Meridian Bank", "anil.deshmukh@meridianbank.in", ["c2"], [("c2", "email", 1)]),
]

SETTINGS = {
    "integrations": [
        {"id": "dronahq", "name": "DronaHQ Agentic Platform", "purpose": "Runs the agents and the vibe-coded apps", "status": "connected", "account": "Workspace: sdr-buildathon", "keyHint": f"{DOTS}8f2a", "lastSync": "2 min ago", "required": True},
        {"id": "apollo", "name": "Apollo.io", "purpose": "Lead discovery and enrichment", "status": "connected", "account": "team@company.com", "keyHint": f"{DOTS}41c9", "lastSync": "5 min ago", "required": False},
        {"id": "gmail", "name": "Gmail", "purpose": "Sends email and reads replies", "status": "connected", "account": "outreach@company.com", "keyHint": f"{DOTS}b7d0", "lastSync": "1 min ago", "required": False},
        {"id": "twilio", "name": "Twilio", "purpose": "SMS and voice calls", "status": "error", "account": "Account AC" + DOTS + "92", "keyHint": f"{DOTS}3e11", "lastSync": "3 hr ago", "required": False, "message": "Auth token was rejected. Reconnect to resume SMS and voice."},
        {"id": "linkedin", "name": "LinkedIn automation", "purpose": "Connection requests and messages", "status": "disconnected", "account": "", "keyHint": "", "lastSync": "Never", "required": False},
        {"id": "crm", "name": "CRM (Google Sheets)", "purpose": "Logs every touch and outcome", "status": "connected", "account": "SDR Pipeline sheet", "keyHint": f"{DOTS}5a08", "lastSync": "8 min ago", "required": False},
        {"id": "vector", "name": "Vector database", "purpose": "Stores knowledge for retrieval (RAG)", "status": "connected", "account": "pgvector, index: sdr-knowledge", "keyHint": f"{DOTS}c2f4", "lastSync": "12 min ago", "required": True},
    ],
    "models": [
        {"id": "flash-lite", "name": "Gemini Flash-Lite", "provider": "Google", "note": "Fast and cheap, good for simple decisions", "cost": "$", "speed": "Fastest", "enabled": True},
        {"id": "flash", "name": "Gemini Flash", "provider": "Google", "note": "Balanced quality, speed and cost", "cost": "$$", "speed": "Medium", "enabled": True},
        {"id": "pro", "name": "Gemini Pro", "provider": "Google", "note": "Most capable, best for judging and hard reasoning", "cost": "$$$", "speed": "Slower", "enabled": True},
    ],
    "routing": [
        {"task": "ICP fitment scoring", "hint": "High volume, simple rubric", "modelId": "flash-lite"},
        {"task": "Reply classification", "hint": "Positive, neutral or negative", "modelId": "flash-lite"},
        {"task": "Research summaries", "hint": "Builds structured prospect context", "modelId": "flash"},
        {"task": "Outreach strategy", "hint": "Decides channel, timing and approach", "modelId": "flash"},
        {"task": "Personalised email writing", "hint": "Customer-facing, needs good tone", "modelId": "flash"},
        {"task": "Voice conversations", "hint": "Low latency matters", "modelId": "flash"},
        {"task": "Evaluation (LLM as judge)", "hint": "Scores outputs against the golden set", "modelId": "pro"},
    ],
    "tools": [
        {"id": "rag", "name": "Knowledge retrieval (RAG)", "hint": "Search the knowledge bases before writing anything", "enabled": True},
        {"id": "web", "name": "Web search", "hint": "Look up recent company news", "enabled": True},
        {"id": "crm", "name": "CRM read and write", "hint": "Log touches and update stages", "enabled": True},
        {"id": "calendar", "name": "Calendar booking", "hint": "Book meetings with reps", "enabled": True},
        {"id": "email", "name": "Send email", "hint": "Outbound messages through Gmail", "enabled": True},
        {"id": "calls", "name": "Place calls", "hint": "Outbound voice through Twilio", "enabled": True},
    ],
    "guardrails": [
        {"id": "g-dnc", "label": "Respect the do-not-contact list", "hint": "No agent can contact a suppressed prospect, whatever the campaign says", "enabled": True, "locked": True},
        {"id": "g-ground", "label": "Ground claims in the knowledge base", "hint": "Product claims must come from retrieved sources. Ungrounded claims are blocked.", "enabled": True},
        {"id": "g-price", "label": "Block unapproved pricing and discounts", "hint": "Agents cannot quote prices or offer discounts without a human", "enabled": True},
        {"id": "g-scan", "label": "Scan outgoing messages", "hint": "Catch legal claims, competitor attacks and personal data before sending", "enabled": True},
        {"id": "g-conf", "label": "Escalate when confidence is low", "hint": "Uses each campaign's confidence threshold", "enabled": True},
        {"id": "g-stop", "label": "Stop after 3 unanswered follow-ups", "hint": "Prevents chasing prospects who are not replying", "enabled": True},
    ],
    "policies": {"dailyCap": 500, "windowStart": 8, "windowEnd": 20},
    "knowledge": [
        {"id": "kb1", "name": "Product and company information", "description": "Features, pricing tiers, positioning, security and compliance answers", "docs": 24, "updated": "2026-09-16", "enabled": True},
        {"id": "kb2", "name": "Customer case studies", "description": "Outcomes by industry and company size", "docs": 12, "updated": "2026-09-15", "enabled": True},
        {"id": "kb3", "name": "Sales playbooks and objections", "description": "Approved responses to common objections", "docs": 18, "updated": "2026-09-14", "enabled": True},
        {"id": "kb4", "name": "Example emails and messages", "description": "High quality outreach for different scenarios", "docs": 40, "updated": "2026-09-17", "enabled": True},
        {"id": "kb5", "name": "Voice call scripts", "description": "Call flows and sample conversations", "docs": 9, "updated": "2026-09-13", "enabled": True},
    ],
    "users": [
        {"id": "u1", "name": "Aarav Mehta", "email": "aarav@company.com", "role": "admin"},
        {"id": "u2", "name": "Priya Nair", "email": "priya@company.com", "role": "manager"},
        {"id": "u3", "name": "Meera Shah", "email": "meera@company.com", "role": "viewer"},
    ],
    "auth": {"sso": True, "mfa": False},
}


def seed_ops(db: Session) -> None:
    if db.scalar(select(Prospect.id).limit(1)) is None:
        for pid, name, title, company, email, camps, touches in PROSPECTS:
            db.add(Prospect(
                id=pid, name=name, title=title, company=company, email=email, campaign_ids=camps,
                touches=[{"campaignId": c, "channel": ch, "daysAgo": d} for c, ch, d in touches],
            ))
    if db.get(GlobalState, "settings") is None:
        db.add(GlobalState(key="settings", value=SETTINGS))
    db.commit()