"""List Bolna Voice AI agents for the dashboard agent picker."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import httpx

from ..core.config import settings

logger = logging.getLogger(__name__)

# Explicit allowlist. Outbound still uses BOLNA_FROM_PHONE for every agent.
VISIBLE_AGENTS: List[Dict[str, str]] = [
    {
        "id": "2459701f-ef45-458e-9301-ef1e44d3f36a",
        "name": "Hindu- Pre Event",
    },
    {
        "id": "663b03aa-0f2a-475e-8db5-e5faeccc3e84",
        "name": "Hindu On Day Version 3.0",
    },
]


def allowed_agent_ids() -> List[str]:
    ids = [str(a.get("id") or "").strip() for a in VISIBLE_AGENTS]
    default = (settings.BOLNA_AGENT_ID or "").strip()
    if default and default not in ids:
        ids.insert(0, default)
    return [i for i in ids if i]


def is_allowed_agent_id(agent_id: str) -> bool:
    return bool((agent_id or "").strip()) and (agent_id or "").strip() in set(allowed_agent_ids())


def display_name_for_agent(agent_id: str) -> str:
    aid = (agent_id or "").strip()
    for item in VISIBLE_AGENTS:
        if item.get("id") == aid:
            return str(item.get("name") or aid)
    return aid


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


def _catalog_row(agent_id: str, status: str = "processed") -> Dict[str, str]:
    return {
        "id": agent_id,
        "name": display_name_for_agent(agent_id),
        "status": status,
        "provider": "bolna",
    }


async def list_bolna_agents() -> List[Dict[str, str]]:
    """Return the Hindu calling agents enabled for this workspace."""
    catalog_ids = allowed_agent_ids()
    if not catalog_ids:
        return []
    fallback = [_catalog_row(aid) for aid in catalog_ids]
    if not settings.bolna_enabled:
        return fallback

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
        return fallback

    rows: List[Any] = []
    if isinstance(body, list):
        rows = body
    elif isinstance(body, dict):
        for key in ("agents", "data", "items"):
            if isinstance(body.get(key), list):
                rows = body[key]
                break

    by_id: Dict[str, Dict[str, str]] = {}
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        item = _normalize_agent(raw)
        if item:
            by_id[item["id"]] = item

    result: List[Dict[str, str]] = []
    for agent_id in catalog_ids:
        match = by_id.get(agent_id)
        if match:
            match["name"] = display_name_for_agent(agent_id)
            result.append(match)
        else:
            result.append(_catalog_row(agent_id))
    return result
