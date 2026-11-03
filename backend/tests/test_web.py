"""Website (SOC_MODE=web) billing, access and account tests. Stripe API calls go to stripe-mock."""
import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import server
from lib.db import db

WH = "whsec_test_secret"


@pytest.fixture(scope="module")
def client():
    with TestClient(server.app) as c:
        yield c


def new_user(client, email=None, password="correct-horse-1"):
    email = email or f"u{uuid.uuid4().hex[:8]}@example.com"
    c = TestClient(server.app)
    r = c.post("/api/auth/register", json={"email": email, "password": password, "name": "Test User"})
    assert r.status_code == 200, r.text
    return c, r.json(), email


def signed(event: dict) -> tuple[bytes, dict]:
    payload = json.dumps(event).encode()
    t = int(time.time())
    sig = hmac.new(WH.encode(), f"{t}.".encode() + payload, hashlib.sha256).hexdigest()
    return payload, {"stripe-signature": f"t={t},v1={sig}", "content-type": "application/json"}


def sub_event(kind: str, user_id: str, status: str, sub_id: str, days=3, interval="month", cancel=False):
    end = int((datetime.now(timezone.utc) + timedelta(days=days)).timestamp())
    return {"id": "evt_" + uuid.uuid4().hex, "object": "event", "type": kind, "data": {"object": {
        "id": sub_id, "object": "subscription", "status": status, "customer": "cus_" + user_id[:8], "metadata": {"user_id": user_id},
        "cancel_at_period_end": cancel, "trial_end": end if status == "trialing" else None,
        "items": {"data": [{"current_period_end": end, "price": {"recurring": {"interval": interval}}}]}}}}


def post_webhook(client, event):
    payload, headers = signed(event)
    return client.post("/api/stripe/webhook", content=payload, headers=headers)


def test_public_config(client):
    r = client.get("/api/config")
    assert r.status_code == 200
    assert r.json()["mode"] == "web" and r.json()["trial_days"] == 3 and r.json()["google_login"] is False


def test_docs_hidden_in_web_mode(client):
    assert '"paths"' not in client.get("/openapi.json").text


def test_short_password_rejected():
    c = TestClient(server.app)
    r = c.post("/api/auth/register", json={"email": "short@example.com", "password": "1234567", "name": "S"})
    assert r.status_code == 422


def test_new_user_has_no_access_and_trial_available(client):
    c, u, _ = new_user(client)
    b = c.get("/api/billing/status").json()
    assert b["mode"] == "web" and b["plan"] == "none" and not b["has_access"] and b["trial_available"]
    r = c.post("/api/interviews", json={"position": "SOC Analyst L1", "experience": "Entry Level", "difficulty": "Realistic / Adaptive", "environment": "random", "mode": "quick"})
    assert r.status_code == 402, r.text
    assert "free trial" in r.json()["detail"]
    assert c.post("/api/voice/tts", json={"text": "hi", "persona_id": "p-jessica"}).status_code == 402


def test_checkout_with_trial_against_stripe_mock(client):
    c, u, _ = new_user(client)
    r = c.post("/api/billing/stripe/checkout", json={"origin_url": "https://evil.example", "interval": "month"})
    assert r.status_code == 200, r.text
    assert r.json()["checkout_url"].startswith("http")
    tx = client.portal.call(db.payment_transactions.find_one, {"user_id": u["id"]})
    assert tx and tx["trial"] is True and tx["interval"] == "month"


def test_webhook_rejects_bad_signature(client):
    r = client.post("/api/stripe/webhook", content=b"{}", headers={"stripe-signature": "t=1,v1=bad"})
    assert r.status_code == 400


def test_trial_then_cancel_then_resubscribe_without_trial(client):
    c, u, _ = new_user(client)
    sub = "sub_" + uuid.uuid4().hex[:10]
    assert post_webhook(client, sub_event("customer.subscription.created", u["id"], "trialing", sub)).status_code == 200
    b = c.get("/api/billing/status").json()
    assert b["has_access"] and b["on_trial"] and b["plan"] == "trial" and b["trial_until"] and not b["trial_available"]
    assert b["interviews_limit"] == 3 and b["provider"] == "stripe"
    # Trial turns into a paid month
    assert post_webhook(client, sub_event("customer.subscription.updated", u["id"], "active", sub, days=30)).status_code == 200
    b = c.get("/api/billing/status").json()
    assert b["plan"] == "pro" and b["has_access"] and not b["on_trial"] and b["interviews_limit"] == 60
    # Cancelled at period end: still active until then
    post_webhook(client, sub_event("customer.subscription.updated", u["id"], "active", sub, days=30, cancel=True))
    assert c.get("/api/billing/status").json()["cancel_at_period_end"] is True
    # Subscription ends
    post_webhook(client, sub_event("customer.subscription.deleted", u["id"], "canceled", sub, days=0))
    b = c.get("/api/billing/status").json()
    assert not b["has_access"] and b["plan"] == "expired" and not b["trial_available"]
    # Webhook replays are harmless
    post_webhook(client, sub_event("customer.subscription.deleted", u["id"], "canceled", sub, days=0))
    assert c.get("/api/billing/status").json()["plan"] == "expired"


