"""
Shopify authentication.

Exchanges the app's client credentials for an Admin API access token using the
client_credentials grant. The token is cached for the life of the process, so
get_headers() is safe to call per-request without re-exchanging each time.

Env vars, read from .env at the repo root:
    SHOPIFY_CLIENT_ID
    SHOPIFY_SECRET_KEY
"""

import os

import requests
from dotenv import load_dotenv

from ymal import settings

load_dotenv(settings.REPO_ROOT / ".env", override=True)

TOKEN_URL = f"https://{settings.SHOP}/admin/oauth/access_token"

_cached_token: str | None = None


def get_token(force_refresh: bool = False) -> str:
    """Return an Admin API access token, exchanging credentials on first call."""
    global _cached_token
    if _cached_token and not force_refresh:
        return _cached_token

    client_id = os.getenv("SHOPIFY_CLIENT_ID")
    client_secret = os.getenv("SHOPIFY_SECRET_KEY")

    if not client_id or not client_secret:
        raise RuntimeError(
            "Missing Shopify credentials. Expected SHOPIFY_CLIENT_ID and "
            f"SHOPIFY_SECRET_KEY in {settings.REPO_ROOT / '.env'} "
            f"(client_id set: {bool(client_id)}, secret set: {bool(client_secret)})"
        )

    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )

    if not response.ok:
        # Deliberately does not echo the secret into the error text.
        raise RuntimeError(
            f"Failed to obtain access token (HTTP {response.status_code}): "
            f"{response.text}"
        )

    _cached_token = response.json()["access_token"]
    return _cached_token


def get_headers() -> dict[str, str]:
    """Standard headers for an Admin GraphQL request."""
    return {
        "X-Shopify-Access-Token": get_token(),
        "Content-Type": "application/json",
    }
