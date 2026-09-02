import asyncio
import csv
import io
import re
import uvicorn
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import logging

from app.core.config import settings
from app.core.database import connect_to_mongo, close_mongo_connection, initialize_db, get_db, db_instance
from app.core.time_utils import serialize_datetime_utc
from app.core.security import get_current_user
from app.api.v1 import (
    leads,
    dashboard,
    ai,
    webhooks,
    campaigns,
    projects,
    agents,
    auth,
    users,
    my_dashboard,
    analytics,
    marketing,
    notifications,
    tasks,
    virtual_customer,
)
from app.models.structured_extraction import StructuredDisposition
from app.services.campaign_service import CampaignService
from app.utils.futwork_disposition_stats import futwork_disposition_exact as _futwork_disposition_exact
from app.utils.futwork_disposition_stats import canonical_disposition_label
from app.utils.bolna_disposition import extract_bolna_disposition
from app.utils.webhook_lead import is_placeholder_customer_name

AGENT_ACTIVE_DISPOSITIONS = ["Attending", "Not Attending"]
_BATCH_LEAD_CAP = 10000
_CALL_EXPORT_CAP = 10000
_CALL_EXPORT_COLUMNS = [
    ("customer_name", "Customer"),
    ("phone", "Phone"),
    ("created_at", "Timestamp"),
    ("duration", "Duration (seconds)"),
    ("disposition", "Disposition"),
    ("status", "Status"),
    ("upload_batch_name", "Batch"),
    ("id", "Call ID"),
    ("recording_url", "Recording URL"),
]

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.PROJECT_NAME)

# CORS — allow all origins in development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_db_client():
    if settings.bolna_enabled:
        logger.info(
            "Calling engine: Bolna enabled | agent_id=%s | from_phone=%s",
            settings.BOLNA_AGENT_ID,
            settings.BOLNA_FROM_PHONE or "(account default)",
        )
    elif settings.futwork_enabled:
        logger.info("Calling engine: legacy Futwork enabled")
    else:
        logger.warning("Calling engine is not configured (set BOLNA_API_KEY + BOLNA_AGENT_ID)")

    if not settings.MONGO_URL:
        logger.error("MONGO_URL is not set — database operations will fail")
        logger.info("Backend started — The Hindu Sales Intelligence API (serverless ready)")
        return
    try:
        await connect_to_mongo()
    except Exception as e:
        logger.error("MongoDB connection failed at startup: %s", e)
        logger.info("Backend started — The Hindu Sales Intelligence API (serverless ready)")
        return
    try:
        await initialize_db()
    except Exception as e:
        # Non-fatal: indexes/seed may fail (e.g. Atlas write quota). Reads still work.
        logger.warning("Database initialization skipped (non-fatal): %s", e)
    logger.info("Backend started — The Hindu Sales Intelligence API (serverless ready)")


@app.on_event("shutdown")
async def shutdown_db_client():
    await close_mongo_connection()


@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    return {"status": "ok", "service": "hindu-sales-api"}


@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    calling = {
        "provider": "bolna" if settings.bolna_enabled else ("futwork" if settings.futwork_enabled else None),
        "configured": settings.calling_engine_ready,
        "agent_id": settings.BOLNA_AGENT_ID if settings.bolna_enabled else None,
    }
    if not settings.MONGO_URL:
        return {
            "status": "degraded",
            "database": "MONGO_URL not configured",
            "calling_engine": calling,
        }
    if db_instance.db is None:
        return {
            "status": "degraded",
            "database": "not connected",
            "calling_engine": calling,
        }
    try:
        await db_instance.db.command("ping")
        return {"status": "healthy", "database": "connected", "calling_engine": calling}
    except Exception as e:
        logger.warning("Health check DB ping failed: %s", e)
        return {"status": "degraded", "database": str(e), "calling_engine": calling}


# ── API Routers ──────────────────────────────────────────────────────────────
_auth_dep = [Depends(get_current_user)]

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(
    users.router, prefix="/api/users", tags=["Users"], dependencies=_auth_dep
)
app.include_router(
    my_dashboard.router,
    prefix="/api/my-dashboard",
    tags=["My Dashboard"],
    dependencies=_auth_dep,
)
app.include_router(
    leads.router, prefix="/api/leads", tags=["Leads"], dependencies=_auth_dep
)
app.include_router(
    virtual_customer.router,
    prefix="/api/virtual-customer",
    tags=["Virtual Customer"],
    dependencies=_auth_dep,
)
app.include_router(
    dashboard.router, prefix="/api/dashboard", tags=["Dashboard"], dependencies=_auth_dep
)
app.include_router(
    analytics.router, prefix="/api/analytics", tags=["Analytics"], dependencies=_auth_dep
)
app.include_router(
    marketing.router, prefix="/api/marketing", tags=["Marketing"], dependencies=_auth_dep
)
app.include_router(
    notifications.router,
    prefix="/api/notifications",
    tags=["Notifications"],
    dependencies=_auth_dep,
)
app.include_router(ai.router, prefix="/api", tags=["AI"], dependencies=_auth_dep)
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["Webhooks"])
app.include_router(
    campaigns.router, prefix="/api/campaigns", tags=["Campaigns"], dependencies=_auth_dep
)
app.include_router(
    projects.router, prefix="/api/projects", tags=["Projects"], dependencies=_auth_dep
)
app.include_router(
    agents.router, prefix="/api/agents", tags=["Agents"], dependencies=_auth_dep
)
app.include_router(tasks.router, prefix="/api", tags=["Tasks"], dependencies=_auth_dep)


