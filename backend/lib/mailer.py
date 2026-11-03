"""Transactional email (password reset) through Resend's HTTP API when RESEND_API_KEY is set.

Without a key, emails are only written to the server log so the owner can still help a user by hand.
"""
import logging
import os

import httpx

logger = logging.getLogger(__name__)


async def send_email(to: str, subject: str, html: str, text: str) -> bool:
    key = (os.environ.get("RESEND_API_KEY") or "").strip()
    sender = os.environ.get("EMAIL_FROM") or "CyberHire <onboarding@resend.dev>"
    if not key:
        logger.warning("RESEND_API_KEY not set; email to %s not sent (subject: %s)", to, subject)
        return False
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post("https://api.resend.com/emails", headers={"Authorization": f"Bearer {key}"},
                             json={"from": sender, "to": [to], "subject": subject, "html": html, "text": text})
        if r.status_code >= 300:
            logger.error("email send failed (%s): %s", r.status_code, r.text[:300])
            return False
        return True
    except httpx.HTTPError as e:
        logger.error("email send failed: %s", e)
        return False
