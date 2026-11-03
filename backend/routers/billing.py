"""Billing.

Desktop app (SOC_MODE unset): free, every feature unlocked.

Website (SOC_MODE=web): CyberHire Pro is $19.99/month or $159/year. New subscribers start a TRIAL_DAYS free trial
with a card on file (Stripe Checkout, or Google Play in the Android app); the first charge happens when the trial
ends unless they cancel. One free trial per account.

Entitlement lives on the user document, whichever store sold it:
  plan ("pro"/"free"), pro_until (end of the paid or trial period), subscription_status (trialing/active/...),
  billing_provider ("stripe" | "google_play" | "paypal"), billing_interval, cancel_at_period_end, trial_used,
  stripe_customer_id / stripe_subscription_id, play_purchase_token / play_product_id.
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

import httpx
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request

from lib import google_play as play
from lib.auth import current_user
from lib.db import db
from lib.limits import AI_CALLS_PER_DAY, AI_CALLS_PER_MINUTE
from lib.mode import WEB, env_int, public_url
from models.schemas import BillingStatus, CheckoutIn, CheckoutOut, OkOut, PaymentStatusOut, PlayVerifyIn, PortalOut

router = APIRouter(tags=["billing"])
logger = logging.getLogger(__name__)
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY") or ""
if os.environ.get("STRIPE_API_BASE"):  # tests: point the SDK at stripe-mock
    stripe.api_base = os.environ["STRIPE_API_BASE"]
PLANS = {
    "month": {"lookup_key": "pro_monthly", "amount": "19.99", "label": "$19.99 / month", "paypal_name": "Pro Monthly", "paypal_unit": "MONTH", "days": 31},
    "year": {"lookup_key": "pro_yearly", "amount": "159.00", "label": "$159 / year", "paypal_name": "Pro Yearly", "paypal_unit": "YEAR", "days": 366},
}
TRIAL_DAYS = env_int("TRIAL_DAYS", 3)
TRIAL_INTERVIEW_LIMIT = env_int("TRIAL_INTERVIEW_LIMIT", 3)        # interviews allowed during the free trial
MONTHLY_INTERVIEW_LIMIT = env_int("MONTHLY_INTERVIEW_LIMIT", 60)   # fair use for paying members, per 30 days
ACTIVE = ("trialing", "active")
GRACE = timedelta(hours=2)


def now():
    return datetime.now(timezone.utc)


def _aware(dt):
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def local_pro() -> bool:
    """The desktop app is free: every account on the computer has every feature."""
    return not WEB


def _free_access(user: dict) -> bool:
    """FREE_ACCESS_EMAILS: comma-separated accounts with full access and no limits (e.g. the Google Play reviewer)."""
    allowed = {e.strip().lower() for e in os.environ.get("FREE_ACCESS_EMAILS", "").split(",") if e.strip()}
    return (user.get("email") or "").lower() in allowed


def is_paid_pro(user: dict) -> bool:
    if local_pro() or user.get("role") == "admin" or _free_access(user):
        return True
    until = _aware(user.get("pro_until"))
    return user.get("plan") == "pro" and until is not None and until > now()


def on_trial(user: dict) -> bool:
    return WEB and user.get("role") != "admin" and is_paid_pro(user) and user.get("subscription_status") == "trialing"


def has_access(user: dict) -> bool:
    return is_paid_pro(user)


def trial_until(user: dict) -> datetime | None:
    return _aware(user.get("pro_until")) if on_trial(user) else None


NO_PLAN_MSG = f"Start your {TRIAL_DAYS}-day free trial to practice with CyberHire Pro."
EXPIRED_MSG = "Your CyberHire Pro subscription isn't active. Subscribe to keep practicing."


def _no_access_msg(user: dict) -> str:
    return EXPIRED_MSG if user.get("trial_used") else NO_PLAN_MSG


async def _interviews_since(user_id: str, since: datetime) -> int:
    return await db.interviews.count_documents({"user_id": user_id, "created_at": {"$gte": since}})


async def usage(user: dict) -> tuple[int, int | None]:
    """(interviews used in the current allowance window, allowance) — allowance None means unlimited."""
    if not WEB or user.get("role") == "admin" or _free_access(user):
        return 0, None
    if on_trial(user):
        start = _aware(user.get("trial_started_at")) or now() - timedelta(days=TRIAL_DAYS)
        return await _interviews_since(user["id"], start), TRIAL_INTERVIEW_LIMIT
    return await _interviews_since(user["id"], now() - timedelta(days=30)), MONTHLY_INTERVIEW_LIMIT


async def require_interview_allowance(user: dict) -> None:
    if not has_access(user):
        raise HTTPException(status_code=402, detail=_no_access_msg(user))
    used, limit = await usage(user)
    if limit is not None and used >= limit:
        if on_trial(user):
            raise HTTPException(status_code=429, detail=f"You've used the {limit} interviews included in the free trial. "
                                                        "Your plan starts automatically when the trial ends, or you can keep practising in Practice.")
        raise HTTPException(status_code=429, detail=f"You've reached the fair-use limit of {limit} interviews in 30 days. It resets as older interviews age out.")


async def require_pro(user: dict = Depends(current_user)) -> dict:
    if not has_access(user):
        raise HTTPException(status_code=402, detail=_no_access_msg(user))
    return user


async def require_ai(user: dict = Depends(current_user)) -> dict:
    """For every route that calls the AI on the owner's key: an active plan, and a per-user rate limit."""
    if not WEB:
        return user
    if not has_access(user):
        raise HTTPException(status_code=402, detail=_no_access_msg(user))
    if user.get("role") != "admin":
        AI_CALLS_PER_MINUTE.check(user["id"], "You're going a little fast. Wait a few seconds and try again.")
        AI_CALLS_PER_DAY.check(user["id"], "You've reached today's fair-use limit. It resets within 24 hours.")
    return user


