"""Which product this server is running as.

- desktop (default): the free Windows app — every feature unlocked, the user's own API keys.
- web: the hosted, paid website — Stripe / Google Play subscriptions, the owner's server-side API keys,
  usage limits and the public marketing pages.
"""
import os

WEB = os.environ.get("SOC_MODE", "desktop").strip().lower() == "web"


def public_url() -> str:
    """The site's public address, e.g. https://cyberhire.app (used for Stripe return links and emails)."""
    return (os.environ.get("PUBLIC_URL") or os.environ.get("RENDER_EXTERNAL_URL") or "").rstrip("/")


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default
