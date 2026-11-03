"""Creates the CyberHire Pro product and its two prices in Stripe if they don't exist yet (safe to run often).

Prices are found by lookup key (pro_monthly / pro_yearly), so the owner never has to copy price IDs around.
"""
import logging
import os

import stripe

logger = logging.getLogger(__name__)

PRODUCT_KEY = "pro_plan"
CATALOG = {
    "name": "CyberHire Pro",
    "description": "AI cybersecurity interview simulator: unlimited practice interviews, reports and coaching.",
    "tax_code": "txcd_10103001",  # SaaS - business use
    "prices": [{"lookup_key": "pro_monthly", "amount": 1999, "currency": "usd", "interval": "month"},
               {"lookup_key": "pro_yearly", "amount": 15900, "currency": "usd", "interval": "year"}],
}


def _product():
    for p in stripe.Product.list(active=True, limit=100).auto_paging_iter():
        meta = p.get("metadata") or {}
        if meta.get("cyberhire_product") == PRODUCT_KEY or meta.get("emergent_product_id") == PRODUCT_KEY:
            return p
    return stripe.Product.create(name=CATALOG["name"], description=CATALOG["description"], tax_code=CATALOG["tax_code"],
                                 metadata={"cyberhire_product": PRODUCT_KEY})


def ensure_catalog() -> None:
    if os.environ.get("STRIPE_API_BASE"):
        stripe.api_base = os.environ["STRIPE_API_BASE"]
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY") or stripe.api_key
    if not stripe.api_key:
        logger.info("Stripe not configured; skipping catalog setup")
        return
    product = _product()
    for p in CATALOG["prices"]:
        existing = stripe.Price.list(lookup_keys=[p["lookup_key"]], active=True, limit=1).data
        if existing and (existing[0].unit_amount != p["amount"] or existing[0].currency != p["currency"]):
            stripe.Price.modify(existing[0].id, active=False)
            existing = []
        if not existing:
            stripe.Price.create(product=product.id, unit_amount=p["amount"], currency=p["currency"], lookup_key=p["lookup_key"],
                                transfer_lookup_key=True, recurring={"interval": p["interval"]}, tax_behavior="exclusive")
        logger.info("Stripe price ready: %s", p["lookup_key"])