# ---------------- entitlement updates (shared by Stripe and Google Play) ----------------
async def set_entitlement(user_id: str, provider: str, status: str, until: datetime | None, **fields) -> None:
    active = status in ACTIVE and until is not None and until > now()
    upd = {"plan": "pro" if active else "free", "subscription_status": status, "billing_provider": provider,
           "pro_until": (until + GRACE) if active else min(until or now(), now()),
           "trial_used": True,  # anyone who has had a subscription (trial or paid) isn't offered another free trial
           **fields}
    await db.users.update_one({"id": user_id}, {"$set": upd})


def _stripe_ready() -> None:
    if not stripe.api_key:
        raise HTTPException(status_code=503, detail="Payments aren't set up yet. Please try again later.")


def _plain(o):
    """Stripe objects → plain dicts/lists, recursively."""
    if hasattr(o, "items"):
        return {k: _plain(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_plain(v) for v in o]
    return o


def _period_end(sub: dict) -> int | None:
    end = sub.get("current_period_end")
    if not end:
        items = (sub.get("items") or {}).get("data") or []
        end = items[0].get("current_period_end") if items else None
    if sub.get("status") == "trialing" and sub.get("trial_end"):
        end = max(end or 0, sub["trial_end"])
    return end


def _interval(sub: dict) -> str:
    items = (sub.get("items") or {}).get("data") or []
    rec = ((items[0].get("price") or {}).get("recurring") or {}) if items else {}
    return "year" if rec.get("interval") == "year" else "month"


async def sync_stripe_subscription(sub) -> None:
    """Copy a Stripe subscription's state onto its user. Safe to run repeatedly (webhooks retry)."""
    sub = _plain(sub)
    uid = (sub.get("metadata") or {}).get("user_id")
    user = await db.users.find_one({"id": uid}, {"_id": 0}) if uid else None
    if not user:
        user = await db.users.find_one({"stripe_subscription_id": sub.get("id")}, {"_id": 0})
    if not user and sub.get("customer"):
        user = await db.users.find_one({"stripe_customer_id": sub["customer"]}, {"_id": 0})
    if not user:
        logger.warning("stripe subscription %s has no matching user", sub.get("id"))
        return
    status = sub.get("status") or "canceled"
    # A newer active subscription from another store is never overwritten by an ended Stripe one.
    if status not in ACTIVE and user.get("billing_provider") not in (None, "stripe") and is_paid_pro(user):
        return
    if status not in ACTIVE and user.get("stripe_subscription_id") not in (None, sub.get("id")) and is_paid_pro(user):
        return
    end = _period_end(sub)
    until = datetime.fromtimestamp(end, tz=timezone.utc) if end else None
    fields = {"stripe_subscription_id": sub.get("id"), "stripe_customer_id": sub.get("customer"),
              "billing_interval": _interval(sub), "cancel_at_period_end": bool(sub.get("cancel_at_period_end") or sub.get("cancel_at"))}
    if status == "trialing" and not user.get("trial_started_at"):
        fields["trial_started_at"] = now()
    await set_entitlement(user["id"], "stripe", status, until, **fields)


async def _retrieve_and_sync(sub_id: str | None) -> None:
    if not sub_id:
        return
    try:
        sub = await asyncio.to_thread(stripe.Subscription.retrieve, sub_id)
    except stripe.StripeError as e:
        logger.warning("subscription retrieve failed: %s", e)
        return
    await sync_stripe_subscription(sub)


# ---------------- Google Play ----------------
async def sync_play_purchase(user: dict, purchase_token: str) -> dict:
    """Check a Google Play subscription with Google and copy its state onto the user. Returns the updated user."""
    if not play.configured():
        raise HTTPException(status_code=503, detail="Google Play subscriptions aren't set up on the server yet.")
    owner = await db.users.find_one({"play_purchase_token": purchase_token}, {"_id": 0, "id": 1})
    if owner and owner["id"] != user["id"]:
        raise HTTPException(status_code=409, detail="This Google Play subscription belongs to another CyberHire account. Sign in with that account.")
    try:
        info = play.interpret(await play.get_subscription(purchase_token))
    except play.PlayError as e:
        raise HTTPException(status_code=e.status, detail=str(e))
    if info["account_id"] and info["account_id"] != user["id"]:
        raise HTTPException(status_code=409, detail="This Google Play subscription belongs to another CyberHire account. Sign in with that account.")
    # A newer active Stripe subscription is never replaced by an ended Play one.
    if info["status"] not in ACTIVE and user.get("billing_provider") == "stripe" and is_paid_pro(user):
        return user
    fields = {"play_purchase_token": purchase_token, "play_product_id": info["product_id"], "play_checked_at": now(),
              "cancel_at_period_end": info["cancel_at_period_end"], "billing_interval": "month"}
    if info["status"] == "trialing" and not user.get("trial_started_at"):
        fields["trial_started_at"] = now()
    await set_entitlement(user["id"], "google_play", info["status"], info["expiry"], **fields)
    if info["needs_ack"] and info["status"] in ACTIVE:
        await play.acknowledge(info["product_id"], purchase_token)
    return await db.users.find_one({"id": user["id"]}, {"_id": 0}) or user


@router.post("/billing/google-play/verify", response_model=OkOut)
async def play_verify(body: PlayVerifyIn, user: dict = Depends(current_user)):
    """Called by the Android app right after a purchase, and on "Restore purchase"."""
    await sync_play_purchase(user, body.purchase_token)
    return OkOut()


async def _refresh_play_if_due(user: dict) -> dict:
    """Renewals, cancellations and expiries happen at Google: re-check a Play subscription every few hours
    and whenever its period has run out, so access always matches what Google says."""
    if user.get("billing_provider") != "google_play" or not user.get("play_purchase_token") or not play.configured():
        return user
    checked = _aware(user.get("play_checked_at"))
    until = _aware(user.get("pro_until"))
    due = checked is None or now() - checked > timedelta(hours=6) or (until is not None and until <= now() and now() - checked > timedelta(minutes=5))
    if not due:
        return user
    try:
        return await sync_play_purchase(user, user["play_purchase_token"])
    except HTTPException as e:
        logger.warning("Play refresh for %s failed: %s", user.get("id"), e.detail)
        await db.users.update_one({"id": user["id"]}, {"$set": {"play_checked_at": now()}})
        return user


@router.post("/billing/google-play/rtdn")
async def play_rtdn(request: Request, token: str = ""):
    """Optional: Google Play real-time developer notifications (Pub/Sub push subscription) for instant updates."""
    secret = os.environ.get("GOOGLE_PLAY_RTDN_TOKEN", "")
    if not secret or token != secret:
        raise HTTPException(status_code=403, detail="Forbidden")
    import base64
    import json as _json
    try:
        msg = (await request.json()).get("message") or {}
        data = _json.loads(base64.b64decode(msg.get("data") or "e30=").decode() or "{}")
    except Exception:
        return {"status": "ignored"}
    ptoken = (data.get("subscriptionNotification") or {}).get("purchaseToken")
    if ptoken:
        u = await db.users.find_one({"play_purchase_token": ptoken}, {"_id": 0})
        if u:
            try:
                await sync_play_purchase(u, ptoken)
            except HTTPException as e:
                logger.warning("RTDN sync failed: %s", e.detail)
    return {"status": "ok"}


@router.get("/billing/status", response_model=BillingStatus)
async def billing_status(user: dict = Depends(current_user)):
    user = await _refresh_play_if_due(user)
    paid, trial = is_paid_pro(user), on_trial(user)
    used, limit = await usage(user)
    return BillingStatus(
        mode="web" if WEB else "desktop",
        plan="trial" if trial else "pro" if paid else ("expired" if user.get("trial_used") else "none"),
        is_pro=paid, has_access=paid, on_trial=trial, trial_until=trial_until(user), trial_days=TRIAL_DAYS,
        trial_available=WEB and not user.get("trial_used"),
        pro_until=_aware(user.get("pro_until")) if paid else None, provider=user.get("billing_provider"),
        interval=user.get("billing_interval"), cancel_at_period_end=bool(user.get("cancel_at_period_end")),
        monthly_price_label=PLANS["month"]["label"], yearly_price_label=PLANS["year"]["label"],
        stripe_enabled=bool(stripe.api_key), play_enabled=play.configured(), play_product_id=play.product_id(), paypal_enabled=bool(os.environ.get("PAYPAL_CLIENT_ID") and os.environ.get("PAYPAL_SECRET")),
        interviews_used=used, interviews_limit=limit,
    )


# ---------------- Stripe ----------------
def _origin(body_origin: str) -> str:
    return public_url() or body_origin.rstrip("/")


@router.post("/billing/stripe/checkout", response_model=CheckoutOut)
async def stripe_checkout(body: CheckoutIn, user: dict = Depends(current_user)):
    _stripe_ready()
    if is_paid_pro(user) and user.get("role") != "admin" and WEB:
        raise HTTPException(status_code=409, detail="You already have CyberHire Pro. Manage it from your Profile.")
    plan = PLANS[body.interval]
    prices = await asyncio.to_thread(lambda: stripe.Price.list(lookup_keys=[plan["lookup_key"]], active=True, limit=1).data)
    if not prices:
        raise HTTPException(status_code=503, detail="The Pro plan price isn't set up yet.")
    price = prices[0]
    origin = _origin(body.origin_url)
    sub_data = {"metadata": {"user_id": user["id"]}}
    if not user.get("trial_used") and TRIAL_DAYS > 0:
        sub_data["trial_period_days"] = TRIAL_DAYS
    kwargs = dict(
        line_items=[{"price": price.id, "quantity": 1}], mode="subscription", payment_method_collection="always",
        success_url=f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}", cancel_url=f"{origin}/pricing?checkout=cancelled",
        client_reference_id=user["id"], allow_promotion_codes=True,
        metadata={"user_id": user["id"], "lookup_key": plan["lookup_key"], "interval": body.interval},
        subscription_data=sub_data,
    )
    if user.get("stripe_customer_id"):
        kwargs["customer"] = user["stripe_customer_id"]
    else:
        kwargs["customer_email"] = user["email"]
    if os.environ.get("STRIPE_AUTOMATIC_TAX") == "1":
        kwargs["automatic_tax"] = {"enabled": True}
        kwargs["billing_address_collection"] = "required"
        if user.get("stripe_customer_id"):
            kwargs["customer_update"] = {"address": "auto"}
    try:
        session = await asyncio.to_thread(lambda: stripe.checkout.Session.create(**kwargs))
    except stripe.StripeError as e:
        logger.error("stripe checkout failed: %s", e)
        raise HTTPException(status_code=502, detail="Could not start checkout. Please try again.")
    await db.payment_transactions.insert_one({
        "session_id": session.id, "user_id": user["id"], "provider": "stripe", "lookup_key": plan["lookup_key"], "interval": body.interval,
        "amount": (price.unit_amount or 0) / 100.0, "currency": price.currency, "trial": "trial_period_days" in sub_data,
        "status": "initiated", "payment_status": "pending", "created_at": now(), "updated_at": now(),
    })
    return CheckoutOut(checkout_url=session.url, session_id=session.id)


