"""
Can a shopper's browser actually reach the tracking endpoint?

On 2026-09-12 tracking was installed on the theme and recorded nothing, for
three separate reasons - nginx basic auth in front of /api/events, a CORS
allowlist naming a domain that does not exist, and a beacon content type that
forced a preflight it could lose. Every one of them failed silently. The block
rendered, the browser logged nothing a merchandiser would see, and the Analytics
tab read zero, which looks exactly like "nobody has clicked yet".

This module exists so that state has a sentence attached to it.

It probes the PUBLIC url - through the VM's nginx, not the container's - with no
credentials, because that is the only thing a shopper's browser can do. Probing
the API directly would pass while the storefront stayed broken, which is worse
than not checking at all.

verdict() is pure and covers every failure mode; probe() is the request.
"""

import requests

# An empty batch. It exercises auth, routing and CORS and stores nothing, so
# this can run as often as anyone likes without polluting the analytics.
EMPTY_BATCH = '{"events":[]}'

# Matches ymal-track.js. See that file for why it is not application/json.
CONTENT_TYPE = "text/plain;charset=UTF-8"

TIMEOUT_SECONDS = 8


def verdict(status: int | None, allow_origin: str | None, shop_origin: str) -> dict:
    """
    What the response means, in a sentence someone can act on.

    `status` is None when the request never got an answer.
    `allow_origin` is the Access-Control-Allow-Origin header, if any.
    """
    if status is None:
        return _bad(
            "unreachable",
            "The tracking endpoint did not answer. Check that the VM's nginx "
            "is running and that the host resolves.",
        )

    if status in (401, 403):
        return _bad(
            "auth",
            "The endpoint is behind HTTP basic auth, so a shopper's browser "
            "gets a 401 and every event is lost. The fix is in the VM's nginx, "
            "not in this repository: add a `location = /api/events` block with "
            "`auth_basic off;`. See frontend/storefront/install.md.",
        )

    if status == 404:
        return _bad(
            "missing",
            "No tracking endpoint at that path. Check YMAL_PUBLIC_URL and that "
            "nginx proxies /api/ to the console container.",
        )

    if status == 503:
        return _bad(
            "storage",
            "The endpoint answered but cannot store events - usually Postgres "
            "being down. Events sent now are lost; beacons cannot retry.",
        )

    if status not in (200, 202):
        return _bad("status", f"Unexpected status {status} from the endpoint.")

    # Reachable. Now: would a browser have been allowed to send it at all?
    if allow_origin not in ("*", shop_origin):
        got = allow_origin or "no Access-Control-Allow-Origin header"
        return _bad(
            "cors",
            f"The endpoint answered, but a browser on {shop_origin} would be "
            f"refused: it returned {got}. Set YMAL_STOREFRONT_ORIGINS in .env "
            "to the storefront's exact domain - a missing hyphen is enough to "
            "break it.",
        )

    return {
        "ok": True,
        "cause": None,
        "hint": "",
        "detail": "",
        "status": status,
        "allow_origin": allow_origin,
    }


def _bad(cause: str, hint: str) -> dict:
    return {"ok": False, "cause": cause, "hint": hint, "detail": ""}


def probe(url: str, shop_origin: str, timeout: int = TIMEOUT_SECONDS) -> dict:
    """
    Post an empty batch the way the storefront would, and report what happened.

    Never raises. This runs at API startup and from the console; a DNS failure
    must produce a warning, not take anything down.
    """
    try:
        response = requests.post(
            url,
            data=EMPTY_BATCH,
            headers={"Content-Type": CONTENT_TYPE, "Origin": shop_origin},
            timeout=timeout,
        )
    except Exception as error:  # noqa: BLE001 - every failure is "unreachable"
        result = verdict(None, None, shop_origin)
        result["detail"] = str(error)
        result["status"] = None
        result["allow_origin"] = None
        return result

    allow_origin = response.headers.get("Access-Control-Allow-Origin")
    result = verdict(response.status_code, allow_origin, shop_origin)
    result["status"] = response.status_code
    result["allow_origin"] = allow_origin
    return result


def describe(result: dict) -> str:
    """One line for a log, in the OK:/WARNING: shape the pipeline already uses."""
    if result["ok"]:
        return "OK: tracking endpoint is reachable by a shopper's browser."
    return f"WARNING: tracking is not recording. {result['hint']}"
