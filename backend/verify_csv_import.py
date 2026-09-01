"""One-off verification: compare call_history CSV against MongoDB."""
import asyncio
import os
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env")

MONGO_URL = os.getenv("MONGO_URL", "")
DB_NAME = os.getenv("DB_NAME", "idac_db")
CSV = BACKEND_DIR / (
    "csv/idac-bani-production-2026-04-15-2026-06-30-"
    "ai_platform_call_history_report-c5bf2072-16aa-42e3-8a1f-241066256db9.csv"
)


def safe_str(v) -> str:
    s = str(v or "").strip()
    return "" if s.lower() in ("nan", "none", "null") else s


async def main() -> None:
    if not MONGO_URL:
        print("ERROR: MONGO_URL not set")
        sys.exit(1)

    df = pd.read_csv(CSV, dtype=str, keep_default_na=False)
    csv_sids_valid = [safe_str(x) for x in df["callSid"] if safe_str(x)]
    csv_unique = set(csv_sids_valid)

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    await db.command("ping")

    total_ch = await db.call_history.count_documents({})
    matched = await db.call_history.count_documents({"id": {"$in": list(csv_unique)}})
    db_ids = set(await db.call_history.distinct("id", {"id": {"$in": list(csv_unique)}}))
    missing = csv_unique - db_ids

    csv_disp = Counter(safe_str(x) or "(empty)" for x in df["disposition"])
    db_disp_rows = await db.call_history.aggregate(
        [
            {"$match": {"id": {"$in": list(csv_unique)}}},
            {"$group": {"_id": "$disposition", "count": {"$sum": 1}}},
        ]
    ).to_list(200)
    db_disp = Counter({(r["_id"] or "(empty)"): r["count"] for r in db_disp_rows})

    csv_status = Counter(safe_str(x) or "(empty)" for x in df["status"])
    db_status_rows = await db.call_history.aggregate(
        [
            {"$match": {"id": {"$in": list(csv_unique)}}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ]
    ).to_list(200)
    db_status = Counter({(r["_id"] or "(empty)"): r["count"] for r in db_status_rows})

    mismatches = []
    for _, row in df.head(50).iterrows():
        sid = safe_str(row["callSid"])
        if not sid:
            continue
        doc = await db.call_history.find_one({"id": sid}, {"_id": 0})
        if not doc:
            mismatches.append((sid, "NOT FOUND"))
            continue
        for field, raw in (
            ("status", row["status"]),
            ("disposition", row["disposition"]),
            ("duration", row["duration"]),
        ):
            expected = int(float(safe_str(raw) or 0)) if field == "duration" else safe_str(raw)
            actual = doc.get(field)
            if field == "duration":
                actual = int(actual or 0)
            else:
                actual = safe_str(actual)
            if actual != expected:
                mismatches.append((sid, f"{field}: csv={expected!r} db={actual!r}"))

    csv_dur_sum = sum(int(float(safe_str(x) or 0)) for x in df["duration"])
    agg = await db.call_history.aggregate(
        [
            {"$match": {"id": {"$in": list(csv_unique)}}},
            {"$group": {"_id": None, "total_duration": {"$sum": "$duration"}, "count": {"$sum": 1}}},
        ]
    ).to_list(1)
    db_dur_sum = agg[0]["total_duration"] if agg else 0
    db_matched_count = agg[0]["count"] if agg else 0

    recent_batches = await db.call_history.aggregate(
        [
            {"$match": {"upload_batch_id": {"$exists": True}}},
            {
                "$group": {
                    "_id": "$upload_batch_id",
                    "label": {"$first": "$upload_batch_label"},
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"_id": -1}},
            {"$limit": 5},
        ]
    ).to_list(5)

    # Extra: check upload metadata on a sample doc
    sample = await db.call_history.find_one({"id": list(csv_unique)[0]}, {"_id": 0})
    sample_fields = {}
    if sample:
        for k in (
            "upload_batch_id",
            "upload_batch_label",
            "source_id",
            "campaign",
            "customer_name",
            "extracted_data",
            "mobile_digits",
            "lead_id",
        ):
            sample_fields[k] = sample.get(k)

    leads_count = await db.leads.count_documents({})
    leads_with_mobile = await db.leads.count_documents({"mobile_digits": {"$exists": True, "$ne": ""}})

    field_counts = {}
    for field in (
        "recording_url",
        "transcript",
        "extracted_data",
        "customer_name",
        "campaign",
        "duration",
        "disposition",
    ):
        field_counts[field] = await db.call_history.count_documents(
            {field: {"$exists": True, "$nin": [None, ""]}}
        )

    camp_ids = [x for x in await db.call_history.distinct("campaign_id") if x]
    camp_resolution = {}
    for cid in camp_ids:
        doc = await db.campaigns.find_one(
            {"$or": [{"futwork_campaign_id": cid}, {"id": cid}]},
            {"_id": 0, "name": 1},
        )
        camp_resolution[cid] = doc.get("name") if doc else None

    date_agg = await db.call_history.aggregate(
        [
            {"$group": {"_id": None, "min": {"$min": "$created_at"}, "max": {"$max": "$created_at"}}}
        ]
    ).to_list(1)
    distinct_phones = len(await db.call_history.distinct("mobile_digits"))

    print("=== CSV ===")
    print(f"Rows: {len(df):,}")
    print(f"Unique callSid: {len(csv_unique):,}")
    print(f"Duplicate callSid in CSV: {len(csv_sids_valid) - len(csv_unique):,}")
    print(f"Duration sum (csv): {csv_dur_sum:,}")
    print()
    print("=== MongoDB call_history ===")
    print(f"Total documents in collection: {total_ch:,}")
    print(f"Matched by CSV callSid: {matched:,}")
    print(f"Missing from DB: {len(missing):,}")
    if missing:
        print(f"  First missing SIDs: {list(missing)[:5]}")
    print(f"Matched count (agg): {db_matched_count:,}")
    print(f"Duration sum (db matched): {db_dur_sum:,}")
    print()
    print("=== Recent upload batches ===")
    for b in recent_batches:
        label = (b.get("label") or "")[:70]
        print(f"  {b['_id']} | {label} | count={b['count']:,}")
    print()
    print("=== Sample doc fields (first CSV callSid) ===")
    for k, v in sample_fields.items():
        print(f"  {k}: {v!r}")
    print()
    print("=== Disposition CSV vs DB ===")
    disp_ok = True
    for d in sorted(set(csv_disp) | set(db_disp)):
        c, db_c = csv_disp.get(d, 0), db_disp.get(d, 0)
        flag = "OK" if c == db_c else "MISMATCH"
        if c != db_c:
            disp_ok = False
        print(f"  {d:<30} csv={c:>6,}  db={db_c:>6,}  {flag}")
    print()
    print("=== Status CSV vs DB ===")
    status_ok = True
    for s in sorted(set(csv_status) | set(db_status)):
        c, db_c = csv_status.get(s, 0), db_status.get(s, 0)
        flag = "OK" if c == db_c else "MISMATCH"
        if c != db_c:
            status_ok = False
        print(f"  {s:<20} csv={c:>6,}  db={db_c:>6,}  {flag}")
    print()
    print(f"=== Field checks (first 50 rows): {len(mismatches)} issues ===")
    for m in mismatches[:20]:
        print(f"  {m}")
    print()
    print(f"Leads collection total: {leads_count:,}")
    print(f"Leads with mobile_digits: {leads_with_mobile:,}")
    print()
    print("=== Field population (call_history) ===")
    for field, count in field_counts.items():
        print(f"  {field:<18} {count:>6,} / {len(df):,}")
    print(f"  distinct mobile_digits: {distinct_phones:,}")
    if date_agg:
        print(f"  created_at range: {date_agg[0]['min']} -> {date_agg[0]['max']}")
    print()
    print("=== Campaign name resolution ===")
    resolved = sum(1 for v in camp_resolution.values() if v)
    print(f"  distinct campaign_id in calls: {len(camp_ids)}")
    print(f"  resolved to campaign name: {resolved}")
    for cid, name in sorted(camp_resolution.items()):
        print(f"    {cid} -> {name or 'NOT IN campaigns collection'}")

    overall = (
        matched == len(csv_unique)
        and not mismatches
        and disp_ok
        and status_ok
        and csv_dur_sum == db_dur_sum
    )
    print()
    print("=== VERDICT ===")
    print("PASS — import matches CSV" if overall else "ISSUES FOUND — see details above")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
