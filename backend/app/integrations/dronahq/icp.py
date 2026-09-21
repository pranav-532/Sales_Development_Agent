from typing import Any

from app.agents.schemas import IcpOut
from app.integrations.dronahq.client import call_webhook
from app.models.tables import Campaign, CampaignProspect


def _normalize_icp_data(data: dict[str, Any]) -> dict[str, Any]:
    """Normalizes field aliases from DronaHQ into the shape expected by IcpOut."""
    norm = dict(data)
    if "is_qualified" in norm and "qualified" not in norm:
        norm["qualified"] = norm["is_qualified"]
    if "fit_score" in norm and "score" not in norm:
        norm["score"] = norm["fit_score"]
    if "painPoints" in norm and "pain_points" not in norm:
        norm["pain_points"] = norm["painPoints"]
    if "missingInformation" in norm and "missing_information" not in norm:
        norm["missing_information"] = norm["missingInformation"]
    if "requiresHumanReview" in norm and "requires_human_review" not in norm:
        norm["requires_human_review"] = norm["requiresHumanReview"]
    return norm


def run_icp(c: Campaign, p: CampaignProspect) -> IcpOut:
    """Executes ICP Fitment scoring via DronaHQ webhook and normalizes to IcpOut schema."""
    cfg = c.pipeline_config or {}
    payload = {
        "campaign_icp": {
            "roles": c.target_roles or [],
            "industries": cfg.get("industries") or [c.icp],
            "geography": c.geography or "",
            "company_size": {"min": cfg.get("companySizeMin"), "max": cfg.get("companySizeMax")},
            "pain_points": cfg.get("painPoints", []),
            "company_criteria": c.company_criteria or "",
            "exclusions": c.exclusions or "",
        },
        "prospect": {
            "name": p.name or "",
            "job_title": p.title or "",
            "company": p.company or "",
            "industry": p.industry or "",
            "location": p.location or "",
            "company_size": p.company_size,
        },
    }

    raw_response = call_webhook("ICP", payload, campaign_id=c.id, prospect_id=p.id)
    normalized = _normalize_icp_data(raw_response)
    return IcpOut.model_validate(normalized)