def test_past_due_loses_access(client):
    c, u, _ = new_user(client)
    sub = "sub_" + uuid.uuid4().hex[:10]
    post_webhook(client, sub_event("customer.subscription.created", u["id"], "active", sub, days=30))
    assert c.get("/api/billing/status").json()["has_access"]
    post_webhook(client, sub_event("customer.subscription.updated", u["id"], "past_due", sub, days=30))
    assert not c.get("/api/billing/status").json()["has_access"]


def test_trial_interview_cap(client):
    c, u, _ = new_user(client)
    post_webhook(client, sub_event("customer.subscription.created", u["id"], "trialing", "sub_" + uuid.uuid4().hex[:10]))

    async def seed():
        for _ in range(3):
            await db.interviews.insert_one({"id": str(uuid.uuid4()), "user_id": u["id"], "status": "completed", "created_at": datetime.now(timezone.utc)})
    client.portal.call(seed)
    r = c.post("/api/interviews", json={"position": "SOC Analyst L1", "experience": "Entry Level", "difficulty": "Realistic / Adaptive", "environment": "random", "mode": "quick"})
    assert r.status_code == 429, r.text
    assert "free trial" in r.json()["detail"]


def test_billing_portal_against_stripe_mock(client):
    c, u, _ = new_user(client)
    post_webhook(client, sub_event("customer.subscription.created", u["id"], "active", "sub_" + uuid.uuid4().hex[:10], days=30))
    r = c.post("/api/billing/portal")
    assert r.status_code == 200, r.text
    assert r.json()["url"].startswith("http")


def test_already_subscribed_cannot_checkout_again(client):
    c, u, _ = new_user(client)
    post_webhook(client, sub_event("customer.subscription.created", u["id"], "active", "sub_" + uuid.uuid4().hex[:10], days=30))
    assert c.post("/api/billing/stripe/checkout", json={"origin_url": "http://testserver", "interval": "year"}).status_code == 409


def test_login_rate_limit():
    email = f"rl{uuid.uuid4().hex[:6]}@example.com"
    c = TestClient(server.app)
    codes = [c.post("/api/auth/login", json={"email": email, "password": "wrong-pass"}).status_code for _ in range(12)]
    assert codes[:10] == [401] * 10 and codes[-1] == 429


def test_forgot_and_reset_password(client):
    c, u, email = new_user(client)
    assert client.post("/api/auth/forgot", json={"email": email}).status_code == 200
    assert client.post("/api/auth/forgot", json={"email": "nobody-" + email}).status_code == 200  # no enumeration
    token = "t" * 43
    tok_hash = hashlib.sha256(token.encode()).hexdigest()

    async def put():
        await db.password_resets.insert_one({"token_hash": tok_hash, "user_id": u["id"], "used": False,
                                             "expires_at": datetime.now(timezone.utc) + timedelta(hours=1)})
    client.portal.call(put)
    assert client.post("/api/auth/reset", json={"token": token, "password": "brand-new-pass-9"}).status_code == 200
    assert client.post("/api/auth/reset", json={"token": token, "password": "another-pass-99"}).status_code == 400  # single use
    d = TestClient(server.app)
    assert d.post("/api/auth/login", json={"email": email, "password": "brand-new-pass-9"}).status_code == 200


def test_delete_account(client):
    c, u, email = new_user(client)
    post_webhook(client, sub_event("customer.subscription.created", u["id"], "active", "sub_" + uuid.uuid4().hex[:10], days=30))
    assert c.post("/api/auth/delete-account", json={"confirm": "nope", "password": "correct-horse-1"}).status_code == 400
    assert c.post("/api/auth/delete-account", json={"confirm": "DELETE", "password": "wrong"}).status_code == 401
    assert c.post("/api/auth/delete-account", json={"confirm": "DELETE", "password": "correct-horse-1"}).status_code == 200
    assert TestClient(server.app).post("/api/auth/login", json={"email": email, "password": "correct-horse-1"}).status_code == 401


def test_admin_seeded_and_has_access(client):
    a = TestClient(server.app)
    r = a.post("/api/auth/login", json={"email": "owner@example.com", "password": "a-strong-admin-pass"})
    assert r.status_code == 200, r.text
    b = a.get("/api/billing/status").json()
    assert b["has_access"] and b["interviews_limit"] is None


def test_security_headers(client):
    r = client.get("/api/config")
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert "strict-transport-security" in r.headers
