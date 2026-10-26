"""
The tracking endpoint, as a shopper's browser actually calls it.

These exist because tracking was installed on the theme and recorded nothing.
Three separate faults, each enough on its own:

  1. nginx basic auth covered the whole host, so every beacon got a 401 before
     reaching the API. Fixed in the VM's nginx, which is not in this repo.
  2. The CORS allowlist named `woodenships.com`; the shop is `wooden-ships.com`.
  3. The beacon sent `Content-Type: application/json`, which is NOT a
     CORS-safelisted value, so the browser had to send a preflight first -
     a round trip that a beacon fired during page unload can lose.

2 and 3 are covered here. `text/plain` is the point: a simple request, no
preflight, nothing to lose the race with.
"""

import json
import os

import pytest
from fastapi.testclient import TestClient

TOKEN = "test-token-value"
os.environ["YMAL_API_TOKEN"] = TOKEN

from app import main  # noqa: E402
from app.main import app  # noqa: E402

from ymal import db  # noqa: E402

main.API_TOKEN = TOKEN

SHOP = "https://www.wooden-ships.com"

BATCH = {
    "events": [
        {
            "type": "click",
            "block": "featured",
            "page_type": "product",
            "session": "abc123",
            "handle": "pumpkin-truck-crew-chunky",
            "anchor": "pumpkin-fair-isle-crew-chunky",
            "position": 2,
        }
    ]
}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def stub_db(monkeypatch):
    stored = []
    monkeypatch.setattr(db, "insert_events", lambda rows: stored.extend(rows) or len(rows))
    return stored


class TestContentTypes:
    def test_accepts_text_plain(self, client, stub_db):
        """
        What sendBeacon sends. text/plain is CORS-safelisted, so the browser
        makes no preflight - which is the whole reason for choosing it.
        """
        r = client.post(
            "/api/events",
            content=json.dumps(BATCH),
            headers={"Content-Type": "text/plain;charset=UTF-8"},
        )
        assert r.status_code == 202
        assert len(stub_db) == 1

    def test_still_accepts_application_json(self, client, stub_db):
        """The fetch fallback for browsers without sendBeacon."""
        r = client.post("/api/events", json=BATCH)
        assert r.status_code == 202
        assert len(stub_db) == 1

    def test_accepts_a_body_with_no_content_type_at_all(self, client, stub_db):
        r = client.post("/api/events", content=json.dumps(BATCH))
        assert r.status_code == 202

    def test_rejects_a_body_that_is_not_json(self, client):
        """
        A shopper cannot cause this; only a broken client can. Worth a 400 so
        it shows up in the nginx log rather than looking like silence.
        """
        r = client.post(
            "/api/events",
            content="not json at all",
            headers={"Content-Type": "text/plain"},
        )
        assert r.status_code == 400

    def test_rejects_json_that_is_not_an_object(self, client):
        r = client.post(
            "/api/events", content="[1, 2, 3]", headers={"Content-Type": "text/plain"}
        )
        assert r.status_code == 400

    def test_an_empty_body_is_not_a_crash(self, client):
        assert client.post("/api/events", content="").status_code in (202, 400)


class TestCors:
    def test_the_real_shop_origin_is_allowed(self, client):
        """
        The bug: the allowlist said `woodenships.com` and the shop is
        `wooden-ships.com`. One hyphen, and every beacon was refused by the
        browser before it left the page.
        """
        r = client.post("/api/events", json=BATCH, headers={"Origin": SHOP})
        assert r.headers.get("access-control-allow-origin") == SHOP

    def test_the_bare_domain_is_allowed_too(self, client):
        bare = "https://wooden-ships.com"
        r = client.post("/api/events", json=BATCH, headers={"Origin": bare})
        assert r.headers.get("access-control-allow-origin") == bare

    def test_an_unrelated_origin_is_not_allowed(self, client):
        """
        Not a wildcard: any page on the internet could otherwise post events
        into this shop's analytics.
        """
        r = client.post(
            "/api/events", json=BATCH, headers={"Origin": "https://evil.example"}
        )
        assert r.headers.get("access-control-allow-origin") is None

    def test_the_shop_domain_is_in_the_default_allowlist(self):
        """
        Checked against the module rather than a request, because the default
        is what a VM with no YMAL_STOREFRONT_ORIGINS in .env will use - which
        is exactly the situation that produced the bug.
        """
        assert SHOP in main.STOREFRONT_ORIGINS
