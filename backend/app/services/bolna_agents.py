"""List Bolna Voice AI agents for the dashboard agent picker."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import httpx

from ..core.config import settings

logger = logging.getLogger(__name__)

# Only this agent is shown in pickers until more are explicitly enabled.
VISIBLE_AGENT_DISPLAY_NAME = "Hindu- Pre Event"


def _normalize_agent(raw: Dict[str, Any]) -> Dict[str, str] | None:
    agent_id = str(raw.get("id") or raw.get("agent_id") or "").strip()
    if not agent_id:
        return None
    name = str(raw.get("agent_name") or raw.get("name") or "").strip() or "Unnamed agent"
    status = str(raw.get("agent_status") or raw.get("status") or "").strip()
    return {
        "id": agent_id,
        "name": name,
        "status": status,
        "provider": "bolna",
    }


def _visible_agent_id() -> str:
    return (settings.BOLNA_AGENT_ID or "").strip()


def _hindu_agent(agent_id: str, status: str = "processed") -> Dict[str, str]:
    return {
        "id": agent_id,
        "name": VISIBLE_AGENT_DISPLAY_NAME,
        "status": status,
        "provider": "bolna",
    }


async def list_bolna_agents() -> List[Dict[str, str]]:
    """Return the single Hindu calling agent for dashboard pickers."""
    visible_id = _visible_agent_id()
    if not visible_id:
        return []
    if not settings.bolna_enabled:
        return [_hindu_agent(visible_id)]

    match: Dict[str, str] | None = None
    url = f"{settings.BOLNA_BASE_URL.rstrip('/')}/v2/agent/all"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {settings.BOLNA_API_KEY}",
                    "Accept": "application/json",
                },
            )
            response.raise_for_status()
            body = response.json()
    except Exception:
        logger.exception("Failed to list Bolna agents")
        body = None

    rows: List[Any] = []
    if isinstance(body, list):
        rows = body
    elif isinstance(body, dict):
        for key in ("agents", "data", "items"):
            if isinstance(body.get(key), list):
                rows = body[key]
                break

    for raw in rows:
        if not isinstance(raw, dict):
            continue
        item = _normalize_agent(raw)
        if item and item["id"] == visible_id:
            match = item
            break

    if match:
        match["name"] = VISIBLE_AGENT_DISPLAY_NAME
        return [match]
    return [_hindu_agent(visible_id)]
