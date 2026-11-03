"""The free Windows app must stay free: every feature unlocked, no paywall, no website pages forced on it."""
from fastapi.testclient import TestClient

import server


def test_desktop_is_free():
    with TestClient(server.app) as c:
        assert c.get("/api/config").json()["mode"] == "desktop"
        r = c.post("/api/auth/register", json={"email": "local@example.com", "password": "abcdef", "name": "Local"})
        assert r.status_code == 200, r.text
        b = c.get("/api/billing/status").json()
        assert b["mode"] == "desktop" and b["has_access"] and b["is_pro"] and not b["on_trial"] and b["interviews_limit"] is None
        # default local admin still exists for the desktop app
        assert TestClient(server.app).post("/api/auth/login", json={"email": "admin@socsim.com", "password": "Admin@123"}).status_code == 200
