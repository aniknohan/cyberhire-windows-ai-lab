"""Browser test of the paid website: landing → sign up → plans → Stripe checkout → trial active → app unlocked.

Runs against a local server in SOC_MODE=web with Stripe calls going to stripe-mock. The checkout page itself is
Stripe-hosted, so the test stands in for it and then delivers the signed webhook Stripe would send.
"""
import hashlib
import hmac
import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get("E2E_BASE", "http://127.0.0.1:8000")
WH = os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
OUT = Path(os.environ.get("E2E_SHOTS", "e2e-shots"))
OUT.mkdir(exist_ok=True)
errors: list[str] = []


def webhook(user_id: str, status="trialing", days=3):
    end = int((datetime.now(timezone.utc) + timedelta(days=days)).timestamp())
    ev = {"id": "evt_" + uuid.uuid4().hex, "object": "event", "type": "customer.subscription.created", "data": {"object": {
        "id": "sub_e2e" + uuid.uuid4().hex[:8], "object": "subscription", "status": status, "customer": "cus_e2e", "metadata": {"user_id": user_id},
        "trial_end": end, "cancel_at_period_end": False, "items": {"data": [{"current_period_end": end, "price": {"recurring": {"interval": "month"}}}]}}}}
    payload = json.dumps(ev).encode()
    t = int(time.time())
    sig = hmac.new(WH.encode(), f"{t}.".encode() + payload, hashlib.sha256).hexdigest()
    r = requests.post(f"{BASE}/api/stripe/webhook", data=payload, headers={"stripe-signature": f"t={t},v1={sig}", "content-type": "application/json"})
    assert r.status_code == 200, r.text


def step(name):
    print(f"--- {name}", flush=True)


with sync_playwright() as p:
    b = p.chromium.launch()
    for label, vp in (("desktop", {"width": 1366, "height": 860}), ("phone", {"width": 390, "height": 844})):
        ctx = b.new_context(viewport=vp)
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        pg.on("console", lambda m: m.type == "error" and "Failed to load resource" not in m.text and errors.append(f"console: {m.text}"))
        step(f"landing ({label})")
        pg.goto(BASE + "/")
        expect(pg.get_by_test_id("landing-title")).to_be_visible(timeout=15000)
        pg.screenshot(path=str(OUT / f"01-landing-{label}.png"), full_page=True)
        overflow = pg.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
        if overflow:
            errors.append(f"horizontal overflow on landing ({label})")
        ctx.close()

    ctx = b.new_context(viewport={"width": 1366, "height": 860})
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    pg.route("https://checkout.stripe.com/**", lambda r: r.fulfill(body="<h1>Stripe Checkout (test stand-in)</h1>", content_type="text/html"))

    step("legal pages")
    for path in ("/terms", "/privacy", "/refund-policy", "/delete-account"):
        pg.goto(BASE + path)
        expect(pg.get_by_test_id("legal-page")).to_be_visible()
    pg.screenshot(path=str(OUT / "02-privacy.png"), full_page=False)

    step("sign up")
    email = f"e2e{uuid.uuid4().hex[:6]}@example.com"
    pg.goto(BASE + "/register")
    pg.get_by_test_id("register-name-input").fill("E2E Tester")
    pg.get_by_test_id("register-email-input").fill(email)
    pg.get_by_test_id("register-password-input").fill("e2e-password-1")
    pg.get_by_test_id("register-submit-button").click()
    pg.wait_for_url("**/pricing?welcome=1", timeout=15000)
    expect(pg.get_by_test_id("plan-month")).to_be_visible()
    expect(pg.get_by_text("First 3 days free").first).to_be_visible()
    pg.screenshot(path=str(OUT / "03-pricing-after-signup.png"), full_page=True)

    step("paywall")
    pg.goto(BASE + "/interview/new")
    pg.wait_for_url("**/pricing", timeout=10000)

    step("checkout")
    pg.goto(BASE + "/pricing")
    pg.get_by_test_id("checkout-stripe-month-button").click()
    pg.wait_for_url("https://checkout.stripe.com/**", timeout=15000)

    step("trial activated by webhook")
    me = requests.Session()
    uid = None
    pg.goto(BASE + "/pricing")
    uid = pg.evaluate("fetch('/api/auth/me').then(r => r.json()).then(u => u.id)")
    webhook(uid)
    pg.goto(BASE + "/")
    expect(pg.get_by_test_id("nav-trial-badge")).to_be_visible(timeout=15000)
    pg.screenshot(path=str(OUT / "04-dashboard-trial.png"), full_page=False)
    pg.goto(BASE + "/interview/new")
    expect(pg.get_by_test_id("page-title")).to_be_visible()
    if "/pricing" in pg.url:
        errors.append("interview setup still paywalled after trial started")

    step("profile")
    pg.goto(BASE + "/profile")
    expect(pg.get_by_test_id("subscription-panel")).to_be_visible()
    expect(pg.get_by_test_id("delete-account-panel")).to_be_visible()
    expect(pg.get_by_test_id("manage-billing-button")).to_be_visible()
    pg.screenshot(path=str(OUT / "05-profile.png"), full_page=True)

    step("forgot password")
    pg.get_by_test_id("logout-button").click()
    pg.goto(BASE + "/login")
    pg.get_by_test_id("forgot-link").click()
    pg.get_by_test_id("forgot-email-input").fill(email)
    pg.get_by_test_id("forgot-submit").click()
    expect(pg.get_by_test_id("forgot-sent")).to_be_visible()
    b.close()

if errors:
    for e in errors:
        print(f"::error::{e}")
    sys.exit(1)
print("E2E OK")
