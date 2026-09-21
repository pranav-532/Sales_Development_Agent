import json

from sqlalchemy.orm import Session

from app.agents.base import build_system
from app.agents.schemas import VoiceDecisionOut, VoiceSummaryOut, VoiceTurnOut
from app.llm import generate_json, model_for
from app.models.tables import Campaign, CampaignProspect
from app.rag import retrieve

ROLE = (
    "Voice SDR Agent. You hold a short, polite spoken conversation with a prospect. "
    "Speak in one or two short sentences at a time, the way a person talks on the phone."
)
TASK = "Voice conversations"

RULES = (
    "Rules: say plainly in your first sentence that you are an AI assistant calling for {owner}'s team. "
    "Never quote prices or discounts. Never promise anything not in the knowledge. "
    "If the prospect asks for a person, set transfer_to_human=true and say a colleague will call back. "
    "If they are not interested, thank them and end the call. "
    "You are already on a call, so if they are interested ask for a short meeting, never for another call. "
    "Do not accept a specific time and do not promise a calendar invite, because you cannot see anyone's calendar: "
    "say a colleague will confirm the time."
)


def _context(db: Session, c: Campaign, p: CampaignProspect, query: str) -> dict:
    cfg = c.pipeline_config or {}
    docs = retrieve(db, c.id, query, k=3)
    return {
        "prospect": {"name": p.name, "job_title": p.title, "company": p.company},
        "research": {
            "company_summary": (p.research or {}).get("company_summary"),
            "professional_context": (p.research or {}).get("professional_context"),
        },
        "knowledge": [{"title": d["title"], "content": d["content"]} for d in docs],
        "campaign": {"objective": cfg.get("objective", ""), "tone": cfg.get("tone", "")},
    }


def decide(db: Session, c: Campaign, p: CampaignProspect, reason: str) -> tuple[dict, dict]:
    ctx = _context(db, c, p, f"{reason} voice call script")
    ctx["why_we_are_calling"] = reason
    user = (
        "Prepare the opening of a call. " + RULES.format(owner=c.owner) + " "
        "opening_script: 2 to 3 sentences, mention the prospect's company by name, name our product once (take the name from knowledge), "
        "give one reason for the call taken from the input, "        "and ask if now is a good time. talking_points: up to 3 short points to use if the conversation continues.\n"
        'Return JSON: {"should_call": bool, "opening_script": str, "talking_points": [str], "reasoning": str}\n\n'
        "INPUT:\n" + json.dumps(ctx)
    )
    model, tier = model_for(db, TASK)
    out, meta = generate_json(model, tier, build_system(db, c.id, "voice", ROLE), user, VoiceDecisionOut, temperature=0.4)
    meta.update(source="local")
    return out.model_dump(), meta


def turn(db: Session, c: Campaign, p: CampaignProspect, turns: list[dict], latest: str) -> tuple[dict, dict]:
    ctx = _context(db, c, p, latest)
    ctx["call_so_far"] = turns[-12:]
    ctx["prospect_just_said"] = latest
    user = (
        "Continue the call. " + RULES.format(owner=c.owner) + " "
        "say: what you say next, at most 40 words. Set end_call=true when the call is naturally over. "
        "outcome: continuing, meeting_agreed, callback_requested, not_interested or needs_human.\n"
        'Return JSON: {"say": str, "end_call": bool, "transfer_to_human": bool, "outcome": str}\n\n'
        "INPUT:\n" + json.dumps(ctx)
    )
    model, tier = model_for(db, TASK)
    out, meta = generate_json(model, tier, build_system(db, c.id, "voice", ROLE), user, VoiceTurnOut, temperature=0.4)
    meta.update(source="local")
    return out.model_dump(), meta


def summarise(db: Session, c: Campaign, p: CampaignProspect, turns: list[dict]) -> tuple[dict, dict]:
    user = (
        "The call has ended. Summarise it for the sales team using only what was said.\n"
        "outcome: meeting_agreed only if the prospect clearly agreed to a meeting; callback_requested if they asked to "
        "be called or contacted later; not_interested; needs_human if they asked for a person or raised something we cannot answer; "
        "otherwise continuing.\n"
        'Return JSON: {"outcome": str, "summary": str (max 2 sentences), "next_step": str, "requires_human_review": bool}\n\n'
        "TRANSCRIPT:\n" + json.dumps(turns)
    )
    model, tier = model_for(db, TASK)
    out, meta = generate_json(model, tier, build_system(db, c.id, "voice", ROLE), user, VoiceSummaryOut, temperature=0.1)
    meta.update(source="local")
    return out.model_dump(), meta