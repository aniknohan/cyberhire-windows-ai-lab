import os
import sys
import tempfile
from pathlib import Path

# Configure the website mode BEFORE the app is imported (mode is read at import time).
_tmp = tempfile.mkdtemp(prefix="cyberhire-test-")
os.environ.setdefault("SOC_MODE", "web")
os.environ["SOC_DATA_DIR"] = _tmp
os.environ.setdefault("JWT_SECRET", "test-secret-" + "x" * 40)
os.environ.setdefault("COOKIE_SECURE", "0")
os.environ.setdefault("PUBLIC_URL", "http://testserver")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_123")
os.environ.setdefault("STRIPE_API_BASE", "http://localhost:12111")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
os.environ.setdefault("ADMIN_EMAIL", "owner@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "a-strong-admin-pass")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("SIGNUP_LIMIT_PER_HOUR", "1000")
