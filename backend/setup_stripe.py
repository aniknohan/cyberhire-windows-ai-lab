"""Idempotent Stripe catalog setup: `python setup_stripe.py` (the website also runs this at startup)."""
import logging
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
logging.basicConfig(level=logging.INFO)

from lib.stripe_catalog import ensure_catalog  # noqa: E402

ensure_catalog()
