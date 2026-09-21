import json
import logging

from sqlalchemy.orm import Session

from app.agents.base import build_system, empty_meta, provider
from app.agents.schemas import IcpOut
from app.integrations.dronahq import run_icp
from app.integrations.dronahq.client import get_config
from app.llm import generate_json, model_for
from app.models.tables import Campaign, CampaignProspect

log = logging.getLogger("sdr.icp")

ROLE = (
    "ICP Fitment Agent. Decide whether the prospect fits this campaign's ideal customer profile. "
    "Do not research, write messages or choose channels."
)

# Scoring guide from the prototype, applied to whichever campaign is running.
GUIDE = (
    "Score 0 to 100 against campaign_icp (roles, industries, geography, company size, exclusions):\n"
    "- 90 to 100: perfect fit, right seniority, industry, size and geography.\n"
    "- 70 to 89: strong fit, one factor is slightly off.\n"
    "- 50 to 69: weak fit, for example a junior role or a poor industry match.\n"
    "- below 50: reject, for example a wrong function (HR, marketing) or a clear geography or size mismatch.\n"
    "qualified is true only when the score is 60 or more AND geography and role match the campaign. "
    "A wrong country or an excluded company is never qualified, whatever the score. "
    "Infer likely pain points from the role and company type, and list them in pain_points. "
    "If company size or another key field is missing, list it in missing_information and set requires_human_review=true."
)


def run(db: Session, c: Campaign, p: CampaignProspect) -> tuple[IcpOut, dict]:
    cfg = c.pipeline_config or {}
    payload = {
        "campaign_icp": {
            "roles": c.target_roles,
            "industries": cfg.get("industries") or [c.icp],
            "geography": c.geography,
            "company_size": {"min": cfg.get("companySizeMin"), "max": cfg.get("companySizeMax")},
            "pain_points": cfg.get("painPoints", []),
            "company_criteria": c.company_criteria,
            "exclusions": c.exclusions,
        },
        "prospect": {
            "name": p.name,
            "job_title": p.title,
            "company": p.company,
            "industry": p.industry,
            "location": p.location,
            "company_size": p.company_size,
        },
    }

    note = ""
    drona_url, _ = get_config("ICP")
    use_drona = provider("ICP_PROVIDER") == "dronahq" or (drona_url and provider("ICP_PROVIDER") != "local")
    if use_drona:
        try:
            out = run_icp(c, p)
            return out, empty_meta("dronahq")
        except Exception as e:  # any failure falls back, the demo must not stall
            note = f"DronaHQ failed ({type(e).__name__}), used the local agent"
            log.warning("[ICP] %s: %s", p.id, note)

    model, tier = model_for(db, "ICP fitment scoring")
    user = (
        GUIDE + "\n"
        'Return JSON: {"qualified": bool, "score": int, "reasons": [str], "pain_points": [str], '
        '"missing_information": [str], "requires_human_review": bool}\n\n'
        "INPUT:\n" + json.dumps(payload)
    )
    out, meta = generate_json(model, tier, build_system(db, c.id, "icp_fitment", ROLE), user, IcpOut, temperature=0.1)
    meta.update(source="local", note=note)
    return out, meta