@router.get("/payments/status/{session_id}", response_model=PaymentStatusOut)
async def payment_status(session_id: str, user: dict = Depends(current_user)):
    rec = await db.payment_transactions.find_one({"session_id": session_id, "user_id": user["id"]}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if rec.get("payment_status") != "paid" and rec.get("provider") == "stripe" and stripe.api_key:
        try:
            s = await asyncio.to_thread(stripe.checkout.Session.retrieve, session_id)
            if s.status == "complete":
                await db.payment_transactions.update_one({"session_id": session_id}, {"$set": {
                    "status": "completed", "payment_status": "paid", "stripe_subscription_id": s.subscription, "updated_at": now()}})
                if s.customer:
                    await db.users.update_one({"id": user["id"]}, {"$set": {"stripe_customer_id": s.customer}})
                await _retrieve_and_sync(s.subscription)
                rec = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
            elif s.status == "expired":
                await db.payment_transactions.update_one({"session_id": session_id}, {"$set": {"status": "expired", "payment_status": "expired"}})
                rec["status"], rec["payment_status"] = "expired", "expired"
        except stripe.StripeError:
            pass
    return PaymentStatusOut(session_id=session_id, status=rec["status"], payment_status=rec["payment_status"])


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    if not secret:
        raise HTTPException(status_code=503, detail="Webhook secret not configured")
    try:
        event = stripe.Webhook.construct_event(payload, request.headers.get("stripe-signature", ""), secret)
    except (stripe.SignatureVerificationError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid signature")
    obj, t = event["data"]["object"], event["type"]
    if t == "checkout.session.completed":
        await db.payment_transactions.update_one({"session_id": obj["id"]}, {"$set": {
            "status": "completed", "payment_status": "paid", "stripe_subscription_id": obj.get("subscription"), "updated_at": now()}})
        uid = (obj.get("metadata") or {}).get("user_id") or obj.get("client_reference_id")
        if uid and obj.get("customer"):
            await db.users.update_one({"id": uid}, {"$set": {"stripe_customer_id": obj["customer"]}})
        await _retrieve_and_sync(obj.get("subscription"))
    elif t == "checkout.session.expired":
        await db.payment_transactions.update_one({"session_id": obj["id"]}, {"$set": {"status": "expired", "payment_status": "expired", "updated_at": now()}})
    elif t in ("customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted",
               "customer.subscription.paused", "customer.subscription.resumed"):
        await sync_stripe_subscription(obj)
    elif t in ("invoice.paid", "invoice.payment_succeeded", "invoice.payment_failed"):
        sub_id = obj.get("subscription") or ((obj.get("parent") or {}).get("subscription_details") or {}).get("subscription")
        await _retrieve_and_sync(sub_id)
    return {"status": "ok"}


@router.post("/billing/portal", response_model=PortalOut)
async def billing_portal(user: dict = Depends(current_user)):
    """Stripe's hosted page where members update their card, switch plan, see invoices or cancel."""
    _stripe_ready()
    if user.get("billing_provider") == "google_play":
        raise HTTPException(status_code=400, detail="Your subscription is billed by Google Play. Manage it in the Play Store app → Payments & subscriptions.")
    if not user.get("stripe_customer_id"):
        raise HTTPException(status_code=400, detail="No subscription to manage yet.")
    try:
        s = await asyncio.to_thread(lambda: stripe.billing_portal.Session.create(
            customer=user["stripe_customer_id"], return_url=f"{public_url() or ''}/profile" if public_url() else None))
    except stripe.StripeError as e:
        logger.error("billing portal failed: %s", e)
        raise HTTPException(status_code=502, detail="Could not open the billing page. Please try again.")
    return PortalOut(url=s.url)


@router.post("/billing/cancel", response_model=OkOut)
async def cancel_subscription(user: dict = Depends(current_user)):
    provider = user.get("billing_provider")
    if provider == "stripe" and user.get("stripe_subscription_id"):
        _stripe_ready()
        sub = await asyncio.to_thread(stripe.Subscription.modify, user["stripe_subscription_id"], cancel_at_period_end=True)
        await sync_stripe_subscription(sub)
    elif provider == "google_play":
        raise HTTPException(status_code=400, detail="Your subscription is billed by Google Play. Cancel it in the Play Store app → Payments & subscriptions.")
    elif provider == "paypal" and user.get("paypal_subscription_id"):
        token = await _paypal_token()
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(f"{_paypal_base()}/v1/billing/subscriptions/{user['paypal_subscription_id']}/cancel",
                             headers={"Authorization": f"Bearer {token}"}, json={"reason": "Cancelled by customer"})
        if r.status_code not in (204, 422):
            raise HTTPException(status_code=502, detail="PayPal cancellation failed")
    else:
        raise HTTPException(status_code=400, detail="No active subscription")
    await db.users.update_one({"id": user["id"]}, {"$set": {"cancel_at_period_end": True}})
    return OkOut()


async def cancel_all_for_deleted_account(user: dict) -> None:
    """Account deletion: end any Stripe subscription immediately so the person is never charged again."""
    if user.get("stripe_subscription_id") and stripe.api_key:
        try:
            await asyncio.to_thread(stripe.Subscription.cancel, user["stripe_subscription_id"])
        except stripe.StripeError as e:
            logger.warning("cancel on account deletion failed: %s", e)


async def _activate(user_id: str, provider: str, until: datetime, **ids) -> None:
    await set_entitlement(user_id, provider, "active", until, **ids)


# ---------------- PayPal (enabled when PAYPAL_CLIENT_ID + PAYPAL_SECRET are set) ----------------
def _paypal_base() -> str:
    return "https://api-m.paypal.com" if os.environ.get("PAYPAL_MODE") == "live" else "https://api-m.sandbox.paypal.com"


async def _paypal_token() -> str:
    cid, sec = os.environ.get("PAYPAL_CLIENT_ID"), os.environ.get("PAYPAL_SECRET")
    if not (cid and sec):
        raise HTTPException(status_code=503, detail="PayPal isn't set up yet — please pay with card for now.")
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{_paypal_base()}/v1/oauth2/token", auth=(cid, sec), data={"grant_type": "client_credentials"})
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="PayPal authentication failed")
    return r.json()["access_token"]


async def _paypal_plan_id(token: str, interval: str) -> str:
    plan = PLANS[interval]
    key = f"paypal_plan_{interval}_{_paypal_base()}"
    cfg = await db.settings.find_one({"key": key}, {"_id": 0})
    if cfg:
        return cfg["value"]
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=20) as c:
        prod = await c.post(f"{_paypal_base()}/v1/catalogs/products", headers=h,
                            json={"name": "CyberHire Pro", "type": "SERVICE", "category": "SOFTWARE"})
        plan = await c.post(f"{_paypal_base()}/v1/billing/plans", headers=h, json={
            "product_id": prod.json()["id"], "name": plan["paypal_name"],
            "billing_cycles": [{"frequency": {"interval_unit": plan["paypal_unit"], "interval_count": 1}, "tenure_type": "REGULAR", "sequence": 1,
                                "total_cycles": 0, "pricing_scheme": {"fixed_price": {"value": plan["amount"], "currency_code": "USD"}}}],
            "payment_preferences": {"auto_bill_outstanding": True, "payment_failure_threshold": 2}})
    if plan.status_code not in (200, 201):
        raise HTTPException(status_code=502, detail="Could not create PayPal plan")
    pid = plan.json()["id"]
    await db.settings.update_one({"key": key}, {"$set": {"value": pid}}, upsert=True)
    return pid


