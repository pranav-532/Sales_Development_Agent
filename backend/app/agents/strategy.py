import json

from sqlalchemy.orm import Session

from app.agents.base import build_system
from app.agents.schemas import Step, StrategyOut
from app.llm import generate_json, model_for
from app.models.tables import Campaign, CampaignProspect
from app.rag import retrieve

ROLE = (
    "Outreach Strategy Agent. Decide how to approach this prospect: which channel first, what follows, and why. "
    "You do not write or send messages."
)

# Channel logic from the prototype.
RULES = (
    "Channel rules:\n"
    "- A CTO or VP Engineering at a larger company: email first, they rarely answer LinkedIn messages from strangers.\n"
    "- A founder or startup leader: LinkedIn first, they are more active there.\n"
    "- A strong buying signal in the research: voice (a call) can be the second or third step, never the first message to a stranger.\n"
    "- Use only channels listed in available_channels. Never invent a channel.\n"
    "Give a sequence of 1 to 3 steps, for example email, then linkedin, then email. "
    "Set requires_human_review=true if the signals are very weak or the role is ambiguous. Follow the playbook."
)


def available_channels(c: Campaign, p: CampaignProspect) -> list[str]:
    out = []
    for ch in c.channels:
        if not ch["enabled"] or ch["paused"]:
            continue
        if ch["channel"] == "email" and not p.email:
            continue
        out.append(ch["channel"])
    return out


def run(db: Session, c: Campaign, p: CampaignProspect) -> tuple[dict, dict]:
    cfg = c.pipeline_config or {}
    avail = available_channels(c, p)
    if not avail:
        raise ValueError("No channel is available for this prospect")
    docs = retrieve(db, c.id, f"{c.icp} {' '.join(c.target_roles)} {cfg.get('objective', '')} playbook strategy", k=3)
    payload = {
        "prospect": {"name": p.name, "job_title": p.title, "company": p.company, "company_size": p.company_size},
        "icp_result": {"score": p.icp.get("score"), "reasons": p.icp.get("reasons", [])},
        "research": {
            "summary": p.research.get("company_summary"),
            "context": p.research.get("professional_context"),
            "signals": p.research.get("signals", []),
            "confidence": p.research.get("confidence"),
        },
        "available_channels": avail,
        "objective": cfg.get("objective", ""),
        "playbook": [{"title": d["title"], "content": d["content"]} for d in docs],
    }
    model, tier = model_for(db, "Outreach strategy")
    user = (
        RULES + "\n"
        'Return JSON: {"primary_channel": str, "secondary_channel": str or null, "objective": str, '
        '"sequence": [{"step": int, "channel": str, "purpose": str}], "reasoning": str (max 2 sentences), '
        '"requires_human_review": bool}\n\nINPUT:\n' + json.dumps(payload)
    )
    out, meta = generate_json(model, tier, build_system(db, c.id, "strategy", ROLE), user, StrategyOut, temperature=0.3)

    # The model can only pick from channels that really work for this prospect, and a call is never the first touch.
    first_touch = [a for a in avail if a != "voice"]
    if not first_touch:
        raise ValueError("Only voice is enabled, and a cold call is never the first touch")
    if out.primary_channel not in first_touch:
        out.primary_channel = first_touch[0]
    if out.secondary_channel not in avail or out.secondary_channel == out.primary_channel:
        out.secondary_channel = next((a for a in avail if a != out.primary_channel), None)
    out.sequence = [s for s in out.sequence if s.channel in avail] or [
        Step(step=1, channel=out.primary_channel, purpose="initial_outreach")
    ]
    if out.sequence[0].channel == "voice":
        out.sequence[0].channel = out.primary_channel
    result = out.model_dump()
    result["knowledge_docs"] = [d["title"] for d in docs]
    meta.update(source="local", note="")
    return result, meta