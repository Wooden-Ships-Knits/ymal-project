"""
Shopify authentication.

Exchanges the app's client credentials for an Admin API access token using the
client_credentials grant, and keeps it fresh.

THE TOKEN EXPIRES. The grant returns expires_in: 86399 - twenty-four hours. This
module originally cached the first token for the life of the process and never
refreshed it. The api container is long-running, so twenty-four hours after
`docker compose up` every console screen that reads Shopify failed with
"401 Unauthorized" until the container was restarted. Found 2026-09-15 on the
Ranking tab.

The nightly job never showed it: `docker compose run --rm api` is a fresh
process, and a fresh process gets a fresh token.

So the token is refreshed REFRESH_MARGIN_SECONDS before it expires, and
shopify.graphql() also retries once with a new token if Shopify refuses one
early (revoked, secret rotated, clock skew).

Env vars, read from .env at the repo root:
    SHOPIFY_CLIENT_ID
    SHOPIFY_SECRET_KEY
"""

import os
import time

import requests
from dotenv import load_dotenv

from ymal import settings

load_dotenv(settings.REPO_ROOT / ".env", override=True)

TOKEN_URL = f"https://{settings.SHOP}/admin/oauth/access_token"

# Refresh this long before expiry, so a request never races the deadline.
REFRESH_MARGIN_SECONDS = 5 * 60

# Used only if Shopify omits expires_in. Deliberately SHORT: assuming a token
# lives forever is exactly the bug this module had.
DEFAULT_LIFETIME_SECONDS = 60 * 60

_cached_token: str | None = None
_token_expires_at: float = 0.0


def _is_fresh() -> bool:
    return bool(_cached_token) and time.time() < _token_expires_at - REFRESH_MARGIN_SECONDS


def get_token(force_refresh: bool = False) -> str:
    """
    Return a valid Admin API access token.

    Reuses the cached token while it has more than REFRESH_MARGIN_SECONDS left,
    otherwise exchanges the credentials for a new one. `force_refresh` skips
    the cache - used after Shopify refuses a token it should have accepted.
    """
    global _cached_token, _token_expires_at
    if not force_refresh and _is_fresh():
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

    body = response.json()
    _cached_token = body["access_token"]
    lifetime = body.get("expires_in") or DEFAULT_LIFETIME_SECONDS
    _token_expires_at = time.time() + float(lifetime)
    return _cached_token


def get_headers() -> dict[str, str]:
    """Standard headers for an Admin GraphQL request."""
    return {
        "X-Shopify-Access-Token": get_token(),
        "Content-Type": "application/json",
    }
