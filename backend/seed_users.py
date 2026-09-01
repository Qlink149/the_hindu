"""Seed users from seed_users.json — sync DB to match the seed list."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.security import hash_password

_SEED_FILE = Path(__file__).resolve().parent / "seed_users.json"


async def seed_users(db) -> int:
    """
    Keep only users listed in seed_users.json.
    Removes stale accounts and upserts seed entries (password/name/role).
    """
    if not _SEED_FILE.exists():
        return 0

    raw = json.loads(_SEED_FILE.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        return 0

    now = datetime.now(timezone.utc).isoformat()
    seed_emails: list[str] = []
    synced = 0

    for entry in raw:
        email = str(entry.get("email") or "").strip().lower()
        password = str(entry.get("password") or "")
        full_name = str(entry.get("full_name") or email.split("@")[0]).strip()
        username = str(entry.get("username") or full_name or email).strip()
        role = str(entry.get("role") or "sales").strip().lower()
        if role not in ("admin", "sales"):
            role = "sales"
        if not email or not password:
            continue

        seed_emails.append(email)
        patch = {
            "email": email,
            "username": username,
            "full_name": full_name,
            "role": role,
            "hashed_password": hash_password(password),
            "is_active": True,
            "updated_at": now,
        }

        existing = await db.users.find_one({"email": email}, {"_id": 1, "id": 1})
        if existing:
            await db.users.update_one({"email": email}, {"$set": patch})
        else:
            await db.users.insert_one(
                {
                    "id": str(uuid.uuid4()),
                    "current_session_id": None,
                    "notification_dismissals": [],
                    "created_at": now,
                    **patch,
                }
            )
        synced += 1

    if seed_emails:
        await db.users.delete_many({"email": {"$nin": seed_emails}})

    return synced
