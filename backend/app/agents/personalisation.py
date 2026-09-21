import json
import logging
import re

from sqlalchemy.orm import Session

from app.agents.base import build_system, empty_meta, provider
from app.agents.schemas import MessageOut
from app.integrations.dronahq import run_personalisation
from app.integrations.dronahq.client import get_config
from app.llm import generate_json, model_for
from app.models.tables import Campaign, CampaignProspect
from app.rag import retrieve

log = logging.getLogger("sdr.personalisation")

ROLE = (
    "Personalisation Agent. Write one short, specific first-touch message using only the research and "
    "approved knowledge provided."
)
RISKY = ("guarantee", "soc 2", "soc2", "iso 27001", "100%")

# Email rules from the prototype, with the two things that went wrong in its saved output fixed:
# no placeholders, and no social proof or numbers unless they are in the knowledge.
RULES = (
    "Writing rules:\n"
    "1. Open with one specific fact about them or their company taken from research. Never open with 'I hope this finds you well'.\n"
    "2. Connect their situation to the product in 1 or 2 sentences, using only capabilities listed in knowledge.\n"
    "3. Social proof is allowed ONLY if a case study appears in knowledge. Otherwise leave it out. "
    "Never invent customers, metrics, speed-up claims (like '10x') or percentages.\n"
    "4. Plain language, like a smart person writing to a colleague. No jargon.\n"
    "5. Do not write a sign-off and do not end with a question. The call to action and the sign-off are added after your body. "
    "Never write placeholders such as [Your Name] or [Company].\n"
    "6. Do not claim what teams 'often' do or assume their problems. State the fact from research, then connect it to the product.\n"
)

SIGNOFFS = {"best", "regards", "best regards", "kind regards", "warm regards", "thanks", "thank you", "cheers", "sincerely"}


def _compose(body: str, cta: str, owner: str) -> str:
    """Builds the final layout in code: body, then the call to action, then the sign-off. The model cannot break it."""
    body = body.strip()
    if cta:
        body = body.replace(cta, "").rstrip()
    lines = body.split("\n")
    while lines:  # drop any sign-off the model wrote anyway
        last = lines[-1].strip()
        low = last.lower().rstrip(",.")
        first_word = low.split(",")[0].split(" ")[0] if low else ""
        if (not last or low in SIGNOFFS or low == owner.lower() or re.fullmatch(r"\[[^\]]{2,40}\]", last)
                or (len(last) <= len(owner) + 20 and (first_word in SIGNOFFS or owner.lower() in low))):
            lines.pop()
        else:
            break
    body = "\n".join(lines).rstrip()
    return "\n\n".join(x for x in (body, cta, f"Best,\n{owner}") if x)


def _flags(text: str, sources: str) -> list[str]:
    """Deterministic hallucination guard: risky claims, numbers and placeholders are checked in code, not trusted to the model."""
    flags = []
    low, src = text.lower(), sources.lower()
    for phrase in RISKY:
        if phrase in low and phrase not in src:
            flags.append(f"Unsupported claim: '{phrase}'")
    for m in re.findall(r"\$\s?\d[\d,\.]*|\d+(?:\.\d+)?\s?%|\b\d+\s?x\b", text, flags=re.I):
        if m.replace(" ", "").lower() not in src.replace(" ", ""):
            flags.append(f"Number not found in sources: {m}")
    for m in re.findall(r"\[[^\]\n]{2,40}\]", text):
        flags.append(f"Unresolved placeholder: {m}")
    return flags


def run(db: Session, c: Campaign, p: CampaignProspect) -> tuple[dict, dict]:
    cfg = c.pipeline_config or {}
    channel = (p.strategy or {}).get("primary_channel", "email")
    query = " ".join([
        p.research.get("company_summary", ""), p.research.get("professional_context", ""),
        " ".join(p.research.get("signals", [])), cfg.get("objective", ""), " ".join(cfg.get("painPoints", [])),
    ])
    docs = retrieve(db, c.id, query, k=4)
    cta = cfg.get("cta", "")
    payload = {
        "prospect": {"name": p.name, "job_title": p.title, "company": p.company},
        "research": {
            "company_summary": p.research.get("company_summary"),
            "professional_context": p.research.get("professional_context"),
            "signals": p.research.get("signals", []),
            "confidence": p.research.get("confidence"),
        },
        "pain_points": p.icp.get("pain_points", []),
        "strategy": {"channel": channel, "reasoning": (p.strategy or {}).get("reasoning")},
        "knowledge": [{"title": d["title"], "content": d["content"]} for d in docs],
        "campaign": {"objective": cfg.get("objective", ""), "tone": cfg.get("tone", ""), "cta": cta},
        "sender_name": c.owner,
    }

    out, meta, note = None, None, ""
    drona_url, _ = get_config("PERSONALISATION")
    use_drona = provider("PERSONALISATION_PROVIDER") == "dronahq" or (drona_url and provider("PERSONALISATION_PROVIDER") != "local")
    if use_drona:
        try:
            out = run_personalisation(c, p, docs, channel, cta)
            meta = empty_meta("dronahq")
        except Exception as e:
            note = f"DronaHQ failed ({type(e).__name__}), used the local agent"
            log.warning("[PERSONALISATION] %s: %s", p.id, note)

    if out is None:
        model, tier = model_for(db, "Personalised email writing")
        length = "Under 300 characters" if channel == "linkedin" else "Body under 120 words"
        user = (
            f"Write the first message on the {channel} channel. {length}. " + RULES +
            f"Do not write the call to action yourself, it is appended after your body: {cta!r}\n"
            'Return JSON: {"subject": str, "body": str, "personalization_points": [str], "cta": str, '
            '"confidence": number 0 to 1, "knowledge_sources_used": [str], "requires_human_review": bool}\n\n'
            "INPUT:\n" + json.dumps(payload)
        )
        out, meta = generate_json(
            model, tier, build_system(db, c.id, "personalisation", ROLE), user, MessageOut, temperature=0.5
        )
        meta.update(source="local")
    meta["note"] = note

    body = _compose(out.body, cta, c.owner)
    sources = json.dumps(payload["research"]) + " " + " ".join(d["content"] for d in docs) + " " + json.dumps(payload["campaign"])
    flags = _flags(f"{out.subject} {body}", sources)
    msg = out.model_dump()
    msg.update(body=body, cta=cta or out.cta, channel=channel, flags=flags, knowledge_docs=[d["title"] for d in docs])
    return msg, meta