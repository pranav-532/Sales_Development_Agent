import json
import os
import sys
import tempfile

os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.gettempdir(), f"sdr_test_drona_{os.getpid()}.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from sqlalchemy import func, select

from app import llm
from app.agents import icp, personalisation, research, strategy
from app.agents.schemas import IcpOut, MessageOut
from app.db import Base, SessionLocal, engine
from app.integrations.dronahq import client as dronahq_client, run_icp, run_personalisation
from app.integrations.dronahq.client import DronaHQError, DronaHQResponseError, parse_dronahq_payload
from app.models.tables import ActivityEvent, AgentJob, Campaign, CampaignProspect, KnowledgeDoc, PromptVersion, utcnow
from app.services import pipeline


def test_dronahq_client_payload_parsing():
    # 1. Direct dict
    d1 = {"qualified": True, "score": 90}
    assert parse_dronahq_payload(d1) == d1

    # 2. Nested under 'output'
    d2 = {"output": {"qualified": True, "score": 85}}
    assert parse_dronahq_payload(d2) == {"qualified": True, "score": 85}

    # 3. Stringified JSON
    d3 = '{"qualified": false, "score": 40}'
    assert parse_dronahq_payload(d3) == {"qualified": False, "score": 40}

    # 4. Markdown code block
    d4 = '```json\n{"subject": "Hello", "body": "Custom message"}\n```'
    assert parse_dronahq_payload(d4) == {"subject": "Hello", "body": "Custom message"}

    # 5. Stringified JSON nested under 'response'
    d5 = {"response": '```json\n{"subject": "Test", "body": "World"}\n```'}
    assert parse_dronahq_payload(d5) == {"subject": "Test", "body": "World"}


def test_dronahq_icp_and_personalisation_one_prospect():
    """Phase 4 & 5: Tests 1 prospect through DronaHQ ICP and DronaHQ Personalisation adapters."""
    c = Campaign(
        id="c_drona_1", name="Test Drona Campaign", owner="Sales Rep", status="live",
        icp="SaaS", geography="United States", target_roles=["CTO"],
        pipeline_config={"targetCount": 1, "objective": "Demo", "cta": "Open to chat?", "tone": "direct"},
    )
    p = CampaignProspect(
        id="p_drona_1", campaign_id="c_drona_1", name="Alice Smith", title="CTO",
        company="Acme Cloud", domain="acme.example", location="United States",
        industry="SaaS", company_size=120, state="ICP_PENDING",
        facts=["Acme Cloud uses Postgres.", "Engineering team is scaling fast."],
    )

    # Test ICP Adapter with mocked Drona webhook response
    icp_mock_response = {
        "output": {
            "qualified": True,
            "score": 95,
            "reasons": ["Role CTO and US location match target profile"],
            "pain_points": ["scaling bottlenecks"],
            "missing_information": [],
            "requires_human_review": False,
        }
    }

    def fake_post_icp(self, url, json=None, headers=None, timeout=None):
        assert "icp" in url.lower()
        return httpx.Response(200, json=icp_mock_response, request=httpx.Request("POST", url))

    saved_client_post = dronahq_client.httpx.Client.post
    dronahq_client.httpx.Client.post = fake_post_icp
    os.environ["DRONA_ICP_WEBHOOK_URL"] = "https://dronahq.example.com/api/v1/agent/icp"
    os.environ["DRONA_ICP_API_KEY"] = "secret_icp_key"

    try:
        icp_res = run_icp(c, p)
        assert isinstance(icp_res, IcpOut)
        assert icp_res.qualified is True
        assert icp_res.score == 95
        assert "scaling bottlenecks" in icp_res.pain_points
    finally:
        dronahq_client.httpx.Client.post = saved_client_post

    # Test Personalisation Adapter with mocked Drona webhook response
    p.research = {
        "company_summary": "Acme Cloud is a fast-growing SaaS company.",
        "professional_context": "Alice leads cloud infrastructure.",
        "signals": ["scaling cloud operations"],
        "confidence": 0.9,
    }
    p.strategy = {"primary_channel": "email", "reasoning": "Email first for technical leadership."}
    p.icp = icp_res.model_dump()
    docs = [{"title": "Approved Claims", "content": "Connects natively to Postgres."}]

    pers_mock_response = {
        "result": {
            "subject": "Cloud scaling at Acme Cloud",
            "body": "Hi Alice, saw that your engineering team is scaling fast. We connect directly to Postgres to simplify data access.",
            "cta": "Open to chat?",
            "personalization_points": ["engineering scaling"],
            "confidence": 0.95,
            "requires_human_review": False,
        }
    }

    def fake_post_pers(self, url, json=None, headers=None, timeout=None):
        assert "personalisation" in url.lower()
        return httpx.Response(200, json=pers_mock_response, request=httpx.Request("POST", url))

    dronahq_client.httpx.Client.post = fake_post_pers
    os.environ["DRONA_PERSONALISATION_WEBHOOK_URL"] = "https://dronahq.example.com/api/v1/agent/personalisation"
    os.environ["DRONA_PERSONALISATION_API_KEY"] = "secret_pers_key"

    try:
        pers_res = run_personalisation(c, p, docs, "email", "Open to chat?")
        assert isinstance(pers_res, MessageOut)
        assert pers_res.subject == "Cloud scaling at Acme Cloud"
        assert "Postgres" in pers_res.body
    finally:
        dronahq_client.httpx.Client.post = saved_client_post


