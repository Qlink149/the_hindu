"""Store original campaign CSV files. Mongo is primary; Cloudinary is optional."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from bson.binary import Binary

from app.core.config import settings

logger = logging.getLogger(__name__)


async def store_original_csv(
    db,
    *,
    upload_id: str,
    filename: str,
    content: bytes,
    batch_label: str = "",
) -> Dict[str, str]:
    """Persist CSV bytes in Mongo so uploads work without Cloudinary.

    If CLOUDINARY_URL is set, also mirror the file there for a public URL.
    """
    await db.lead_upload_files.replace_one(
        {"upload_id": upload_id},
        {
            "upload_id": upload_id,
            "filename": filename or "upload.csv",
            "content_type": "text/csv",
            "content": Binary(content),
            "byte_size": len(content),
            "created_at": datetime.now(timezone.utc),
        },
        upsert=True,
    )

    secure_url = ""
    public_id = ""
    if (settings.CLOUDINARY_URL or "").strip():
        try:
            from .cloudinary_csv import upload_lead_csv_raw

            cloud = await upload_lead_csv_raw(
                content,
                batch_label=batch_label or filename,
                upload_id=upload_id,
            )
            secure_url = str(cloud.get("secure_url") or "")
            public_id = str(cloud.get("public_id") or "")
        except Exception:
            logger.exception(
                "Optional Cloudinary CSV upload failed; file kept in Mongo | upload_id=%s",
                upload_id,
            )

    return {"secure_url": secure_url, "public_id": public_id}


async def get_original_csv_bytes(
    db, upload_id: str
) -> Optional[Tuple[bytes, str]]:
    doc = await db.lead_upload_files.find_one({"upload_id": upload_id})
    if not doc or doc.get("content") is None:
        return None
    return bytes(doc["content"]), str(doc.get("filename") or "upload.csv")


async def has_original_csv(db, upload_id: str, history: Optional[Dict[str, Any]] = None) -> bool:
    stored = await db.lead_upload_files.find_one({"upload_id": upload_id}, {"_id": 1})
    if stored:
        return True
    if history and (history.get("original_csv_secure_url") or "").strip():
        return True
    return False
