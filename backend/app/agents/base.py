import json
import os
import re

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tables import PromptVersion

HARD_RULES = """You are one agent in an autonomous SDR system. Follow these rules without exception:
- Use only facts given in the input. Never invent facts, names, numbers, customers or product capabilities.
- Never guess or construct email addresses. Never use personal contact details.
- If information is missing, list it in missing_information and lower your confidence.
- Reply with one JSON object and nothing else."""


def build_system(db: Session, campaign_id: str, agent_key: str, role: str) -> str:
    """Hard rules, then the campaign's ACTIVE system prompt and agent prompt from the prompt manager."""
    rows = db.scalars(
        select(PromptVersion).where(
            PromptVersion.campaign_id == campaign_id,
            PromptVersion.is_active.is_(True),
            PromptVersion.agent_key.in_(["system", agent_key]),
        )
    ).all()
    texts = {r.agent_key: r.content for r in rows}
    parts = [HARD_RULES, "Your role: " + role]
    if texts.get("system"):
        parts.append("Campaign instructions:\n" + texts["system"])
    if texts.get(agent_key):
        parts.append("Agent instructions:\n" + texts[agent_key])
    return "\n\n".join(parts)


def provider(env_name: str) -> str:
    return os.getenv(env_name, "local").strip().lower()


def empty_meta(source: str, note: str = "") -> dict:
    return {"source": source, "model": "", "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "note": note}


def call_dronahq(prefix: str, payload: dict) -> dict:
    url = os.getenv(f"DRONAHQ_{prefix}_URL", "").strip()
    key = os.getenv(f"DRONAHQ_{prefix}_KEY", "").strip()
    if not url or not key:
        raise RuntimeError("DronaHQ URL or key is not configured")
    header = os.getenv("DRONAHQ_AUTH_HEADER", "Authorization")
    prefix_txt = os.getenv("DRONAHQ_AUTH_PREFIX", "Bearer ")
    r = httpx.post(url, json=payload, headers={header: f"{prefix_txt}{key}"}, timeout=45)
    r.raise_for_status()
    data = r.json()
    for k in ("output", "data", "result", "response"):
        if isinstance(data, dict) and k in data and isinstance(data[k], (dict, str)):
            data = data[k]
            break
    if isinstance(data, str):
        data = json.loads(re.sub(r"\s*```$", "", re.sub(r"^```(?:json)?\s*", "", data.strip())))
    if not isinstance(data, dict):
        raise ValueError("Unexpected DronaHQ response shape")
    return data