def test_full_pipeline_with_dronahq_5_prospects():
    """Phase 6 & 7: End-to-end pipeline test across 5 prospects:
    Discovery -> Drona ICP -> Local Research -> Local Strategy -> Drona Personalisation
    """
    saved_env = dict(os.environ)
    saved_groq_post = llm.httpx.post
    saved_drona_post = dronahq_client.httpx.Client.post

    os.environ.update(
        GROQ_API_KEYS="k_test_1,k_test_2",
        GROQ_KEY_RPM="6000",
        DEMO_INBOXES="tester@example.com",
        DRONA_ICP_WEBHOOK_URL="https://dronahq.example.com/webhook/icp",
        DRONA_ICP_API_KEY="drona_icp_token",
        DRONA_PERSONALISATION_WEBHOOK_URL="https://dronahq.example.com/webhook/personalisation",
        DRONA_PERSONALISATION_API_KEY="drona_pers_token",
        ICP_PROVIDER="dronahq",
        PERSONALISATION_PROVIDER="dronahq",
    )
    llm._pool = None

    drona_calls = {"icp": 0, "personalisation": 0}
    groq_calls = {"research": 0, "strategy": 0}

    # Mock DronaHQ Webhooks
    def fake_drona_client_post(self, url, json=None, headers=None, timeout=None):
        assert headers.get("Authorization") in ("Bearer drona_icp_token", "Bearer drona_pers_token")
        if "icp" in url:
            drona_calls["icp"] += 1
            prop = json["prospect"]
            cicp = json["campaign_icp"]
            ok = prop["location"] == cicp["geography"] and prop["job_title"] in cicp["roles"]
            return httpx.Response(200, json={
                "output": {
                    "qualified": ok,
                    "score": 92 if ok else 35,
                    "reasons": ["Target title and geography match" if ok else "Off-target role or location"],
                    "pain_points": ["internal tooling overhead"],
                    "missing_information": [],
                    "requires_human_review": False,
                }
            }, request=httpx.Request("POST", url))
        if "personalisation" in url:
            drona_calls["personalisation"] += 1
            prop = json["prospect"]
            sender = json["sender_name"]
            return httpx.Response(200, json={
                "response": f"```json\n{{\"subject\": \"Tooling for {prop['company']}\", \"body\": \"Hi {prop['name']}, noticed your team handles custom tools. We integrate natively with Postgres.\", \"cta\": \"Open to a call?\", \"confidence\": 0.9}}\n```"
            }, request=httpx.Request("POST", url))
        raise AssertionError("Unexpected Drona URL: " + url)

    # Mock Local Groq LLM Calls for Research and Strategy
    def fake_groq_post(url, json=None, headers=None, timeout=None):
        payload = json or {}
        system = payload["messages"][0]["content"]
        user = payload["messages"][1]["content"]
        import json as json_mod
        data = json_mod.loads(user.split("INPUT:\n", 1)[1])
        if "Research and Enrichment Agent" in system:
            groq_calls["research"] += 1
            return httpx.Response(200, json={
                "choices": [{"message": {"content": json_mod.dumps({
                    "company_summary": f"{data['prospect']['company']} builds software.",
                    "professional_context": f"{data['prospect']['name']} oversees infrastructure.",
                    "signals": data.get("facts", ["growing team"])[1:3],
                    "confidence": 0.88,
                    "requires_human_review": False,
                })}}],
                "usage": {"prompt_tokens": 300, "completion_tokens": 100},
            })
        if "Outreach Strategy Agent" in system:
            groq_calls["strategy"] += 1
            return httpx.Response(200, json={
                "choices": [{"message": {"content": json_mod.dumps({
                    "primary_channel": "email",
                    "secondary_channel": "linkedin",
                    "objective": "book demo",
                    "sequence": [{"step": 1, "channel": "email"}, {"step": 2, "channel": "linkedin"}],
                    "reasoning": "Standard enterprise CTO cadence.",
                    "requires_human_review": False,
                })}}],
                "usage": {"prompt_tokens": 320, "completion_tokens": 110},
            })
        raise AssertionError("Unexpected Groq agent: " + system[:80])

    dronahq_client.httpx.Client.post = fake_drona_client_post
    llm.httpx.post = fake_groq_post

    try:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        with SessionLocal() as db:
            db.add(Campaign(
                id="c_drona_pipe", name="Drona SaaS Outreach", owner="Rohan Verma", status="draft",
                icp="SaaS", geography="United States", target_roles=["CTO"], approval_mode="none",
                created_at="2026-09-20", updated_at="2026-09-20",
                agents=[{"key": k, "name": k, "enabled": True, "paused": False} for k in ("icp_fitment", "research", "strategy", "personalisation")],
                channels=[{"channel": "email", "enabled": True, "paused": False, "dailyLimit": 100}],
            ))
            db.add(PromptVersion(id="pv1", campaign_id="c_drona_pipe", agent_key="system", version=1, content="Be precise.", author="admin", created_at="2026-09-20", is_active=True))
            db.add(KnowledgeDoc(id="kd1", kb="kb1", title="Approved claims", content="Approved claims: connects to Postgres.", audience=["*"]))
            db.commit()

            c = db.get(Campaign, "c_drona_pipe")
            r = pipeline.start(db, c, {
                "targetCount": 5, "objective": "Book a meeting", "cta": "Open to a call?",
                "tone": "direct", "industries": ["SaaS"], "painPoints": [],
                "companySizeMin": 50, "companySizeMax": 1000,
            })
            assert r["candidates"] >= 5

        # Execute queued jobs through worker loop
        for _ in range(300):
            with SessionLocal() as db:
                jobs = db.scalars(
                    select(AgentJob).where(AgentJob.status == "queued", AgentJob.run_after <= utcnow())
                    .order_by(AgentJob.created_at)
                ).all()
                if not jobs:
                    break
                for j in jobs:
                    j.status, j.attempts = "running", j.attempts + 1
                db.commit()
                ids = [j.id for j in jobs]
            for jid in ids:
                pipeline.run_job(jid)

        # Verification of results in database
        with SessionLocal() as db:
            prospects = db.scalars(select(CampaignProspect)).all()
            assert len(prospects) >= 5

            # ICP checks
            qualified = [p for p in prospects if (p.icp or {}).get("final_qualified")]
            assert len(qualified) >= 5
            assert drona_calls["icp"] >= 5

            # Local agents checks
            assert groq_calls["research"] >= 5
            assert groq_calls["strategy"] >= 5

            # Personalisation checks (DronaHQ)
            assert drona_calls["personalisation"] >= 5
            completed_messages = [p for p in prospects if p.message]
            assert len(completed_messages) >= 5

            for p in completed_messages:
                assert p.state == "READY_TO_SEND"
                assert "Postgres" in p.message["body"]
                assert p.message["body"].endswith("Open to a call?\n\nBest,\nRohan Verma")
                assert (p.icp or {}).get("final_qualified") is True

            # Audit events check
            events = db.scalars(select(ActivityEvent)).all()
            assert len(events) > 0
            drona_events = [e for e in events if e.source == "dronahq"]
            assert len(drona_events) >= 10  # at least 5 ICP + 5 Personalisation events

            # No dead jobs or unhandled failures
            dead_jobs = db.scalars(select(AgentJob).where(AgentJob.status == "dead")).all()
            assert len(dead_jobs) == 0

        print(f"PIPELINE VERIFIED: {drona_calls['icp']} Drona ICP calls, {drona_calls['personalisation']} Drona Personalisation calls, {len(completed_messages)} messages ready to send.")

    finally:
        dronahq_client.httpx.Client.post = saved_drona_post
        llm.httpx.post = saved_groq_post
        llm._pool = None
        os.environ.clear()
        os.environ.update(saved_env)


if __name__ == "__main__":
    test_dronahq_client_payload_parsing()
    print("test_dronahq_client_payload_parsing PASSED")
    test_dronahq_icp_and_personalisation_one_prospect()
    print("test_dronahq_icp_and_personalisation_one_prospect PASSED")
    test_full_pipeline_with_dronahq_5_prospects()
    print("test_full_pipeline_with_dronahq_5_prospects PASSED")