def _and_queries(*parts: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    merged = [p for p in parts if p]
    if not merged:
        return {}
    if len(merged) == 1:
        return merged[0]
    return {"$and": merged}


_OVERCALL_SIGNAL_PHRASES = (
    "called multiple times",
    "too many calls",
    "bar bar",
)

_CRM_OVERCALL_ISSUE = (
    "Leads complaining about over-calling; reduce retries and use human callback."
)


async def _call_history_lead_id_clause(db, lead_id: str) -> Optional[Dict[str, Any]]:
    """Expand internal leads.id to call_history match (lead_id, phone, Futwork ids)."""
    lid = (lead_id or "").strip()
    if not lid:
        return None
    lead = await db.leads.find_one(
        {"id": lid},
        {"_id": 0, "id": 1, "mobile_digits": 1, "client_lead_id": 1, "futwork_lead_id": 1},
    )
    if not lead:
        return {"lead_id": lid}
    ors: List[Dict[str, Any]] = [{"lead_id": lid}]
    md = (lead.get("mobile_digits") or "").strip()
    if md:
        ors.append({"mobile_digits": md})
    cid = (lead.get("client_lead_id") or "").strip()
    if cid:
        ors.append({"client_lead_id": cid})
    fid = (lead.get("futwork_lead_id") or "").strip()
    if fid:
        ors.append({"futwork_lead_id": fid})
    return {"$or": ors} if len(ors) > 1 else ors[0]


async def _detect_crm_issues_from_calls(db, base: Dict[str, Any]) -> List[str]:
    """Scan key_signals on recent filtered calls for over-calling complaints."""
    issues: List[str] = []
    seen: set = set()
    cursor = (
        db.call_history.find(
            _and_queries(
                base,
                {"structured_extraction.key_signals": {"$exists": True, "$ne": []}},
            ),
            {"structured_extraction.key_signals": 1},
        )
        .sort("created_at", -1)
        .limit(200)
    )
    docs = await cursor.to_list(200)
    for doc in docs:
        se = doc.get("structured_extraction") or {}
        signals = se.get("key_signals") if isinstance(se, dict) else []
        if not isinstance(signals, list):
            continue
        for sig in signals:
            sl = str(sig or "").lower()
            if any(p in sl for p in _OVERCALL_SIGNAL_PHRASES):
                if _CRM_OVERCALL_ISSUE not in seen:
                    seen.add(_CRM_OVERCALL_ISSUE)
                    issues.append(_CRM_OVERCALL_ISSUE)
                break
    return issues


_IST = ZoneInfo("Asia/Kolkata")


def _ist_date_to_utc_bounds(start_date: str, end_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Convert YYYY-MM-DD calendar days (IST) to naive UTC bounds for MongoDB."""
    try:
        day_start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=_IST)
        if end_date:
            day_end = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=_IST) + timedelta(days=1)
        else:
            day_end = day_start + timedelta(days=1)
        return {
            "$gte": day_start.astimezone(timezone.utc).replace(tzinfo=None),
            "$lt": day_end.astimezone(timezone.utc).replace(tzinfo=None),
        }
    except ValueError:
        return None


def _call_history_date_clause(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Build created_at filter for call_history (YYYY-MM-DD interpreted as IST days)."""
    if not start_date and not end_date:
        return None

    if start_date and not end_date:
        bounds = _ist_date_to_utc_bounds(start_date)
        return {"created_at": bounds} if bounds else None

    date_filter: Dict[str, Any] = {}
    if start_date:
        try:
            day_start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=_IST)
            date_filter["$gte"] = day_start.astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError:
            pass
    if end_date:
        try:
            day_end = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=_IST) + timedelta(
                days=1
            )
            date_filter["$lt"] = day_end.astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError:
            pass
    if date_filter:
        return {"created_at": date_filter}
    return None


