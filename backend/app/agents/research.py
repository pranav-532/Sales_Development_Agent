import json

from sqlalchemy.orm import Session

from app.agents.base import build_system
from app.agents.schemas import ResearchOut
from app.llm import generate_json, model_for
from app.models.tables import Campaign, CampaignProspect

ROLE = (
    "Lead Research and Enrichment Agent. Turn the provided facts into a structured prospect profile. "
    "Accuracy matters more than completeness."
)


def run(db: Session, c: Campaign, p: CampaignProspect) -> tuple[dict, dict]:
    cfg = c.pipeline_config or {}
    payload = {
        "prospect": {"name": p.name, "job_title": p.title, "company": p.company, "location": p.location},
        "facts": p.facts,
        "campaign_objective": cfg.get("objective", ""),
        "pain_points_we_care_about": cfg.get("painPoints", []),
    }
    model, tier = model_for(db, "Research summaries")
    user = (
        "Build a research profile using ONLY the facts listed under INPUT. You have no other source, so add nothing.\n"
        "Rules: never guess or construct an email address. Never invent signals, news or numbers. Never exaggerate a fact. "
        "If you are unsure, lower the confidence and say what is missing.\n"
        "signals: 2 to 5 short buying signals, each taken directly from a fact (hiring, tooling backlog, manual work, launches). "
        "If there are fewer real signals, return fewer.\n"
        'Return JSON: {"company_industry": str, "company_summary": str (max 2 sentences), '
        '"professional_context": str (1 to 2 sentences on the role and likely priorities, from the facts only), '
        '"signals": [str], "tech_stack_hints": [str], "sources_used": [str], "confidence": number 0 to 1, '
        '"missing_information": [str], "requires_human_review": bool}\n'
        "Confidence reflects how much verifiable information you had. Few facts means low confidence. "
        "Set requires_human_review=true if confidence is below 0.4.\n\n"
        "INPUT:\n" + json.dumps(payload)
    )
    out, meta = generate_json(model, tier, build_system(db, c.id, "research", ROLE), user, ResearchOut, temperature=0.2)
    result = out.model_dump()
    if p.source and p.source not in result["sources_used"]:
        result["sources_used"].append(p.source)
    result.update(
        prospect_name=p.name,
        job_title=p.title,
        company_name=p.company,
        company_domain=p.domain,
        linkedin_url=p.linkedin_url or None,
        business_email=p.email or None,  # only ever what the source provided, never guessed
    )
    meta.update(source="local", note="")
    return result, meta