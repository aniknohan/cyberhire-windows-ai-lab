"""Google Play subscriptions: check a purchase with Google, acknowledge it, and map it to CyberHire Pro access.

Server settings:
  GOOGLE_PLAY_PACKAGE               the app's package name, e.g. io.github.aniknohan.cyberhire
  GOOGLE_PLAY_SERVICE_ACCOUNT_JSON  the JSON key of a Google Cloud service account that has access to the app in
                                    Play Console (Users and permissions: "View financial data" and
                                    "Manage orders and subscriptions")
  GOOGLE_PLAY_PRODUCT_ID            the subscription's product ID in Play Console (default cyberhire_pro)
  GOOGLE_PLAY_RTDN_TOKEN            optional: a secret added to the Pub/Sub push URL for real-time notifications
"""
import json
import logging
import os
import time
from datetime import datetime, timezone

import httpx
import jwt

logger = logging.getLogger(__name__)
SCOPE = "https://www.googleapis.com/auth/androidpublisher"
API = "https://androidpublisher.googleapis.com/androidpublisher/v3/applications"
_token: dict = {"value": None, "exp": 0.0}


class PlayError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


def package() -> str:
    return (os.environ.get("GOOGLE_PLAY_PACKAGE") or "").strip()


def product_id() -> str:
    return (os.environ.get("GOOGLE_PLAY_PRODUCT_ID") or "cyberhire_pro").strip()


def configured() -> bool:
    return bool(package() and os.environ.get("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON"))


def _service_account() -> dict:
    raw = os.environ.get("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON") or ""
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise PlayError("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON is not valid JSON", 503) from e


async def _access_token() -> str:
    if _token["value"] and _token["exp"] - 60 > time.time():
        return _token["value"]
    sa = _service_account()
    token_uri = sa.get("token_uri", "https://oauth2.googleapis.com/token")
    now = int(time.time())
    assertion = jwt.encode({"iss": sa["client_email"], "scope": SCOPE, "aud": token_uri, "iat": now, "exp": now + 3600},
                           sa["private_key"], algorithm="RS256")
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(token_uri, data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion})
    if r.status_code != 200:
        logger.error("Google token exchange failed: %s %s", r.status_code, r.text[:300])
        raise PlayError("Couldn't reach Google Play to check the subscription.")
    data = r.json()
    _token.update(value=data["access_token"], exp=time.time() + int(data.get("expires_in", 3600)))
    return _token["value"]


async def get_subscription(purchase_token: str) -> dict:
    """purchases.subscriptionsv2.get: the subscription's current state."""
    tok = await _access_token()
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(f"{API}/{package()}/purchases/subscriptionsv2/tokens/{purchase_token}", headers={"Authorization": f"Bearer {tok}"})
    if r.status_code in (400, 404, 410):
        raise PlayError("Google Play doesn't recognise this purchase.", 400)
    if r.status_code != 200:
        logger.error("subscriptionsv2.get failed: %s %s", r.status_code, r.text[:300])
        raise PlayError("Couldn't check the subscription with Google Play. Please try again.")
    return r.json()


async def acknowledge(product: str, purchase_token: str) -> None:
    """New purchases must be acknowledged within 3 days, or Google refunds them automatically."""
    tok = await _access_token()
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(f"{API}/{package()}/purchases/subscriptions/{product}/tokens/{purchase_token}:acknowledge",
                         headers={"Authorization": f"Bearer {tok}"}, json={})
    if r.status_code not in (200, 204):
        logger.error("acknowledge failed: %s %s", r.status_code, r.text[:300])


def _ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def interpret(sub: dict) -> dict:
    """Google's subscription resource → CyberHire entitlement fields."""
    state = sub.get("subscriptionState", "")
    items = sub.get("lineItems") or []
    item = max(items, key=lambda i: i.get("expiryTime", "")) if items else {}
    expiry = _ts(item.get("expiryTime"))
    offer_id = ((item.get("offerDetails") or {}).get("offerId") or "").lower()
    phase = item.get("offerPhase") or {}
    in_trial = ("freeTrial" in phase) or ("trial" in offer_id and not phase)
    future = bool(expiry and expiry > datetime.now(timezone.utc))
    if state in ("SUBSCRIPTION_STATE_ACTIVE", "SUBSCRIPTION_STATE_IN_GRACE_PERIOD"):
        status = "trialing" if in_trial else "active"
    elif state == "SUBSCRIPTION_STATE_CANCELED":  # cancelled, but the paid or trial time that's left still counts
        status = ("trialing" if in_trial else "active") if future else "canceled"
    elif state == "SUBSCRIPTION_STATE_ON_HOLD":
        status = "past_due"
    elif state == "SUBSCRIPTION_STATE_PAUSED":
        status = "paused"
    elif state in ("SUBSCRIPTION_STATE_PENDING", "SUBSCRIPTION_STATE_PENDING_PURCHASE_CANCELED"):
        status = "incomplete"
    else:
        status = "canceled"
    auto = (item.get("autoRenewingPlan") or {}).get("autoRenewEnabled")
    return {
        "status": status, "expiry": expiry, "product_id": item.get("productId") or product_id(),
        "cancel_at_period_end": state == "SUBSCRIPTION_STATE_CANCELED" or auto is False,
        "account_id": (sub.get("externalAccountIdentifiers") or {}).get("obfuscatedExternalAccountId"),
        "needs_ack": sub.get("acknowledgementState") == "ACKNOWLEDGEMENT_STATE_PENDING",
    }
