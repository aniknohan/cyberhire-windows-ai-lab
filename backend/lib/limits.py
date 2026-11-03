"""Small in-process rate limiters (one server instance): login attempts and AI calls per user.

They protect the owner's AI bill and accounts from brute force. Counts reset when the server restarts,
which is acceptable for these soft limits; hard limits (interviews per month) are counted in the database.
"""
import os
import time
from collections import defaultdict, deque

from fastapi import HTTPException


def _env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


class Window:
    def __init__(self, limit: int, seconds: int):
        self.limit, self.seconds = limit, seconds
        self.hits: dict[str, deque] = defaultdict(deque)

    def hit(self, key: str) -> bool:
        """Record one hit; False when the key is over its limit for the window."""
        now = time.monotonic()
        q = self.hits[key]
        while q and now - q[0] > self.seconds:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        if len(self.hits) > 50_000:  # keep memory bounded
            for k in list(self.hits)[:10_000]:
                if not self.hits[k]:
                    del self.hits[k]
        return True

    def check(self, key: str, message: str) -> None:
        if not self.hit(key):
            raise HTTPException(status_code=429, detail=message)


AUTH_ATTEMPTS = Window(limit=10, seconds=15 * 60)      # per IP+email: sign-in tries; per IP: reset requests
SIGNUPS = Window(limit=_env("SIGNUP_LIMIT_PER_HOUR", 20), seconds=60 * 60)  # new accounts per IP
RESET_EMAILS = Window(limit=3, seconds=60 * 60)        # per email address
AI_CALLS_PER_MINUTE = Window(limit=40, seconds=60)     # per user: bursts (TTS + answers)
AI_CALLS_PER_DAY = Window(limit=1500, seconds=86_400)  # per user: a very heavy day of practice
