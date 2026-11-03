import hashlib
import html
import secrets
import uuid

import httpx
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from lib.answers import delete_audio
from lib.auth import clear_session, current_user, hash_password, set_session, verify_password
from lib.db import db
from lib.limits import AUTH_ATTEMPTS, RESET_EMAILS, SIGNUPS
from lib.mailer import send_email
from lib.mode import WEB, public_url
from routers.billing import cancel_all_for_deleted_account, require_ai
from lib.resume import extract_pdf_text, summarize_resume
from models.schemas import (DeleteAccountIn, ForgotIn, GoogleSessionIn, LoginIn, OkOut, ProfileUpdate, RegisterIn, ResetIn,
                            ResumeUploadIn, UserOut)

router = APIRouter(prefix="/auth", tags=["auth"])


def _out(u: dict) -> UserOut:
    return UserOut(**{k: u.get(k, "") for k in UserOut.model_fields})


def _ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return (fwd.split(",")[0].strip() if fwd else "") or (request.client.host if request.client else "?")


@router.post("/register", response_model=UserOut)
async def register(body: RegisterIn, response: Response, request: Request):
    email = body.email.lower()
    if WEB:
        SIGNUPS.check(_ip(request), "Too many new accounts from this network. Please try again later.")
        if len(body.password) < 8:
            raise HTTPException(status_code=422, detail="Use a password with at least 8 characters.")
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = {
        "id": str(uuid.uuid4()), "email": email, "name": body.name.strip(),
        "password_hash": hash_password(body.password), "role": "candidate",
        "target_role": body.target_role, "experience_level": body.experience_level,
        "resume_summary": "", "created_at": datetime.now(timezone.utc),
    }
    await db.users.insert_one(user)
    set_session(response, user["id"], request)
    return _out(user)


@router.post("/login", response_model=UserOut)
async def login(body: LoginIn, response: Response, request: Request):
    AUTH_ATTEMPTS.check(f"login:{_ip(request)}:{body.email.lower()}", "Too many sign-in attempts. Please wait 15 minutes and try again.")
    user = await db.users.find_one({"email": body.email.lower()})
    if user and not user.get("password_hash"):
        raise HTTPException(status_code=401, detail="This account has no password yet. Use 'Forgot password?' to set one.")
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    set_session(response, user["id"], request)
    return _out(user)


EMERGENT_SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"


@router.post("/google", response_model=UserOut)
async def google_session(body: GoogleSessionIn, response: Response, request: Request):
    """Exchange the one-time Emergent Google session_id (server-side only) for our own session cookie.
    Users are linked by email, so an existing email/password account gains Google sign-in.
    Only for the original Emergent-hosted site; the self-hosted website and desktop app use email + password."""
    if WEB or not __import__("os").environ.get("EMERGENT_GOOGLE_LOGIN"):
        raise HTTPException(status_code=404, detail="Google sign-in isn't available. Sign in with your email and password.")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(EMERGENT_SESSION_URL, headers={"X-Session-ID": body.session_id})
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Google sign-in is temporarily unavailable")
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Google sign-in failed or expired — please try again")
    data = r.json()
    email = str(data.get("email") or "").lower()
    if not email:
        raise HTTPException(status_code=401, detail="Google account has no email")
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if user:
        upd = {"google_id": data.get("id"), "picture": data.get("picture", "")}
        await db.users.update_one({"id": user["id"]}, {"$set": upd})
        user.update(upd)
    else:
        user = {
            "id": str(uuid.uuid4()), "email": email, "name": data.get("name") or email.split("@")[0],
            "password_hash": None, "role": "candidate", "google_id": data.get("id"), "picture": data.get("picture", ""),
            "target_role": "SOC Analyst L1", "experience_level": "Entry Level", "resume_summary": "",
            "created_at": datetime.now(timezone.utc),
        }
        await db.users.insert_one(dict(user))
    set_session(response, user["id"], request)
    return _out(user)


@router.post("/logout", response_model=OkOut)
async def logout(response: Response):
    clear_session(response)
    return OkOut()


@router.get("/me", response_model=UserOut)
async def me(user: dict = Depends(current_user)):
    return _out(user)


@router.put("/profile", response_model=UserOut)
async def update_profile(body: ProfileUpdate, user: dict = Depends(current_user)):
    await db.users.update_one({"id": user["id"]}, {"$set": body.model_dump()})
    return _out({**user, **body.model_dump()})


