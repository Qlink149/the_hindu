"""Background CSV lead upload processing with progress tracking."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..core.config import settings
from ..core.database import db_instance
from ..services.campaign_service import CampaignService
from ..services.lead_service import LeadService

logger = logging.getLogger(__name__)

_FAILURE_INSERT_CHUNK = 1000
_PROCESS_CHUNK = 50
_PROGRESS_EVERY_ROWS = 25


async def _persist_failed_rows(db, upload_id: str, failed_rows: List[Dict[str, Any]]) -> None:
    if not failed_rows:
        return
    failure_docs = [
        {
            "upload_id": upload_id,
            "row_index": int(f.get("row_index", -1)),
            "reason": f.get("reason", ""),
            "raw": f.get("raw", {}),
            "created_at": datetime.utcnow(),
        }
        for f in failed_rows
    ]
    for i in range(0, len(failure_docs), _FAILURE_INSERT_CHUNK):
        await db.lead_upload_failures.insert_many(
            failure_docs[i : i + _FAILURE_INSERT_CHUNK],
            ordered=False,
        )


async def run_lead_csv_upload_job(
    *,
    upload_id: str,
    rows: List[Dict[str, Any]],
    resolved_batch: str,
    filename: str,
    csv_headers: List[str],
    original_csv_secure_url: str,
    original_csv_public_id: str,
    push_to_futwork: bool,
) -> None:
    db = db_instance.db
    if db is None:
        logger.error("CSV upload job aborted: database unavailable | upload_id=%s", upload_id)
        return

    row_count = len(rows)
    service = LeadService(db)
    total_processed = 0
    total_new = 0
    total_updated = 0
    all_failed_rows: List[Dict[str, Any]] = []

    try:
        await db.lead_upload_history.update_one(
            {"id": upload_id},
            {
                "$set": {
                    "status": "processing",
                    "row_count": row_count,
                    "rows_processed": 0,
                    "phase": "importing_leads",
                }
            },
        )

        for start in range(0, row_count, _PROCESS_CHUNK):
            chunk = rows[start : start + _PROCESS_CHUNK]
            result = await service.upsert_from_csv(
                chunk,
                upload_batch_id=upload_id,
                upload_batch_name=resolved_batch,
                auto_assign_new=True,
            )
            total_processed += int(result.get("processed", 0) or 0)
            total_new += int(result.get("new", 0) or 0)
            total_updated += int(result.get("updated", 0) or 0)
            chunk_failed = result.get("failed_rows", []) or []
            for f in chunk_failed:
                item = dict(f)
                item["row_index"] = int(item.get("row_index", 0)) + start
                all_failed_rows.append(item)

            rows_done = min(start + len(chunk), row_count)
            if rows_done % _PROGRESS_EVERY_ROWS == 0 or rows_done == row_count:
                await db.lead_upload_history.update_one(
                    {"id": upload_id},
                    {
                        "$set": {
                            "rows_processed": rows_done,
                            "processed": total_processed,
                            "new_leads": total_new,
                            "updated_leads": total_updated,
                            "unprocessed": len(all_failed_rows),
                        }
                    },
                )

        await _persist_failed_rows(db, upload_id, all_failed_rows)

        pushed_count = 0
        failed_count = 0
        if push_to_futwork:
            if not settings.calling_engine_ready:
                await db.lead_upload_history.update_one(
                    {"id": upload_id},
                    {
                        "$set": {
                            "phase": "futwork_skipped",
                            "error_message": "Calling Engine is not configured on the server.",
                        }
                    },
                )
            else:
                await db.lead_upload_history.update_one(
                    {"id": upload_id},
                    {"$set": {"phase": "syncing_to_calling"}},
                )
                upload_campaign_id = None
                try:
                    cs = CampaignService(db)
                    doc = await cs.find_campaign_by_futwork_settings()
                    if doc and doc.get("id"):
                        upload_campaign_id = str(doc["id"])
                except Exception:
                    logger.exception(
                        "upload job: failed to resolve campaign | upload_id=%s", upload_id
                    )
                leads_to_push = await service.leads_for_futwork_push_by_batch(upload_id)
                pushed_count, failed_count = await service.push_to_futwork(
                    leads_to_push,
                    campaign_id=upload_campaign_id,
                )

        final_status = "completed"
        if push_to_futwork and pushed_count <= 0 and total_processed > 0:
            if not settings.calling_engine_ready:
                final_status = "completed"
            elif failed_count > 0 and pushed_count == 0:
                final_status = "completed"

        await db.lead_upload_history.update_one(
            {"id": upload_id},
            {
                "$set": {
                    "status": final_status,
                    "phase": "done",
                    "rows_processed": row_count,
                    "processed": total_processed,
                    "new_leads": total_new,
                    "updated_leads": total_updated,
                    "unprocessed": len(all_failed_rows),
                    "futwork_pushed": pushed_count if push_to_futwork else 0,
                    "futwork_failed": failed_count if push_to_futwork else 0,
                    "completed_at": datetime.utcnow(),
                }
            },
        )
        logger.info(
            "CSV upload complete | upload_id=%s | processed=%s new=%s updated=%s unprocessed=%s futwork=%s",
            upload_id,
            total_processed,
            total_new,
            total_updated,
            len(all_failed_rows),
            pushed_count,
        )
    except Exception:
        logger.exception("CSV upload job failed | upload_id=%s", upload_id)
        await db.lead_upload_history.update_one(
            {"id": upload_id},
            {"$set": {"status": "failed", "phase": "failed", "completed_at": datetime.utcnow()}},
        )


def schedule_lead_csv_upload_job(**kwargs: Any) -> None:
    asyncio.create_task(run_lead_csv_upload_job(**kwargs))