@router.post("/billing/paypal/checkout", response_model=CheckoutOut)
async def paypal_checkout(body: CheckoutIn, user: dict = Depends(current_user)):
    token = await _paypal_token()
    plan_id = await _paypal_plan_id(token, body.interval)
    origin = body.origin_url.rstrip("/")
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{_paypal_base()}/v1/billing/subscriptions", headers={"Authorization": f"Bearer {token}"}, json={
            "plan_id": plan_id, "custom_id": user["id"],
            "application_context": {"brand_name": "CyberHire", "user_action": "SUBSCRIBE_NOW",
                                    "return_url": f"{origin}/payment/success?provider=paypal", "cancel_url": f"{origin}/payment/cancel"}})
    if r.status_code not in (200, 201):
        raise HTTPException(status_code=502, detail="Could not start PayPal checkout")
    sub = r.json()
    approve = next((link["href"] for link in sub.get("links", []) if link.get("rel") == "approve"), None)
    await db.payment_transactions.insert_one({"session_id": sub["id"], "user_id": user["id"], "provider": "paypal", "interval": body.interval, "amount": float(PLANS[body.interval]["amount"]),
                                              "currency": "usd", "status": "initiated", "payment_status": "pending", "created_at": now(), "updated_at": now()})
    return CheckoutOut(checkout_url=approve or "", session_id=sub["id"])