@router.post("/resume", response_model=UserOut)
async def upload_resume(body: ResumeUploadIn, user: dict = Depends(require_ai)):
    text = extract_pdf_text(body.pdf_b64)
    summary = await summarize_resume(text)
    upd = {"resume_summary": summary, "resume_filename": body.filename, "resume_text": text,
           "resume_uploaded_at": datetime.now(timezone.utc)}
    await db.users.update_one({"id": user["id"]}, {"$set": upd})
    return _out({**user, **upd})


@router.delete("/resume", response_model=UserOut)
async def delete_resume(user: dict = Depends(current_user)):
    upd = {"resume_summary": "", "resume_filename": "", "resume_text": ""}
    await db.users.update_one({"id": user["id"]}, {"$set": upd})
    return _out({**user, **upd})


# ---------------- password reset ----------------
RESET_TTL = timedelta(hours=1)


def _hash_token(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


@router.post("/forgot", response_model=OkOut)
async def forgot_password(body: ForgotIn, request: Request):
    """Always answers OK so the form never reveals whether an email has an account."""
    email = body.email.lower()
    AUTH_ATTEMPTS.check("forgot:" + _ip(request), "Too many requests. Please wait a few minutes.")
    if not RESET_EMAILS.hit(email):
        return OkOut()
    user = await db.users.find_one({"email": email}, {"_id": 0, "id": 1, "name": 1})
    if user:
        token = secrets.token_urlsafe(32)
        await db.password_resets.insert_one({"token_hash": _hash_token(token), "user_id": user["id"],
                                             "expires_at": datetime.now(timezone.utc) + RESET_TTL, "used": False})
        base = public_url() or str(request.base_url).rstrip("/")
        link = f"{base}/reset-password?token={token}"
        name = html.escape(user.get("name") or "there")
        await send_email(email, "Reset your CyberHire password",
                         f"<p>Hi {name},</p><p>Someone asked to reset the password for your CyberHire account. "
                         f"<a href=\"{link}\">Choose a new password</a>. The link works for 1 hour.</p>"
                         "<p>If this wasn't you, you can ignore this email; your password stays the same.</p>",
                         f"Hi {user.get('name') or 'there'},\n\nReset your CyberHire password (link valid for 1 hour):\n{link}\n\n"
                         "If this wasn't you, ignore this email.")
    return OkOut()


@router.post("/reset", response_model=OkOut)
async def reset_password(body: ResetIn, request: Request):
    AUTH_ATTEMPTS.check("reset:" + _ip(request), "Too many attempts. Please wait a few minutes.")
    rec = await db.password_resets.find_one({"token_hash": _hash_token(body.token)}, {"_id": 0})
    exp = rec and rec.get("expires_at")
    if exp is not None and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if not rec or rec.get("used") or not exp or exp < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired. Ask for a new one.")
    await db.users.update_one({"id": rec["user_id"]}, {"$set": {"password_hash": hash_password(body.password),
                                                               "password_changed_at": datetime.now(timezone.utc)}})
    await db.password_resets.update_one({"token_hash": rec["token_hash"]}, {"$set": {"used": True}})
    return OkOut()


# ---------------- account deletion (also required by Google Play for apps with accounts) ----------------
@router.post("/delete-account", response_model=OkOut)
async def delete_account(body: DeleteAccountIn, response: Response, user: dict = Depends(current_user)):
    if body.confirm.strip().upper() != "DELETE":
        raise HTTPException(status_code=400, detail='Type DELETE to confirm.')
    if user.get("password_hash") and not verify_password(body.password or "", user["password_hash"]):
        raise HTTPException(status_code=401, detail="That password isn't right.")
    if user.get("role") == "admin":
        raise HTTPException(status_code=400, detail="The admin account can't be deleted here.")
    await cancel_all_for_deleted_account(user)
    uid = user["id"]
    async for r in db.responses.find({"user_id": uid}, {"audio_path": 1}):
        delete_audio(r.get("audio_path"))
    iv_ids = [iv["id"] async for iv in db.interviews.find({"user_id": uid}, {"id": 1})]
    if iv_ids:
        await db.turns.delete_many({"interview_id": {"$in": iv_ids}})
    for coll in ("responses", "interviews", "practice_sessions", "drills", "password_resets"):
        await db[coll].delete_many({"user_id": uid})
    await db.payment_transactions.update_many({"user_id": uid}, {"$set": {"user_deleted": True}})  # keep for accounting
    await db.users.delete_one({"id": uid})
    clear_session(response)
    return OkOut()
