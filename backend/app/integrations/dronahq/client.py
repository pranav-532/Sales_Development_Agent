import json
import logging
import os
import re
import time

import httpx

log = logging.getLogger("sdr.dronahq")


class DronaHQError(Exception):
    """Base exception for DronaHQ integration failures."""
    pass


class DronaHQConfigError(DronaHQError):
    """Raised when webhook URL or credentials are not configured."""
    pass


class DronaHQResponseError(DronaHQError):
    """Raised when DronaHQ returns an invalid or unparseable response."""
    pass


def get_config(agent_type: str) -> tuple[str, str]:
    """Resolves URL and API key from environment for the given agent type ('ICP' or 'PERSONALISATION')."""
    agent_key = agent_type.upper()
    
    # Check standard and alternative environment variable names
    url = (
        os.getenv(f"DRONA_{agent_key}_WEBHOOK_URL", "")
        or os.getenv(f"DRONAHQ_{agent_key}_URL", "")
        or os.getenv("DRONA_WEBHOOK_URL", "")
        or os.getenv("DRONAHQ_URL", "")
    ).strip()

    key = (
        os.getenv(f"DRONA_{agent_key}_API_KEY", "")
        or os.getenv(f"DRONAHQ_{agent_key}_KEY", "")
        or os.getenv("DRONAHQ_API_KEY", "")
        or os.getenv("DRONA_API_KEY", "")
    ).strip()

    return url, key


def _unwrap_response_data(data: object) -> object:
    """Unwraps nested data if response is enveloped under common keys."""
    if isinstance(data, dict):
        for k in ("output", "data", "result", "response", "message"):
            if k in data and isinstance(data[k], (dict, str, list)):
                return data[k]
    return data


def parse_dronahq_payload(content: object) -> dict:
    """Parses raw DronaHQ response content into a Python dictionary.
    Handles direct dicts, wrapped keys, and stringified JSON (including markdown code blocks).
    """
    if isinstance(content, dict):
        unwrapped = _unwrap_response_data(content)
        if isinstance(unwrapped, dict):
            return unwrapped
        if isinstance(unwrapped, str):
            content = unwrapped

    if isinstance(content, str):
        cleaned = content.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return _unwrap_response_data(parsed) if isinstance(_unwrap_response_data(parsed), dict) else parsed
        except Exception as e:
            raise DronaHQResponseError(f"Failed to parse stringified JSON from DronaHQ: {str(e)[:150]}") from e

    raise DronaHQResponseError(f"Unexpected response structure from DronaHQ: expected dict or JSON string, got {type(content).__name__}")


def call_webhook(
    agent_name: str,
    payload: dict,
    campaign_id: str = "",
    prospect_id: str = "",
    timeout: float = 45.0,
) -> dict:
    """Sends a request to the DronaHQ agent webhook and returns the parsed dictionary."""
    url, key = get_config(agent_name)
    if not url:
        raise DronaHQConfigError(f"DronaHQ webhook URL for '{agent_name}' is not configured")

    header_name = os.getenv("DRONAHQ_AUTH_HEADER", "Authorization").strip()
    prefix = os.getenv("DRONAHQ_AUTH_PREFIX", "Bearer ")
    headers = {"Content-Type": "application/json"}
    if key:
        headers[header_name] = f"{prefix}{key}"

    start_time = time.time()
    log.info("[DRONAHQ] Request started: agent=%s campaign=%s prospect=%s", agent_name, campaign_id, prospect_id)

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
    except httpx.TimeoutException as e:
        elapsed = time.time() - start_time
        log.warning("[DRONAHQ] Request timed out after %.2fs: agent=%s prospect=%s", elapsed, agent_name, prospect_id)
        raise DronaHQError(f"DronaHQ webhook call timed out ({timeout}s)") from e
    except httpx.HTTPStatusError as e:
        elapsed = time.time() - start_time
        log.warning("[DRONAHQ] HTTP error %d after %.2fs: agent=%s prospect=%s", e.response.status_code, elapsed, agent_name, prospect_id)
        raise DronaHQError(f"DronaHQ returned HTTP status {e.response.status_code}") from e
    except httpx.RequestError as e:
        elapsed = time.time() - start_time
        log.warning("[DRONAHQ] Network failure after %.2fs: agent=%s prospect=%s (%s)", elapsed, agent_name, prospect_id, type(e).__name__)
        raise DronaHQError(f"DronaHQ connection failure: {type(e).__name__}") from e

    elapsed = time.time() - start_time
    try:
        raw_json = response.json()
    except Exception as e:
        log.warning("[DRONAHQ] Invalid JSON response after %.2fs: agent=%s prospect=%s", elapsed, agent_name, prospect_id)
        raise DronaHQResponseError(f"DronaHQ returned non-JSON response: {str(e)[:100]}") from e

    parsed_result = parse_dronahq_payload(raw_json)
    log.info("[DRONAHQ] Request completed in %.2fs: agent=%s campaign=%s prospect=%s", elapsed, agent_name, campaign_id, prospect_id)
    return parsed_result
