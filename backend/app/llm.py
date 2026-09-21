import json
import os
import re
import threading
import time

import httpx
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.tables import GlobalState

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "qwen/qwen3.8-27b"  # the model the team verified on Groq

# Approximate USD per 1M tokens (input, output). Only used for the cost display, so edit to match Groq's price list.
PRICES = {"flash-lite": (0.10, 0.40), "flash": (0.30, 2.50), "pro": (1.25, 10.00)}


class LLMError(Exception):
    pass


def _models() -> dict[str, str]:
    """One model for everything by default (GROQ_MODEL). GROQ_MODEL_LITE / _FLASH / _PRO can override a tier."""
    base = os.getenv("GROQ_MODEL", "").strip() or DEFAULT_MODEL
    return {
        "flash-lite": os.getenv("GROQ_MODEL_LITE", "").strip() or base,
        "flash": os.getenv("GROQ_MODEL_FLASH", "").strip() or base,
        "pro": os.getenv("GROQ_MODEL_PRO", "").strip() or base,
    }


def model_for(db: Session, task: str) -> tuple[str, str]:
    """Reads the routing table from Settings, so the Settings page controls which tier runs."""
    tier = "flash"
    row = db.get(GlobalState, "settings")
    if row:
        for r in row.value.get("routing", []):
            if r.get("task") == task:
                tier = r.get("modelId", "flash")
    models = _models()
    if tier not in models:
        tier = "flash"
    return models[tier], tier


def _load_keys() -> list[str]:
    """GROQ_API_KEYS=a,b,c and also GROQ_API_KEY_1=a, GROQ_API_KEY_2=b (the prototype's style) both work."""
    keys = [k.strip() for k in os.getenv("GROQ_API_KEYS", "").split(",") if k.strip()]
    for i in range(1, 21):
        v = os.getenv(f"GROQ_API_KEY_{i}", "").strip()
        if v and v not in keys:
            keys.append(v)
    return keys


class KeyPool:
    def __init__(self) -> None:
        rpm = float(os.getenv("GROQ_KEY_RPM", "30"))
        self.gap = 60.0 / max(rpm, 1.0)
        self.slots = [{"key": k, "next_ok": 0.0} for k in _load_keys()]
        self.lock = threading.Lock()
        self.cursor = 0

    def acquire(self, timeout: float = 120.0) -> dict:
        if not self.slots:
            raise LLMError("No Groq keys configured. Set GROQ_API_KEYS in backend/.env")
        deadline = time.time() + timeout
        while True:
            with self.lock:
                now = time.time()
                n = len(self.slots)
                for i in range(n):
                    slot = self.slots[(self.cursor + i) % n]
                    if slot["next_ok"] <= now:
                        slot["next_ok"] = now + self.gap
                        self.cursor = (self.cursor + i + 1) % n
                        return slot
                wait = max(0.05, min(s["next_ok"] for s in self.slots) - now)
            if time.time() + wait > deadline:
                raise LLMError("All Groq keys are busy or rate limited")
            time.sleep(min(wait, 2.0))

    def cool(self, slot: dict, seconds: float = 60.0) -> None:
        with self.lock:
            slot["next_ok"] = max(slot["next_ok"], time.time() + seconds)


_pool: KeyPool | None = None
_pool_lock = threading.Lock()


def get_pool() -> KeyPool:
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = KeyPool()
        return _pool


def _strip(text: str) -> str:
    t = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()  # reasoning models may prepend this
    t = re.sub(r"^```(?:json)?\s*", "", t)
    return re.sub(r"\s*```$", "", t)


def generate_json(
    model: str,
    tier: str,
    system: str,
    user: str,
    schema: type[BaseModel],
    temperature: float = 0.3,
    attempts: int = 4,
) -> tuple[BaseModel, dict]:
    pool = get_pool()
    prompt = user
    tokens_in = tokens_out = 0
    last = "unknown error"

    for attempt in range(attempts):
        slot = pool.acquire()
        body = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        try:
            r = httpx.post(GROQ_URL, json=body, headers={"Authorization": f"Bearer {slot['key']}"}, timeout=60)
        except httpx.HTTPError as e:
            last = f"network error ({type(e).__name__})"
            time.sleep(1 + attempt)
            continue

        if r.status_code == 429:
            pool.cool(slot)
            last = "rate limited"
            continue
        if r.status_code >= 500:
            last = f"model service error {r.status_code}"
            time.sleep(2**attempt)
            continue
        if r.status_code == 400 and "json_validate_failed" in r.text:
            last = "model produced invalid JSON"  # Groq's JSON mode rejected it, so just try again
            continue
        if r.status_code != 200:
            raise LLMError(f"Groq rejected the request ({r.status_code}): {r.text[:160]}")

        try:
            data = r.json()
            usage = data.get("usage", {})
            tokens_in += usage.get("prompt_tokens", 0)
            tokens_out += usage.get("completion_tokens", 0)
            obj = schema.model_validate(json.loads(_strip(data["choices"][0]["message"]["content"])))
        except (KeyError, IndexError, TypeError, ValueError) as e:
            last = f"malformed model output ({type(e).__name__})"
            prompt = user + "\n\nYour previous reply was not valid JSON in the required shape. Reply with only the JSON object."
            continue

        p_in, p_out = PRICES.get(tier, PRICES["flash"])
        cost = tokens_in * p_in / 1e6 + tokens_out * p_out / 1e6
        return obj, {"model": model, "tokens_in": tokens_in, "tokens_out": tokens_out, "cost_usd": cost}

    raise LLMError(f"Model call failed after {attempts} attempts: {last}")