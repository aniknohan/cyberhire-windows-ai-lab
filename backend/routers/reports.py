"""User reports about AI responses (Google Play requires in-app reporting for AI-generated content)."""
import html
import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from lib.auth import admin_user, current_user
from lib.db import db
from lib.limits import Window
from lib.mailer import send_email
from models.schemas import OkOut, ReportIn

router = APIRouter(tags=["reports"])
logger = logging.getLogger(__name__)
_PER_USER = Window(limit=20, seconds=86_400)


@router.post("/reports", response_model=OkOut)
async def report_ai_response(body: ReportIn, user: dict = Depends(current_user)):
    if not _PER_USER.hit(user["id"]):
        return OkOut()
    doc = {"id": str(uuid.uuid4()), "user_id": user["id"], "user_email": user.get("email"), "text": body.text.strip(),
           "interview_id": body.interview_id, "page": body.page, "status": "open", "created_at": datetime.now(timezone.utc)}
    await db.reports.insert_one(dict(doc))
    logger.warning("AI response reported by %s: %s", user.get("email"), doc["text"][:300])
    to = os.environ.get("SUPPORT_EMAIL")
    if to:
        await send_email(to, "CyberHire: an AI response was reported",
                         f"<p><b>{html.escape(user.get('email') or '')}</b> reported (page {html.escape(body.page or '')}, interview {html.escape(body.interview_id or '-')}):</p>"
                         f"<blockquote>{html.escape(doc['text'])}</blockquote>",
                         f"{user.get('email')} reported (page {body.page}, interview {body.interview_id}):\n\n{doc['text']}")
    return OkOut()


@router.get("/admin/reports")
async def list_reports(admin: dict = Depends(admin_user)):
    return await db.reports.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
