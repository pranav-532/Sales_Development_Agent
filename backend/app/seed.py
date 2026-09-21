from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tables import Campaign, Suppression

AGENTS = [
    ("icp_fitment", "ICP Fitment Agent"),
    ("research", "Lead Research Agent"),
    ("strategy", "Outreach Strategy Agent"),
    ("personalisation", "Personalisation Agent"),
    ("conversation", "Conversation Agent"),
    ("voice", "Voice SDR Agent"),
    ("followup", "Follow-up Agent"),
]


def _agents() -> list[dict]:
    return [{"key": k, "name": n, "enabled": True, "paused": False} for k, n in AGENTS]


def _channels(li: int, em: int, sms: int, voice: int) -> list[dict]:
    return [
        {"channel": "linkedin", "enabled": li > 0, "paused": False, "dailyLimit": li},
        {"channel": "email", "enabled": em > 0, "paused": False, "dailyLimit": em},
        {"channel": "sms", "enabled": sms > 0, "paused": False, "dailyLimit": sms},
        {"channel": "voice", "enabled": voice > 0, "paused": False, "dailyLimit": voice},
    ]


CAMPAIGNS = [
    dict(
        id="c1", name="US SaaS CTO", owner="Aarav Mehta", status="live", icp="SaaS CTO",
        description="Outbound to CTOs at US SaaS companies with 50 to 500 employees.",
        geography="United States", target_roles=["CTO", "VP Engineering"],
        created_at="2026-09-10", updated_at="2026-09-18", active_prompt_version=3,
        channels=_channels(40, 120, 30, 15),
        funnel={"discovered": 1284, "researched": 980, "qualified": 610, "contacted": 426,
                "engaged": 88, "meeting": 18, "opportunity": 7},
        outreach_count=426, meetings=18, rep_ids=["r1", "r2"],
    ),
    dict(
        id="c2", name="India BFSI CIO", owner="Priya Nair", status="paused", icp="BFSI CIO",
        description="CIOs and CTOs at banks, insurers and NBFCs in India.",
        geography="India", target_roles=["CIO", "Head of IT"],
        created_at="2026-09-08", updated_at="2026-09-19", active_prompt_version=2,
        channels=_channels(25, 80, 0, 10),
        funnel={"discovered": 642, "researched": 500, "qualified": 320, "contacted": 211,
                "engaged": 40, "meeting": 11, "opportunity": 4},
        outreach_count=211, meetings=11, rep_ids=["r3"],
    ),
    dict(
        id="c3", name="Voice AI Founders", owner="Aarav Mehta", status="live", icp="AI Founders",
        description="Founders of early stage Voice AI startups in the US and Europe.",
        geography="US, Europe", target_roles=["Founder", "CEO"],
        created_at="2026-09-12", updated_at="2026-09-18", active_prompt_version=1,
        channels=_channels(30, 90, 0, 20),
        funnel={"discovered": 389, "researched": 300, "qualified": 210, "contacted": 142,
                "engaged": 31, "meeting": 9, "opportunity": 3},
        outreach_count=142, meetings=9, rep_ids=["r1", "r3"],
    ),
    dict(
        id="c4", name="Enterprise Expansion", owner="Priya Nair", status="draft", icp="Existing Customers",
        description="Upsell and cross-sell outreach to existing enterprise customers.",
        geography="Global", target_roles=["Account Owner", "Head of Ops"],
        created_at="2026-09-17", updated_at="2026-09-17", active_prompt_version=1,
        channels=_channels(0, 60, 0, 0),
        funnel={k: 0 for k in ("discovered", "researched", "qualified", "contacted",
                               "engaged", "meeting", "opportunity")},
        outreach_count=0, meetings=0, rep_ids=[],
    ),
]

SUPPRESSIONS = [
    ("s1", "chris.wu@pulsevoice.com", "email", "Opted out by reply", "Conversation Agent", "2026-09-18"),
    ("s2", "competitorco.com", "domain", "Competitor", "Priya Nair", "2026-09-09"),
    ("s3", "bigcustomer.io", "domain", "Existing customer, handled by the account team", "Aarav Mehta", "2026-09-10"),
]


def seed(db: Session) -> None:
    if db.scalar(select(Campaign.id).limit(1)) is not None:
        return
    for row in CAMPAIGNS:
        db.add(
            Campaign(
                **row,
                agents=_agents(),
                company_criteria="", exclusions="", reference_profiles="",
                approval_mode="first_touch", qualify_threshold=70, confidence_threshold=60,
                escalate_on=["pricing", "human_request"],
            )
        )
    for sid, value, kind, reason, by, at in SUPPRESSIONS:
        db.add(Suppression(id=sid, value=value, type=kind, reason=reason, added_by=by, added_at=at))
    db.commit()