def _legacy_lead_date_clause(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Date filter for legacy leads fallback (call_date with created_at fallback)."""
    bounds_clause = _call_history_date_clause(start_date, end_date)
    if not bounds_clause:
        return None
    bounds = bounds_clause["created_at"]
    gte = bounds.get("$gte")
    lt = bounds.get("$lt")
    effective = {"$ifNull": ["$call_date", "$created_at"]}
    expr_parts: List[Dict[str, Any]] = []
    if gte is not None:
        expr_parts.append({"$gte": [effective, gte]})
    if lt is not None:
        expr_parts.append({"$lt": [effective, lt]})
    if not expr_parts:
        return None
    if len(expr_parts) == 1:
        return {"$expr": expr_parts[0]}
    return {"$expr": {"$and": expr_parts}}


def _value_in_date_range(
    value: Any, start_date: Optional[str], end_date: Optional[str]
) -> bool:
    clause = _call_history_date_clause(start_date, end_date)
    if not clause:
        return True
    bounds = clause["created_at"]
    dt = value
    if isinstance(dt, str):
        try:
            raw = dt.replace("Z", "+00:00")
            dt = datetime.fromisoformat(raw)
        except ValueError:
            return True
    if not isinstance(dt, datetime):
        return True
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    gte = bounds.get("$gte")
    lt = bounds.get("$lt")
    if gte is not None and dt < gte:
        return False
    if lt is not None and dt >= lt:
        return False
    return True


def _call_history_filter_query(
    campaign: Optional[str],
    status: Optional[str],
    disposition: Optional[str],
    search: Optional[str],
    upload_batch_id: Optional[str] = None,
    lead_id: Optional[str] = None,
    mobile_digits: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    agent_id: Optional[str] = None,
    extra_clause: Optional[Dict[str, Any]] = None,
    *,
    lead_id_clause: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    parts: List[Dict[str, Any]] = []
    if extra_clause:
        parts.append(extra_clause)
    if upload_batch_id and upload_batch_id != "all":
        parts.append({"upload_batch_id": upload_batch_id})
    if lead_id_clause is not None:
        parts.append(lead_id_clause)
    elif lead_id:
        parts.append({"lead_id": lead_id})
    if mobile_digits:
        parts.append({"mobile_digits": mobile_digits})
    if campaign and campaign != "all":
        parts.append({"campaign": campaign})
    if agent_id and agent_id != "all":
        parts.append({"agent_id": agent_id})
    if disposition and disposition != "all":
        parts.append(_futwork_disposition_exact(canonical_disposition_label(disposition)))
    if status and status != "all":
        parts.append({"status": status})

    q = (search or "").strip()
    if q:
        esc = re.escape(q)
        digits = re.sub(r"\D+", "", q)
        or_clauses: List[Dict[str, Any]] = [
            {"customer_name": {"$regex": esc, "$options": "i"}},
            {"phone": {"$regex": esc, "$options": "i"}},
            {"client_lead_id": {"$regex": esc, "$options": "i"}},
        ]
        if digits:
            or_clauses.append({"mobile_digits": {"$regex": digits}})
            if len(digits) > 10:
                or_clauses.append({"mobile_digits": {"$regex": digits[-10:]}})
        parts.append({"$or": or_clauses})

    date_clause = _call_history_date_clause(start_date, end_date)
    if date_clause:
        parts.append(date_clause)

    return _and_queries(*parts)


async def _upload_batch_created_at(db, upload_batch_id: str) -> Optional[datetime]:
    uid = (upload_batch_id or "").strip()
    if not uid:
        return None
    try:
        doc = await db.lead_upload_history.find_one(
            {"id": uid}, {"_id": 0, "created_at": 1}
        )
    except Exception:
        return None
    created = (doc or {}).get("created_at")
    return created if isinstance(created, datetime) else None


async def _upload_batch_call_clause(db, upload_batch_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """Only calls that were tagged for this upload. Never lifetime history for the same phone."""
    uid = (upload_batch_id or "").strip()
    if not uid or uid == "all":
        return None
    return {"upload_batch_id": uid}


def _display_phone(raw: Any, digits: Any = "") -> str:
    d = "".join(c for c in str(digits or raw or "") if c.isdigit())[-10:]
    if len(d) == 10:
        return f"+91{d}"
    text = str(raw or digits or "").strip()
    return text


def _lead_display_name(lead: Dict[str, Any]) -> str:
    name = str(lead.get("full_name") or "").strip()
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
    return combined or name or "Unknown"


def _doc_to_call_row(doc: Dict[str, Any]) -> Dict[str, Any]:
    campaign_name = doc.get("campaign", "") or "Default Campaign"
    extracted = doc.get("extracted_data") or doc.get("extractedData")
    disposition = (doc.get("disposition") or "").strip()
    if not disposition:
        disposition = extract_bolna_disposition(extracted)
    phone = _display_phone(doc.get("phone"), doc.get("mobile_digits"))
    return {
        "id": doc.get("id", doc.get("call_sid", "")),
        "customer_name": doc.get("customer_name", "Unknown"),
        "phone": phone,
        "status": doc.get("status", ""),
        "disposition": disposition,
        "duration": int(doc.get("duration", 0) or 0),
        "recording_url": doc.get("recording_url", ""),
        "transcript": doc.get("transcript", ""),
        "created_at": serialize_datetime_utc(
            doc.get("started_at") or doc.get("created_at")
        ),
        "campaign": campaign_name,
        "lead_id": doc.get("lead_id", ""),
        "direction": doc.get("direction") or "outbound",
        "hangup_by": doc.get("hangup_by") or "bot",
        "extracted_data": extracted if isinstance(extracted, dict) else {},
        "upload_batch_id": doc.get("upload_batch_id") or "",
        "upload_batch_name": doc.get("upload_batch_name") or "",
        "call_sid": doc.get("call_sid") or doc.get("id") or "",
    }


def _lead_to_placeholder_row(lead: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": lead.get("id", ""),
        "customer_name": _lead_display_name(lead),
        "phone": _display_phone(lead.get("mobile"), lead.get("mobile_digits")),
        "status": lead.get("last_call_status") or lead.get("futwork_sync_status") or "queued",
        "disposition": (lead.get("disposition") or "").strip(),
        "duration": int(lead.get("last_call_duration") or 0),
        "recording_url": lead.get("last_recording_url") or "",
        "transcript": lead.get("transcript") or "",
        "created_at": serialize_datetime_utc(
            lead.get("last_call_date") or lead.get("created_at")
        ),
        "campaign": lead.get("campaign_name") or "Default Campaign",
        "lead_id": lead.get("id", ""),
        "direction": "outbound",
        "hangup_by": "bot",
        "extracted_data": lead.get("extracted_data") if isinstance(lead.get("extracted_data"), dict) else {},
        "upload_batch_id": lead.get("upload_batch_id") or "",
        "upload_batch_name": lead.get("upload_batch_name") or "",
        "call_sid": "",
    }


async def _enrich_call_rows_from_leads(db, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not rows:
        return rows
    lead_ids = [str(r.get("lead_id") or "") for r in rows if r.get("lead_id")]
    mobiles = []
    for r in rows:
        digits = "".join(c for c in str(r.get("phone") or "") if c.isdigit())[-10:]
        if len(digits) == 10:
            mobiles.append(digits)
    ors: List[Dict[str, Any]] = []
    if lead_ids:
        ors.append({"id": {"$in": list(dict.fromkeys(lead_ids))}})
    if mobiles:
        ors.append({"mobile_digits": {"$in": list(dict.fromkeys(mobiles))}})
    if not ors:
        return rows
    leads = await db.leads.find(
        ors[0] if len(ors) == 1 else {"$or": ors},
        {
            "_id": 0,
            "id": 1,
            "full_name": 1,
            "first_name": 1,
            "last_name": 1,
            "mobile": 1,
            "mobile_digits": 1,
            "last_recording_url": 1,
            "transcript": 1,
            "disposition": 1,
            "extracted_data": 1,
            "upload_batch_id": 1,
            "upload_batch_name": 1,
        },
    ).to_list(length=max(len(rows) * 2, 50))
    by_id = {str(l.get("id") or ""): l for l in leads if l.get("id")}
    by_mobile = {
        str(l.get("mobile_digits") or ""): l
        for l in leads
        if l.get("mobile_digits")
    }
    for row in rows:
        lead = by_id.get(str(row.get("lead_id") or ""))
        if not lead:
            digits = "".join(c for c in str(row.get("phone") or "") if c.isdigit())[-10:]
            lead = by_mobile.get(digits)
        if not lead:
            continue
        name = _lead_display_name(lead)
        if name and not is_placeholder_customer_name(name):
            row["customer_name"] = name
        phone = _display_phone(lead.get("mobile"), lead.get("mobile_digits"))
        if phone:
            row["phone"] = phone
        if not row.get("lead_id") and lead.get("id"):
            row["lead_id"] = lead["id"]
        if not row.get("recording_url") and lead.get("last_recording_url"):
            row["recording_url"] = lead["last_recording_url"]
        if not row.get("transcript") and lead.get("transcript"):
            row["transcript"] = lead["transcript"]
        if not row.get("disposition") and lead.get("disposition"):
            row["disposition"] = lead["disposition"]
        if not row.get("extracted_data") and isinstance(lead.get("extracted_data"), dict):
            row["extracted_data"] = lead["extracted_data"]
        if not row.get("upload_batch_id") and lead.get("upload_batch_id"):
            row["upload_batch_id"] = lead["upload_batch_id"]
        if not row.get("upload_batch_name") and lead.get("upload_batch_name"):
            row["upload_batch_name"] = lead["upload_batch_name"]
    return rows


async def _list_batch_lead_call_rows(
    db,
    *,
    upload_batch_id: str,
    status: Optional[str],
    disposition: Optional[str],
    search: Optional[str],
    skip_n: int,
    limit_n: int,
    agent_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> tuple[List[Dict[str, Any]], int]:
    """One row per lead in the upload batch, joined to the latest call."""
    uid = (upload_batch_id or "").strip()
    lead_parts: List[Dict[str, Any]] = [{"upload_batch_id": uid}]
    sq = (search or "").strip()
    if sq:
        esc = re.escape(sq)
        digits = re.sub(r"\D+", "", sq)
        ors: List[Dict[str, Any]] = [
            {"full_name": {"$regex": esc, "$options": "i"}},
            {"first_name": {"$regex": esc, "$options": "i"}},
            {"last_name": {"$regex": esc, "$options": "i"}},
            {"mobile": {"$regex": esc, "$options": "i"}},
        ]
        if digits:
            ors.append({"mobile_digits": {"$regex": digits}})
        lead_parts.append({"$or": ors})
    lead_query = _and_queries(*lead_parts)
    leads = await db.leads.find(
        lead_query,
        {
            "_id": 0,
            "id": 1,
            "full_name": 1,
            "first_name": 1,
            "last_name": 1,
            "mobile": 1,
            "mobile_digits": 1,
            "created_at": 1,
            "updated_at": 1,
            "last_call_date": 1,
            "last_call_status": 1,
            "last_call_duration": 1,
            "last_recording_url": 1,
            "transcript": 1,
            "disposition": 1,
            "extracted_data": 1,
            "futwork_sync_status": 1,
            "futwork_lead_id": 1,
            "campaign_name": 1,
            "upload_batch_id": 1,
            "upload_batch_name": 1,
        },
    ).sort("created_at", -1).to_list(length=_BATCH_LEAD_CAP)

    lead_ids = [str(l.get("id") or "") for l in leads if l.get("id")]
    call_filter: Dict[str, Any] = {"upload_batch_id": uid}
    if agent_id and agent_id != "all":
        call_filter = {"$and": [call_filter, {"agent_id": agent_id}]}
    call_docs = await db.call_history.find(
        call_filter,
        {"_id": 0},
    ).sort("created_at", -1).to_list(length=_BATCH_LEAD_CAP)

    missing_lead_ids = [
        str(d.get("lead_id") or "")
        for d in call_docs
        if d.get("lead_id") and str(d.get("lead_id")) not in set(lead_ids)
    ]
    if missing_lead_ids:
        extra = await db.leads.find(
            {"id": {"$in": missing_lead_ids}},
            {
                "_id": 0,
                "id": 1,
                "full_name": 1,
                "first_name": 1,
                "last_name": 1,
                "mobile": 1,
                "mobile_digits": 1,
                "created_at": 1,
                "updated_at": 1,
                "last_call_date": 1,
                "last_call_status": 1,
                "last_call_duration": 1,
                "last_recording_url": 1,
                "transcript": 1,
                "disposition": 1,
                "extracted_data": 1,
                "futwork_sync_status": 1,
                "futwork_lead_id": 1,
                "campaign_name": 1,
                "upload_batch_id": 1,
                "upload_batch_name": 1,
            },
        ).to_list(length=_BATCH_LEAD_CAP)
        seen = {str(l.get("id") or "") for l in leads}
        for lead in extra:
            lid = str(lead.get("id") or "")
            if lid and lid not in seen:
                leads.append(lead)
                seen.add(lid)

    created = await _upload_batch_created_at(db, uid)

    by_lead_calls: Dict[str, Dict[str, Any]] = {}
    by_call_id: Dict[str, Dict[str, Any]] = {}
    by_mobile: Dict[str, Dict[str, Any]] = {}
    for doc in call_docs:
        lid = str(doc.get("lead_id") or "")
        if lid and lid not in by_lead_calls:
            by_lead_calls[lid] = doc
        cid = str(doc.get("id") or doc.get("call_sid") or "")
        if cid and cid not in by_call_id:
            by_call_id[cid] = doc
        md = str(doc.get("mobile_digits") or "")
        if md and md not in by_mobile:
            by_mobile[md] = doc

    rows: List[Dict[str, Any]] = []
    want_status = (status or "").strip().lower()
    want_disp = canonical_disposition_label(disposition) if disposition and disposition != "all" else ""
    for lead in leads:
        call_doc = (
            by_lead_calls.get(str(lead.get("id") or ""))
            or by_call_id.get(str(lead.get("futwork_lead_id") or ""))
            or by_mobile.get(str(lead.get("mobile_digits") or ""))
        )
        if call_doc:
            row = _doc_to_call_row(call_doc)
            if is_placeholder_customer_name(row.get("customer_name")):
                name = _lead_display_name(lead)
                if name and not is_placeholder_customer_name(name):
                    row["customer_name"] = name
        else:
            row = _lead_to_placeholder_row(lead)
            lcd = lead.get("last_call_date")
            if created is not None and isinstance(lcd, datetime) and lcd < created:
                row["status"] = lead.get("futwork_sync_status") or "queued"
                row["duration"] = 0
                row["disposition"] = ""
                row["recording_url"] = ""
                row["transcript"] = ""
                row["created_at"] = serialize_datetime_utc(
                    lead.get("updated_at") or created
                )
            name = _lead_display_name(lead)
            if name and not is_placeholder_customer_name(name):
                row["customer_name"] = name
        phone = _display_phone(lead.get("mobile"), lead.get("mobile_digits"))
        if phone:
            row["phone"] = phone
        row["lead_id"] = lead.get("id") or row.get("lead_id") or ""
        stamp = (
            (call_doc or {}).get("started_at")
            or (call_doc or {}).get("created_at")
            or lead.get("last_call_date")
            or lead.get("created_at")
        )
        if not _value_in_date_range(stamp, start_date, end_date):
            continue
        if want_status and want_status != "all":
            if str(row.get("status") or "").strip().lower() != want_status:
                continue
        if want_disp:
            got = canonical_disposition_label(row.get("disposition") or "")
            if got != want_disp:
                continue
        rows.append(row)

    total = len(rows)
    page_rows = rows[skip_n : skip_n + limit_n]
    return page_rows, total


@app.get("/api/call-history/filters", dependencies=_auth_dep)
async def get_call_history_filters(agent_id: str = None, db=Depends(get_db)):
    """Distinct filter values — only this agent's currently active dispositions."""
    try:
        all_campaign_names = await db.campaigns.distinct("name")
        ch_campaign_names = await db.call_history.distinct("campaign")
        lead_campaign_names = await db.leads.distinct("campaign_name")
        campaigns_merged = sorted(
            set(
                c
                for c in (all_campaign_names + ch_campaign_names + lead_campaign_names)
                if c
            )
        )

        match: Dict[str, Any] = {}
        if agent_id and agent_id != "all":
            match["agent_id"] = agent_id
        statuses = sorted(
            {
                s
                for s in await db.call_history.distinct("status", match)
                if s is not None and str(s).strip()
            }
        )
        # Hindu agent extractions only — never inject the broader IDAC list.
        dispositions = list(AGENT_ACTIVE_DISPOSITIONS)

        upload_batches = await CampaignService(db).list_upload_batches_for_filters(limit=100)

        return {
            "campaigns": campaigns_merged,
            "statuses": statuses,
            "dispositions": dispositions,
            "upload_batches": upload_batches,
        }
    except Exception as e:
        logger.error("Error fetching call history filters: %s", e)
        return {"campaigns": [], "statuses": [], "dispositions": [], "upload_batches": []}


@app.get("/api/call-history/summary", dependencies=_auth_dep)
async def get_call_history_summary(
    campaign: str = None,
    status: str = None,
    disposition: str = None,
    q: str = None,
    upload_batch_id: str = None,
    leadId: str = None,
    mobile_digits: str = None,
    start_date: str = None,
    end_date: str = None,
    agent_id: str = None,
    db=Depends(get_db),
):
    """Aggregated KPIs for call_history matching the same filters as the list endpoint."""
    try:
        lead_clause = await _call_history_lead_id_clause(db, leadId) if leadId else None
        batch_clause = await _upload_batch_call_clause(db, upload_batch_id)
        base = _call_history_filter_query(
            campaign,
            status,
            disposition,
            q,
            extra_clause=batch_clause,
            lead_id=leadId,
            mobile_digits=mobile_digits,
            start_date=start_date,
            end_date=end_date,
            agent_id=agent_id,
            lead_id_clause=lead_clause,
        )
        total = await db.call_history.count_documents(base)

        completed_q = _and_queries(
            base,
            {"status": {"$regex": r"^completed$", "$options": "i"}},
        )
        attending_q = _and_queries(base, _futwork_disposition_exact("Attending"))
        not_attending_q = _and_queries(
            base, _futwork_disposition_exact("Not Attending")
        )

        completed = await db.call_history.count_documents(completed_q)
        attending = await db.call_history.count_documents(attending_q)
        not_attending = await db.call_history.count_documents(not_attending_q)

        connected_q = _and_queries(base, {"duration": {"$gt": 0}})
        connected_calls = await db.call_history.count_documents(connected_q)
        pipeline = [
            {"$match": connected_q},
            {"$group": {"_id": None, "avg": {"$avg": "$duration"}, "n": {"$sum": 1}}},
        ]
        agg = await db.call_history.aggregate(pipeline).to_list(1)
        avg_duration = 0.0
        if agg and agg[0].get("avg") is not None:
            avg_duration = float(agg[0]["avg"])

        return {
            "total_calls": total,
            "completed": completed,
            "attending": attending,
            "not_attending": not_attending,
            "connected_calls": connected_calls,
            "avg_duration_seconds": round(avg_duration) if connected_calls else 0,
        }
    except Exception as e:
        logger.error("Error in call history summary: %s", e)
        return {
            "total_calls": 0,
            "completed": 0,
            "attending": 0,
            "not_attending": 0,
            "connected_calls": 0,
            "avg_duration_seconds": 0,
        }


@app.get("/api/call-history/ai-batch-summary", dependencies=_auth_dep)
async def get_call_history_ai_batch_summary(
    campaign: str = None,
    status: str = None,
    disposition: str = None,
    q: str = None,
    upload_batch_id: str = None,
    start_date: str = None,
    end_date: str = None,
    agent_id: str = None,
    db=Depends(get_db),
):
    """
    Batch summary computed from AI structured extractions stored on call_history.
    Returns a shape compatible with the frontend \"Batch Summary\" view.
    """
    try:
        batch_clause = await _upload_batch_call_clause(db, upload_batch_id)
        base = _call_history_filter_query(
            campaign,
            status,
            disposition,
            q,
            extra_clause=batch_clause,
            start_date=start_date,
            end_date=end_date,
            agent_id=agent_id,
        )
        # Only consider calls with structured extraction present
        base = _and_queries(base, {"structured_extraction.disposition": {"$exists": True, "$ne": ""}})

        total = await db.call_history.count_documents(base)
        if total == 0:
            return {
                "batch_summary": {
                    "total_calls": 0,
                    "hot_leads": 0,
                    "semi_interested": 0,
                    "mildly_interested": 0,
                    "not_interested": 0,
                    "voicemail_wrong_number": 0,
                    "already_bought": 0,
                    "system_tags_incorrect": 0,
                    "top_priority_leads": [],
                    "crm_issues_detected": [],
                }
            }

        # Aggregate counts by AI disposition
        pipeline = [
            {"$match": base},
            {"$group": {"_id": "$structured_extraction.disposition", "count": {"$sum": 1}}},
        ]
        rows = await db.call_history.aggregate(pipeline).to_list(length=50)
        counts = {str(r["_id"]): int(r["count"]) for r in rows if r.get("_id")}

        system_incorrect = await db.call_history.count_documents(
            _and_queries(base, {"structured_extraction.system_tag_correct": False})
        )

        # Priority leads: choose Hot, then Semi, then Mild by recency
        pri_disp = [
            StructuredDisposition.hot_lead.value,
            StructuredDisposition.semi_interested.value,
            "Semi-interested",
            StructuredDisposition.mildly_interested.value,
        ]
        pri_cursor = (
            db.call_history.find(
                _and_queries(base, {"structured_extraction.disposition": {"$in": pri_disp}}),
                {"_id": 0, "structured_extraction.lead_name": 1, "structured_extraction.phone": 1, "created_at": 1},
            )
            .sort("created_at", -1)
            .limit(50)
        )
        pri_docs = await pri_cursor.to_list(50)
        top_priority = []
        seen = set()
        for d in pri_docs:
            se = d.get("structured_extraction") or {}
            name = (se.get("lead_name") or "Unknown").strip() or "Unknown"
            phone = (se.get("phone") or "").strip()
            key = f"{name}|{phone}"
            if key in seen:
                continue
            seen.add(key)
            top_priority.append(f"{name} ({phone})" if phone else name)
            if len(top_priority) >= 3:
                break

        crm_issues = await _detect_crm_issues_from_calls(db, base)

        return {
            "batch_summary": {
                "total_calls": total,
                "hot_leads": int(counts.get(StructuredDisposition.hot_lead.value, 0)),
                "semi_interested": int(
                    counts.get(StructuredDisposition.semi_interested.value, 0)
                    + counts.get("Semi-interested", 0)
                ),
                "mildly_interested": int(counts.get(StructuredDisposition.mildly_interested.value, 0)),
                "not_interested": int(counts.get(StructuredDisposition.not_interested.value, 0)),
                "voicemail_wrong_number": int(counts.get(StructuredDisposition.voicemail.value, 0))
                + int(counts.get(StructuredDisposition.wrong_number.value, 0)),
                "already_bought": int(counts.get(StructuredDisposition.already_bought.value, 0)),
                "system_tags_incorrect": int(system_incorrect),
                "top_priority_leads": top_priority,
                "crm_issues_detected": crm_issues,
            }
        }
    except Exception as e:
        logger.error("Error in ai batch summary: %s", e)
        return {
            "batch_summary": {
                "total_calls": 0,
                "hot_leads": 0,
                "semi_interested": 0,
                "mildly_interested": 0,
                "not_interested": 0,
                "voicemail_wrong_number": 0,
                "already_bought": 0,
                "system_tags_incorrect": 0,
                "top_priority_leads": [],
                "crm_issues_detected": [],
            }
        }


@app.get("/api/call-history/by-id/{call_id}", dependencies=_auth_dep)
async def get_call_history_by_id(call_id: str, db=Depends(get_db)):
    """Full call (or lead placeholder) for the View Details modal."""
    cid = (call_id or "").strip()
    if not cid:
        raise HTTPException(status_code=404, detail="Call not found")
    doc = await db.call_history.find_one(
        {"$or": [{"id": cid}, {"call_sid": cid}]},
        {"_id": 0},
    )
    if doc:
        rows = await _enrich_call_rows_from_leads(db, [_doc_to_call_row(doc)])
        return rows[0]
    lead = await db.leads.find_one({"id": cid}, {"_id": 0})
    if lead:
        latest = await (
            db.call_history.find({"lead_id": cid}, {"_id": 0})
            .sort("created_at", -1)
            .limit(1)
            .to_list(1)
        )
        row = _doc_to_call_row(latest[0]) if latest else _lead_to_placeholder_row(lead)
        rows = await _enrich_call_rows_from_leads(db, [row])
        return rows[0]
    raise HTTPException(status_code=404, detail="Call not found")


async def _fetch_filtered_calls(
    db,
    *,
    campaign: Optional[str],
    status: Optional[str],
    disposition: Optional[str],
    q: Optional[str],
    upload_batch_id: Optional[str],
    leadId: Optional[str],
    mobile_digits: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    agent_id: Optional[str],
    skip_n: int,
    limit_n: int,
) -> tuple[List[Dict[str, Any]], int]:
    """Same matching rules as the AI Calling list, for one page or a full export."""
    lead_clause = await _call_history_lead_id_clause(db, leadId) if leadId else None
    batch_clause = await _upload_batch_call_clause(db, upload_batch_id)
    ch_query = _call_history_filter_query(
        campaign,
        status,
        disposition,
        q,
        extra_clause=batch_clause,
        lead_id=leadId,
        mobile_digits=mobile_digits,
        start_date=start_date,
        end_date=end_date,
        agent_id=agent_id,
        lead_id_clause=lead_clause,
    )

    calls: List[Dict[str, Any]] = []
    total = 0
    call_history_collection_used = await db.call_history.count_documents({}) > 0
    uid = (upload_batch_id or "").strip()
    use_batch_leads = bool(uid) and uid != "all" and not leadId

    if use_batch_leads:
        calls, total = await _list_batch_lead_call_rows(
            db,
            upload_batch_id=uid,
            status=status,
            disposition=disposition,
            search=q,
            skip_n=skip_n,
            limit_n=limit_n,
            agent_id=agent_id,
            start_date=start_date,
            end_date=end_date,
        )
        return calls, total

    if call_history_collection_used:
        total = await db.call_history.count_documents(ch_query)
        ch_docs = await (
            db.call_history.find(ch_query, {"_id": 0})
            .sort("created_at", -1)
            .skip(skip_n)
            .limit(limit_n)
            .to_list(limit_n)
        )
        for doc in ch_docs:
            calls.append(_doc_to_call_row(doc))
        calls = await _enrich_call_rows_from_leads(db, calls)
        return calls, total

    legacy_parts: List[Dict[str, Any]] = [
        {
            "$or": [
                {"call_status": {"$nin": ["", None]}},
                {"recording_url": {"$nin": ["", None]}},
            ]
        }
    ]
    if campaign and campaign != "all":
        legacy_parts.append({"campaign_name": campaign})
    if disposition and disposition != "all":
        legacy_parts.append(_futwork_disposition_exact(canonical_disposition_label(disposition)))
    if status and status != "all":
        legacy_parts.append(
            {"$or": [{"call_status": {"$regex": f"^{status}$", "$options": "i"}}]}
        )

    sq = (q or "").strip()
    if sq:
        esc = re.escape(sq)
        digits = re.sub(r"\D+", "", sq)
        ors = [
            {"full_name": {"$regex": esc, "$options": "i"}},
            {"mobile": {"$regex": esc, "$options": "i"}},
            {"client_lead_id": {"$regex": esc, "$options": "i"}},
        ]
        if digits:
            ors.append({"mobile_digits": {"$regex": digits}})
        legacy_parts.append({"$or": ors})

    legacy_date = _legacy_lead_date_clause(start_date, end_date)
    if legacy_date:
        legacy_parts.append(legacy_date)

    base_query = _and_queries(*legacy_parts)
    total = await db.leads.count_documents(base_query)
    leads_data = await (
        db.leads.find(base_query, {"_id": 0})
        .sort("created_at", -1)
        .skip(skip_n)
        .limit(limit_n)
        .to_list(limit_n)
    )
    for lead in leads_data:
        call_status = lead.get("call_status", "") or "completed"
        campaign_name = lead.get("campaign_name", "") or "Default Campaign"
        calls.append(
            {
                "id": lead.get("id", ""),
                "customer_name": _lead_display_name(lead),
                "phone": _display_phone(lead.get("mobile"), lead.get("mobile_digits")),
                "status": call_status,
                "disposition": lead.get("disposition", ""),
                "duration": int(lead.get("call_duration", 0) or 0),
                "recording_url": lead.get("recording_url", ""),
                "transcript": lead.get("transcript", ""),
                "created_at": serialize_datetime_utc(
                    lead.get("call_date") or lead.get("created_at")
                ),
                "campaign": campaign_name,
                "lead_id": lead.get("id", ""),
                "direction": "outbound",
                "hangup_by": "bot",
            }
        )
    return calls, total


def _call_history_csv_bytes(rows: List[Dict[str, Any]]) -> bytes:
    out = io.StringIO()
    out.write("\ufeff")
    writer = csv.writer(out)
    writer.writerow([label for _, label in _CALL_EXPORT_COLUMNS])
    for row in rows:
        writer.writerow(
            ["" if row.get(key) is None else str(row.get(key, "")) for key, _ in _CALL_EXPORT_COLUMNS]
        )
    return out.getvalue().encode("utf-8")


@app.get("/api/call-history/export", dependencies=_auth_dep)
async def export_call_history(
    campaign: str = None,
    status: str = None,
    disposition: str = None,
    q: str = None,
    upload_batch_id: str = None,
    leadId: str = None,
    mobile_digits: str = None,
    start_date: str = None,
    end_date: str = None,
    agent_id: str = None,
    db=Depends(get_db),
):
    """CSV of every call matching the same filters as GET /api/call-history."""
    try:
        calls, _total = await _fetch_filtered_calls(
            db,
            campaign=campaign,
            status=status,
            disposition=disposition,
            q=q,
            upload_batch_id=upload_batch_id,
            leadId=leadId,
            mobile_digits=mobile_digits,
            start_date=start_date,
            end_date=end_date,
            agent_id=agent_id,
            skip_n=0,
            limit_n=_CALL_EXPORT_CAP,
        )
    except Exception:
        logger.exception("Error exporting call history")
        raise HTTPException(status_code=500, detail="Failed to export call history")

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"ai-calling-{stamp}.csv"
    return StreamingResponse(
        iter([_call_history_csv_bytes(calls)]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/call-history", dependencies=_auth_dep)
async def get_call_history(
    campaign: str = None,
    status: str = None,
    disposition: str = None,
    q: str = None,
    upload_batch_id: str = None,
    leadId: str = None,
    mobile_digits: str = None,
    start_date: str = None,
    end_date: str = None,
    agent_id: str = None,
    page: int = 1,
    size: int = 50,
    limit: int = 0,
    offset: int = 0,
    db=Depends(get_db),
):
    """
    Paginated call history from call_history (webhooks), with legacy leads fallback
    only when call_history is empty for this deployment.
    """
    try:
        use_legacy_pagination = limit > 0 and page == 1 and size == 50
        if use_legacy_pagination:
            skip_n = offset
            limit_n = limit if limit > 0 else 100000
        else:
            page = max(1, page)
            size = min(max(1, size), 500)
            skip_n = (page - 1) * size
            limit_n = size

        calls, total = await _fetch_filtered_calls(
            db,
            campaign=campaign,
            status=status,
            disposition=disposition,
            q=q,
            upload_batch_id=upload_batch_id,
            leadId=leadId,
            mobile_digits=mobile_digits,
            start_date=start_date,
            end_date=end_date,
            agent_id=agent_id,
            skip_n=skip_n,
            limit_n=limit_n,
        )
        has_more = skip_n + len(calls) < total
        return {
            "calls": calls,
            "total": total,
            "page": page if not use_legacy_pagination else 1,
            "size": limit_n if use_legacy_pagination else size,
            "has_more": has_more,
        }
    except Exception as e:
        logger.error(f"Error fetching call history: {e}")
        return {
            "calls": [],
            "total": 0,
            "page": 1,
            "size": size,
            "has_more": False,
        }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
