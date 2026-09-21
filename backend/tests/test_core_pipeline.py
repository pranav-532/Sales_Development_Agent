"""Runs the real pipeline (start, queue, handlers) through the four core agents, with the Groq HTTP call mocked."""
import json
import json as json_lib
import os
import sys
import tempfile

os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.gettempdir(), f"sdr_test_core_{os.getpid()}.db")  # never the real database
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from sqlalchemy import func, select

from app import llm
from app.db import Base, SessionLocal, engine
from app.models.tables import ActivityEvent, AgentJob, Campaign, CampaignProspect, KnowledgeDoc, PromptVersion, utcnow
from app.services import pipeline


def groq_reply(content: dict) -> httpx.Response:
    return httpx.Response(200, json={
        "choices": [{"message": {"content": "<think>reasoning</think>" + json.dumps(content)}}],
        "usage": {"prompt_tokens": 400, "completion_tokens": 120},
    })


def test_core_pipeline_on_groq():
    saved_env = dict(os.environ)
    saved_post = llm.httpx.post
    for name in [n for n in os.environ if n.startswith("GROQ_")]:
        os.environ.pop(name)  # ignore the real keys in backend/.env, the test uses fake ones
    os.environ.update(GROQ_API_KEYS="k1,k2", GROQ_KEY_RPM="6000", DEMO_INBOXES="me@gmail.com")
    os.environ.pop("GROQ_MODEL", None)
    llm._pool = None
    seen = {"models": set(), "auth": set(), "icp_inputs": []}
    counter = {"personalise": 0}

    def fake_post(url, json=None, headers=None, timeout=None):
        assert url == "https://api.groq.com/openai/v1/chat/completions"
        seen["models"].add(json["model"])
        seen["auth"].add(headers["Authorization"])
        system, user = json["messages"][0]["content"], json["messages"][1]["content"]
        data = json_lib.JSONDecoder().raw_decode(user.split("INPUT:\n", 1)[1])[0]
        if "ICP Fitment Agent" in system:
            seen["icp_inputs"].append(data["campaign_icp"])
            ok = data["prospect"]["location"] == data["campaign_icp"]["geography"] and data["prospect"]["job_title"] in data["campaign_icp"]["roles"]
            return groq_reply({"qualified": ok, "score": 88 if ok else 30, "reasons": ["role and geography match" if ok else "wrong geography or role"],
                               "pain_points": ["internal tooling backlog"], "missing_information": []})
        if "Research and Enrichment Agent" in system:
            return groq_reply({"company_summary": "A SaaS company.", "professional_context": "Leads engineering.",
                               "signals": data["facts"][1:3], "confidence": 85, "requires_human_review": False})
        if "Outreach Strategy Agent" in system:
            return groq_reply({"primary_channel": "Phone", "secondary_channel": "fax", "objective": "book a call",
                               "sequence": [{"step": 1, "channel": "Phone"}, {"step": 2, "channel": "Email"}], "reasoning": "senior buyer"})
        if "Personalisation Agent" in system:
            counter["personalise"] += 1
            body = "Hi [First Name], saw your team has a growing tooling queue. We speed teams up 10x. Is that a priority?\n\nBest,\n[Your Name]" if counter["personalise"] == 1 \
                else f"Hi, saw that {data['research']['signals'][0]}\n\nBest regards,\n{data['sender_name']}"
            return groq_reply({"subject": "Internal tooling", "body": body, "confidence": 0.9})
        raise AssertionError("unexpected agent: " + system[:80])

    llm.httpx.post = fake_post
    try:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        with SessionLocal() as db:
            db.add(Campaign(
                id="c1", name="US SaaS CTO", owner="Aarav Mehta", status="draft", icp="SaaS", geography="United States",
                target_roles=["CTO"], approval_mode="none", created_at="2026-09-20", updated_at="2026-09-20",
                agents=[{"key": k, "name": k, "enabled": True, "paused": False} for k in ("icp_fitment", "research", "strategy", "personalisation")],
                channels=[{"channel": n, "enabled": True, "paused": False, "dailyLimit": 100} for n in ("email", "linkedin", "voice")],
            ))
            db.add(PromptVersion(id="p1", campaign_id="c1", agent_key="system", version=1, content="Be brief.", author="a", created_at="x", is_active=True))
            db.add(KnowledgeDoc(id="k1", kb="kb1", title="Approved claims", content="Approved claims: connects to Postgres.", audience=["*"]))
            db.commit()
            c = db.get(Campaign, "c1")
            r = pipeline.start(db, c, {"targetCount": 5, "objective": "Book a call", "cta": "Open to a call?", "tone": "friendly",
                                       "industries": ["SaaS"], "painPoints": [], "companySizeMin": 50, "companySizeMax": 1000})
            assert r["candidates"] >= 5

        for _ in range(400):  # what the worker does: take due jobs, count the attempt, run them
            with SessionLocal() as db:
                jobs = db.scalars(select(AgentJob).where(AgentJob.status == "queued", AgentJob.run_after <= utcnow()).order_by(AgentJob.created_at)).all()
                if not jobs:
                    break
                for j in jobs:
                    j.status, j.attempts = "running", j.attempts + 1
                db.commit()
                ids = [j.id for j in jobs]
            for jid in ids:
                pipeline.run_job(jid)

        with SessionLocal() as db:
            rows = db.scalars(select(CampaignProspect)).all()
            states = {}
            for p in rows:
                states[p.state] = states.get(p.state, 0) + 1
            errs = [j.error for j in db.scalars(select(AgentJob)) if j.error]
            assert not errs, errs
            assert not [p for p in rows if p.state == "FAILED"], [(p.name, p.error) for p in rows if p.state == "FAILED"]
            qualified = [p for p in rows if (p.icp or {}).get("final_qualified")]
            assert len(qualified) >= 5, states
            assert all(p.location == "United States" for p in qualified), "campaign geography must decide the ICP result"
            assert seen["icp_inputs"][0]["geography"] == "United States" and seen["icp_inputs"][0]["roles"] == ["CTO"]

            done = [p for p in rows if p.message]
            assert done
            flagged = [p for p in done if p.message["flags"]]
            assert len(flagged) == 1 and flagged[0].state == "READY_FOR_REVIEW", states
            kinds = " ".join(flagged[0].message["flags"])
            assert "Unresolved placeholder" in kinds and "10x" in kinds and "[Your Name]" not in flagged[0].message["body"], kinds
            clean = [p for p in done if not p.message["flags"]]
            assert clean and all(p.state == "READY_TO_SEND" and p.message["body"].endswith("Open to a call?\n\nBest,\nAarav Mehta") and p.message["body"].count("Aarav Mehta") == 1 and p.message["body"].count("Best") == 1 for p in clean)
            assert all(p.strategy["primary_channel"] in ("email", "linkedin", "voice") and p.strategy["secondary_channel"] != "fax" for p in done)
            assert all(p.strategy["sequence"][0]["channel"] != "voice" for p in done), "never a cold call first"
            assert all("internal tooling backlog" in (p.icp["pain_points"]) for p in qualified)
            assert db.scalar(select(func.sum(ActivityEvent.cost_usd))) > 0
            assert db.get(Campaign, "c1").funnel["qualified"] == len(qualified)
        assert seen["models"] == {"qwen/qwen3.8-27b"} and seen["auth"] == {"Bearer k1", "Bearer k2"}
        print("core pipeline on Groq OK:", states)
    finally:
        llm.httpx.post = saved_post
        llm._pool = None
        os.environ.clear()
        os.environ.update(saved_env)


if __name__ == "__main__":
    test_core_pipeline_on_groq()