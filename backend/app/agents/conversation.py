import json

from sqlalchemy.orm import Session

from app.agents.base import build_system
from app.agents.personalisation import _flags
from app.agents.schemas import ConversationOut
from app.llm import generate_json, model_for
from app.models.tables import Campaign, CampaignProspect
from app.rag import retrieve

ROLE = (
    "Conversation Agent. Read the prospect's latest reply in the context of the whole conversation, "
    "work out what they want and, when a reply is needed, draft it. You never send anything yourself."
)

TOPICS = "pricing, contract, security, legal, compliance, integration, competitor, timing, human_request, other"


def run(db: Session, c: Campaign, p: CampaignProspect, history: list[dict], latest: str) -> tuple[dict, dict]:
    cfg = c.pipeline_config or {}
    docs = retrieve(db, c.id, f"{latest} {cfg.get('objective', '')} objection pricing security", k=3)
    payload = {
        "prospect": {"name": p.name, "job_title": p.title, "company": p.company},
        "conversation_so_far": history,
        "latest_reply": latest,
        "knowledge": [{"title": d["title"], "content": d["content"]} for d in docs],
        "campaign": {"objective": cfg.get("objective", ""), "tone": cfg.get("tone", ""), "cta": cfg.get("cta", "")},
        "sender_name": c.owner,
    }
    user = (
        "Classify the latest reply.\n"
        "intent is exactly one of: interested, wants_meeting, wants_call, asking_question, objection, "
        "not_interested, unsubscribe, out_of_office, not_now, unclear.\n"
        "- wants_meeting: they propose or accept a time to talk. wants_call: they ask for a phone call.\n"
        "- not_now: come back later. out_of_office: an automatic away message.\n"
        "- unsubscribe: they ask to stop or be removed. Anything hostile counts as unsubscribe.\n"
        "- When unsure, choose objection over interested. Never mark interested on a polite brush-off.\n"
        f"topics: zero or more of: {TOPICS}. Use human_request if they ask to speak to a person.\n"
        "response_required is true when a reply from us would help. If it is true, write reply_draft: under 90 words, "
        "in the campaign tone, signed with sender_name. Use only facts from knowledge. "
        "If they propose a time, thank them and say you will confirm a time shortly. Do not accept a time yourself "
        "and do not promise a calendar invite, because you cannot see anyone's calendar. "        "Never quote prices, discounts or dates you were not given. "
        "If they asked about pricing or a contract, set requires_human_review=true and leave reply_draft empty.\n"
        'Return JSON: {"intent": str, "sentiment": "positive"|"neutral"|"negative", "summary": str (one sentence), '
        '"topics": [str], "response_required": bool, "reply_draft": str, "requires_human_review": bool, '
        '"confidence": number 0 to 1}\n\nINPUT:\n' + json.dumps(payload)
    )
    model, tier = model_for(db, "Reply classification")
    out, meta = generate_json(model, tier, build_system(db, c.id, "conversation", ROLE), user, ConversationOut, temperature=0.2)

    result = out.model_dump()
    sources = json.dumps(payload["knowledge"]) + " " + json.dumps(history) + " " + latest
    result["flags"] = _flags(result["reply_draft"], sources) if result["reply_draft"] else []
    result["knowledge_docs"] = [d["title"] for d in docs]
    meta.update(source="local")
    return result, meta