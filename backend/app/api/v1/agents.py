"""Calling agents available for outbound Bolna dials."""

from typing import Any, Dict, List

from fastapi import APIRouter

from ...core.config import settings
from ...services.bolna_agents import list_bolna_agents

router = APIRouter()


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]], include_in_schema=False)
async def list_agents():
    """Bolna agents on this account, for the dashboard / campaign / calling pickers."""
    if not settings.calling_engine_ready:
        return []
    return await list_bolna_agents()
