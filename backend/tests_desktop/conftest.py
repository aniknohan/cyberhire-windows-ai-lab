import os
import sys
import tempfile
from pathlib import Path

os.environ["SOC_MODE"] = "desktop"
os.environ["SOC_DATA_DIR"] = tempfile.mkdtemp(prefix="cyberhire-desktop-test-")
os.environ.setdefault("JWT_SECRET", "desktop-test-secret-" + "x" * 30)
os.environ["COOKIE_SECURE"] = "0"
for k in ("STRIPE_SECRET_KEY", "PUBLIC_URL", "ADMIN_EMAIL", "ADMIN_PASSWORD"):
    os.environ.pop(k, None)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
