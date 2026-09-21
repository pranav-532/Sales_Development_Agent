import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tables import GlobalState, KnowledgeDoc

STOP = {"this", "that", "with", "from", "have", "will", "your", "their", "about", "into", "they", "them", "been", "were", "also", "than", "then", "when", "what"}


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 3 and w not in STOP}


def retrieve(db: Session, campaign_id: str, query: str, k: int = 4) -> list[dict]:
    settings = db.get(GlobalState, "settings")
    enabled = (
        {kb["id"] for kb in settings.value.get("knowledge", []) if kb.get("enabled")} if settings else None
    )
    terms = _words(query)
    scored = []
    for d in db.scalars(select(KnowledgeDoc)).all():
        if enabled is not None and d.kb not in enabled:
            continue
        if "*" not in d.audience and campaign_id not in d.audience:
            continue
        score = len(terms & _words(d.title)) * 3 + len(terms & _words(d.content))
        if campaign_id in d.audience:
            score += 2
        if d.title.lower().startswith("approved claims"):
            score += 100  # the claims list is always in context
        scored.append((score, d))
    scored.sort(key=lambda x: -x[0])
    picked = [x for x in scored if x[0] > 0][:k] or scored[:2]
    return [{"title": d.title, "kb": d.kb, "content": d.content} for _, d in picked]