@router.post("/billing/paypal/confirm/{subscription_id}", response_model=PaymentStatusOut)
async def paypal_confirm(subscription_id: str, user: dict = Depends(current_user)):
    rec = await db.payment_transactions.find_one({"session_id": subscription_id, "user_id": user["id"]}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Subscription not found")
    token = await _paypal_token()
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(f"{_paypal_base()}/v1/billing/subscriptions/{subscription_id}", headers={"Authorization": f"Bearer {token}"})
    data = r.json() if r.status_code == 200 else {}
    if data.get("status") == "ACTIVE":
        nxt = (data.get("billing_info") or {}).get("next_billing_time")
        interval = rec.get("interval", "month")
        until = datetime.fromisoformat(nxt.replace("Z", "+00:00")) if nxt else now() + timedelta(days=PLANS[interval]["days"])
        await db.payment_transactions.update_one({"session_id": subscription_id}, {"$set": {"status": "completed", "payment_status": "paid", "updated_at": now()}})
        await _activate(user["id"], "paypal", until, billing_interval=interval, paypal_subscription_id=subscription_id)
        return PaymentStatusOut(session_id=subscription_id, status="completed", payment_status="paid")
    return PaymentStatusOut(session_id=subscription_id, status=rec["status"], payment_status=rec["payment_status"])
