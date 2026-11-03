"""Idempotent startup seeding: admin account, personas, company templates, scenarios, question bank."""
import logging
import os
import uuid
from datetime import datetime, timezone

from lib.auth import hash_password
from lib.db import db
from lib.seed_data import COMPANY_TEMPLATES, PERSONAS, SCENARIOS, build_questions, removed_duplicates

logger = logging.getLogger(__name__)


async def seed_all() -> None:
    try:
        from lib.mode import WEB
        email = os.environ.get("ADMIN_EMAIL", "" if WEB else "admin@socsim.com").lower()
        weak = os.environ.get("ADMIN_PASSWORD", "Admin@123") == "Admin@123" or len(os.environ.get("ADMIN_PASSWORD", "")) < 10
        if WEB and (not email or weak):
            logger.warning("No admin account created: set ADMIN_EMAIL and a strong ADMIN_PASSWORD (10+ characters).")
        elif not await db.users.find_one({"email": email}):
            await db.users.insert_one({
                "id": str(uuid.uuid4()), "email": email, "name": "SOC Admin",
                "password_hash": hash_password(os.environ.get("ADMIN_PASSWORD", "Admin@123")),
                "role": "admin", "target_role": "SOC Analyst L2", "experience_level": "3–5 Years",
                "resume_summary": "", "created_at": datetime.now(timezone.utc),
            })
        for coll, items in (("personas", PERSONAS), ("company_templates", COMPANY_TEMPLATES),
                            ("scenarios", SCENARIOS), ("questions", build_questions())):
            if await db[coll].count_documents({}) == 0:
                await db[coll].insert_many([dict(i, created_at=datetime.now(timezone.utc)) for i in items])
                logger.info("seeded %s (%d)", coll, len(items))
        await _upsert_role_banks()
    except Exception as e:
        logger.error("seed_all failed: %s", e)


async def _upsert_role_banks() -> None:
    """Penetration Tester personas + the two 200-question banks (SOC Analyst L1-L3, Penetration Tester L1-L3),
    added to existing databases by id so admin edits are never overwritten."""
    import json
    from pathlib import Path
    data = Path(__file__).parent.parent / "data"
    items = [("personas", p) for p in PERSONAS if p.get("track") == "pentest"]
    for name in ("question_bank_soc200.json", "question_bank_pentest.json", "question_bank_skills.json"):
        if (data / name).exists():
            removed = removed_duplicates()
            items += [("questions", q) for q in json.loads((data / name).read_text(encoding="utf-8")) if q["id"] not in removed]
    added = 0
    for coll, doc in items:
        res = await db[coll].update_one({"id": doc["id"]}, {"$setOnInsert": dict(doc, created_at=datetime.now(timezone.utc))}, upsert=True)
        added += 1 if res.upserted_id else 0
    if added:
        logger.info("seeded role banks (%d new docs)", added)
    # Once: drop repeated questions from databases created before the cleanup.
    if not await db.settings.find_one({"key": "question_bank_dedupe"}):
        res = await db.questions.delete_many({"id": {"$in": sorted(removed_duplicates())}})
        logger.info("removed %d duplicate questions", res.deleted_count)
        await db.settings.update_one({"key": "question_bank_dedupe"}, {"$set": {"value": "v1"}}, upsert=True)
