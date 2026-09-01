"""List Bolna Voice AI agents for the dashboard agent picker."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import httpx

from ..core.config import settings

logger = logging.getLogger(__name__)


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


async def list_bolna_agents() -> List[Dict[str, str]]:
    """Fetch agents from Bolna. Always includes the env default agent if configured."""
    agents: List[Dict[str, str]] = []
    seen: set[str] = set()

    if settings.bolna_enabled:
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
            if not item or item["id"] in seen:
                continue
            seen.add(item["id"])
            agents.append(item)

    default_id = (settings.BOLNA_AGENT_ID or "").strip()
    if default_id and default_id not in seen:
        agents.insert(
            0,
            {
                "id": default_id,
                "name": "Default Bolna agent",
                "status": "processed",
                "provider": "bolna",
            },
        )

    return agents
