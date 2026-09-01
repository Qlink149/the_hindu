"""Bolna Voice AI outbound call push (POST https://api.bolna.ai/call)."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

import httpx

from ..core.config import settings
from ..core.time_utils import utc_now
from ..utils.webhook_lead import is_placeholder_customer_name

logger = logging.getLogger(__name__)


def ten_digit_phone(lead: Dict[str, Any]) -> str:
    raw_phone = (
        lead.get("recipientPhoneNumber")
        or lead.get("mobile_digits")
        or lead.get("mobile", "")
    )
    phone = "".join(c for c in str(raw_phone) if c.isdigit())[-10:]
    if len(phone) == 10:
        return phone
    db_digits = "".join(c for c in str(lead.get("mobile_digits") or "") if c.isdigit())[-10:]
    return db_digits if len(db_digits) == 10 else ""


def e164_phone(lead: Dict[str, Any]) -> str:
    """Bolna requires E.164. Indian 10-digit numbers are prefixed with +91."""
    digits = "".join(
        c
        for c in str(
            lead.get("recipientPhoneNumber")
            or lead.get("mobile")
            or lead.get("mobile_digits")
            or ""
        )
        if c.isdigit()
    )
    if digits.startswith("91") and len(digits) == 12:
        return f"+{digits}"
    if len(digits) == 10:
        return f"+91{digits}"
    if digits:
        return f"+{digits}"
    ten = ten_digit_phone(lead)
    return f"+91{ten}" if ten else ""


def display_name_for_lead(lead: Dict[str, Any]) -> str:
    name = (
        (lead.get("full_name") or "").strip()
        or (lead.get("customer_name") or "").strip()
    )
    if name and not is_placeholder_customer_name(name):
        return name
    combined = " ".join(
        p
        for p in (
            str(lead.get("first_name") or "").strip(),
            str(lead.get("last_name") or "").strip(),
        )
        if p
    )
    if combined and not is_placeholder_customer_name(combined):
        return combined
    return name or "Unknown"


async def record_outbound_call_placeholder(
    db,
    lead: Dict[str, Any],
    *,
    execution_id: str,
    agent_id: str = "",
    campaign_id: Optional[str] = None,
) -> None:
    """Insert a call_history row as soon as Bolna accepts the dial so the UI is live."""
    eid = str(execution_id or "").strip()
    if not eid or db is None:
        return
    phone10 = ten_digit_phone(lead)
    name = display_name_for_lead(lead)
    now = utc_now()
    insert_doc: Dict[str, Any] = {
        "id": eid,
        "call_sid": eid,
        "lead_id": str(lead.get("id") or ""),
        "customer_name": name,
        "phone": e164_phone(lead) or str(lead.get("mobile") or phone10),
        "mobile_digits": phone10,
        "status": "queued",
        "disposition": "",
        "duration": 0,
        "agent_id": agent_id or "",
        "campaign_id": campaign_id or "",
        "upload_batch_id": str(lead.get("upload_batch_id") or ""),
        "upload_batch_name": str(lead.get("upload_batch_name") or ""),
        "direction": "outbound",
        "hangup_by": "bot",
        "created_at": now,
        "updated_at": now,
    }
    try:
        await db.call_history.update_one(
            {"id": eid},
            {"$setOnInsert": insert_doc, "$set": {"updated_at": now}},
            upsert=True,
        )
    except Exception:
        logger.exception("Failed to record outbound call placeholder | execution_id=%s", eid)


def bolna_user_data(lead: Dict[str, Any], customer_name: str) -> Dict[str, str]:
    data: Dict[str, str] = {"customer_name": customer_name}
    lead_id = str(lead.get("id") or "").strip()
    if lead_id:
        data["lead_id"] = lead_id
        data["unique_identifier"] = lead_id
    project = str(lead.get("project") or "").strip()
    if project:
        data["project"] = project
    batch_id = str(lead.get("upload_batch_id") or "").strip()
    if batch_id:
        data["upload_batch_id"] = batch_id
    batch_name = str(lead.get("upload_batch_name") or "").strip()
    if batch_name:
        data["upload_batch_name"] = batch_name
    return data


def extract_bolna_execution_id(body: Any) -> str:
    if not isinstance(body, dict):
        return ""
    for key in ("execution_id", "id", "call_id"):
        val = body.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    for wrapper in ("data", "result"):
        inner = body.get(wrapper)
        if isinstance(inner, dict):
            eid = extract_bolna_execution_id(inner)
            if eid:
                return eid
    return ""


def bolna_call_endpoint() -> str:
    base = (settings.BOLNA_BASE_URL or "https://api.bolna.ai").rstrip("/")
    return f"{base}/call"


def bolna_request_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.BOLNA_API_KEY}",
        "Content-Type": "application/json",
    }


async def resolve_outbound_agent_id(db, *, campaign_id: Optional[str] = None) -> str:
    """Prefer the agent saved on the campaign, else the env default."""
    if campaign_id:
        doc = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0, "agent_id": 1})
        saved = str((doc or {}).get("agent_id") or "").strip()
        if saved:
            return saved
    fid = (settings.calling_campaign_id or "").strip()
    if fid:
        doc = await db.campaigns.find_one(
            {"$or": [{"futwork_campaign_id": fid}, {"id": fid}]},
            {"_id": 0, "agent_id": 1},
        )
        saved = str((doc or {}).get("agent_id") or "").strip()
        if saved:
            return saved
    return (settings.BOLNA_AGENT_ID or "").strip()


async def post_one_lead_to_bolna(
    http_client: httpx.AsyncClient,
    db,
    lead: Dict[str, Any],
    *,
    campaign_id: Optional[str] = None,
    agent_id: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """
    POST one outbound call to Bolna and persist sync status on the lead.

    Returns (success, execution_id or None).
    """
    from .lead_service import LeadService

    ls = LeadService(db)
    phone10 = ten_digit_phone(lead)
    recipient = e164_phone(lead)
    if len(phone10) != 10 or not recipient:
        logger.warning(
            "Skipping lead: invalid phone for Bolna dial | mobile_digits=%s",
            lead.get("mobile_digits"),
        )
        return False, None

    name = display_name_for_lead(lead)
    resolved_agent = (agent_id or "").strip() or await resolve_outbound_agent_id(
        db, campaign_id=campaign_id
    )
    if not resolved_agent:
        logger.warning("Skipping lead: no Bolna agent_id configured")
        return False, None
    payload: Dict[str, Any] = {
        "agent_id": resolved_agent,
        "recipient_phone_number": recipient,
        "user_data": bolna_user_data(lead, name),
    }
    from_number = (settings.BOLNA_FROM_PHONE or "").strip()
    if from_number:
        payload["from_phone_number"] = from_number

    endpoint = bolna_call_endpoint()
    headers = bolna_request_headers()

    try:
        logger.info("BOLNA PUSH REQUEST | URL: %s | Payload: %s", endpoint, payload)
        response = await http_client.post(endpoint, json=payload, headers=headers)
        logger.info(
            "BOLNA PUSH RESPONSE | Status: %s | Body: %s",
            response.status_code,
            response.text,
        )
        response.raise_for_status()
        try:
            body = response.json()
        except Exception:
            body = None
        execution_id = extract_bolna_execution_id(body)
        await ls.apply_lead_futwork_sync(
            mobile_digits=phone10,
            status="pushed",
            futwork_lead_id=execution_id or None,
            campaign_id=campaign_id,
        )
        if execution_id:
            await record_outbound_call_placeholder(
                db,
                lead,
                execution_id=execution_id,
                agent_id=resolved_agent,
                campaign_id=campaign_id,
            )
        return True, execution_id or None
    except httpx.HTTPStatusError as e:
        logger.error(
            "Failed to push lead %s to Bolna | HTTPStatusError: %s | Response Body: %s",
            phone10,
            e,
            e.response.text if e.response else "",
            exc_info=True,
        )
        await ls.apply_lead_futwork_sync(
            mobile_digits=phone10,
            status="failed",
            campaign_id=campaign_id,
        )
        return False, None
    except Exception as e:
        logger.error("Failed to push lead %s to Bolna: %s", phone10, e, exc_info=True)
        await ls.apply_lead_futwork_sync(
            mobile_digits=phone10,
            status="failed",
            campaign_id=campaign_id,
        )
        return False, None
