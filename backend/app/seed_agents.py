from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tables import KnowledgeDoc

DOCS = [
    ("k1", "kb1", "Loomstack overview", ["*"],
     "Loomstack is a workflow and internal tools platform for engineering teams. Teams build internal apps, approval flows and automations on top of their existing databases and APIs without writing front-end code."),
    ("k2", "kb1", "Approved claims", ["*"],
     "Approved claims: Loomstack connects to Postgres, MySQL, REST and GraphQL sources. It includes role-based access and audit logs. It can be deployed in the customer's own cloud. Do NOT claim SOC 2 or ISO certification, uptime guarantees, or any specific ROI or percentage numbers."),
    ("k3", "kb2", "Case study: Helix Payments (illustrative demo example)", ["c1", "c2"],
     "Helix Payments, a fictional 300-person fintech, replaced a set of hand-built admin scripts with Loomstack internal tools, so engineers spend less time on ad-hoc operations requests."),
    ("k4", "kb3", "Playbook: engineering leaders", ["c1"],
     "For CTOs and VPs of Engineering: lead with time lost to internal tooling requests and one-off scripts. Keep emails under 120 words. End with one clear question."),
    ("k5", "kb3", "Playbook: banks and insurers", ["c2"],
     "For CIOs at banks and insurers: lead with audit logs, access control and deployment inside the customer's own environment. Be formal. Never promise regulatory approval; say Loomstack supports compliance workflows."),
    ("k6", "kb3", "Playbook: voice AI founders", ["c3"],
     "For founders of voice AI startups: lead with how fast their team can build call review and QA dashboards on top of their own data. Keep it casual and short."),
    ("k7", "kb3", "Objection handling", ["*"],
     "Pricing questions: do not quote prices, hand to a human rep. 'We already build this in-house': acknowledge it, then ask how much engineering time the upkeep takes. 'Not now': offer to follow up later."),
    ("k8", "kb4", "Example first email (engineering leaders)", ["c1"],
     "Subject: Fewer internal tool requests. Hi Alex, teams like yours often lose engineering time to internal admin tools and scripts. Loomstack lets engineers build those on top of existing databases and APIs. Worth a short chat? Best, Sender"),
    ("k9", "kb5", "Voice call script", ["*"],
     "Open by confirming you are speaking to the right person and asking if now is a good time. Ask one question about how they handle internal tooling today. If they ask for a human, offer to transfer. If interested, offer a 15-minute meeting."),
]


def seed_agents(db: Session) -> None:
    if db.scalar(select(KnowledgeDoc.id).limit(1)) is not None:
        return
    for did, kb, title, audience, content in DOCS:
        db.add(KnowledgeDoc(id=did, kb=kb, title=title, content=content, audience=audience))
    db.commit()