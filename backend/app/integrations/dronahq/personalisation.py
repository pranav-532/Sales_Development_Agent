from typing import Any

from app.agents.schemas import MessageOut
from app.integrations.dronahq.client import call_webhook
from app.models.tables import Campaign, CampaignProspect


def _normalize_personalisation_data(data: dict[str, Any]) -> dict[str, Any]:
    """Normalizes field aliases from DronaHQ into the shape expected by MessageOut."""
    norm = dict(data)
    if "email_subject" in norm and "subject" not in norm:
        norm["subject"] = norm["email_subject"]
    if "email_body" in norm and "body" not in norm:
        norm["body"] = norm["email_body"]
    if "call_to_action" in norm and "cta" not in norm:
        norm["cta"] = norm["call_to_action"]
    if "personalizationPoints" in norm and "personalization_points" not in norm:
        norm["personalization_points"] = norm["personalizationPoints"]
    if "knowledge_sources" in norm and "knowledge_sources_used" not in norm:
        norm["knowledge_sources_used"] = norm["knowledge_sources"]
    if "knowledgeSourcesUsed" in norm and "knowledge_sources_used" not in norm:
        norm["knowledge_sources_used"] = norm["knowledgeSourcesUsed"]
    if "requiresHumanReview" in norm and "requires_human_review" not in norm:
        norm["requires_human_review"] = norm["requiresHumanReview"]
    return norm


def run_personalisation(
    c: Campaign,
    p: CampaignProspect,
    docs: list[dict],
    channel: str,
    cta: str,
) -> MessageOut:
    """Executes message personalisation via DronaHQ webhook and normalizes to MessageOut schema."""
    cfg = c.pipeline_config or {}
    payload = {
        "prospect": {
            "name": p.name or "",
            "job_title": p.title or "",
            "company": p.company or "",
        },
        "research": {
            "company_summary": (p.research or {}).get("company_summary"),
            "professional_context": (p.research or {}).get("professional_context"),
            "signals": (p.research or {}).get("signals", []),
            "confidence": (p.research or {}).get("confidence"),
        },
        "pain_points": (p.icp or {}).get("pain_points", []),
        "strategy": {
            "channel": channel,
            "reasoning": (p.strategy or {}).get("reasoning"),
        },
        "knowledge": [{"title": d["title"], "content": d["content"]} for d in docs],
        "campaign": {
            "objective": cfg.get("objective", ""),
            "tone": cfg.get("tone", ""),
            "cta": cta,
        },
        "sender_name": c.owner or "",
    }

    raw_response = call_webhook("PERSONALISATION", payload, campaign_id=c.id, prospect_id=p.id)
    normalized = _normalize_personalisation_data(raw_response)
    return MessageOut.model_validate(normalized)
