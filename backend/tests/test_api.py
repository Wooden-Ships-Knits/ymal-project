"""
The HTTP boundary. config_store is stubbed — these tests cover routing, auth
and status codes, not Shopify.
"""

import os

import pytest
from fastapi.testclient import TestClient

TOKEN = "test-token-value"

# Set before importing app.main, which refuses to start without it.
os.environ["YMAL_API_TOKEN"] = TOKEN

from app import main  # noqa: E402  — import after the env var is set
from app.main import app  # noqa: E402

from ymal import config_store  # noqa: E402

# app.main calls load_dotenv(override=True), so a real token in the developer's
# .env wins over the env var above. Pin the module global instead: these tests
# must not depend on whether .env happens to hold a token, or on which one.
main.API_TOKEN = TOKEN


@pytest.fixture
def client():
    return TestClient(app)


def test_the_token_under_test_is_the_one_the_app_checks():
    # Guards the pin above: if app.main ever reads the token per-request from
    # somewhere else, every auth test below would silently pass for the wrong
    # reason.
    assert main.API_TOKEN == TOKEN


@pytest.fixture(autouse=True)
def stub_store(monkeypatch):
    state = {"config": {"version": 1, "enabled": True, "placements": {}}}

    monkeypatch.setattr(
        config_store, "read", lambda: {"config": state["config"], "has_previous": True}
    )
    # Must include updated_at: put_config reads it off the returned document to
    # build its response, so a stub without it fails with a KeyError rather
    # than testing anything.
    monkeypatch.setattr(
        config_store,
        "write",
        lambda config, updated_by: {
            **config,
            "updated_by": updated_by,
            "updated_at": "2026-09-05T00:00:00Z",
        },
    )
    monkeypatch.setattr(config_store, "undo", lambda: state["config"])
    monkeypatch.setattr(
        config_store, "published_block_ids", lambda: {"recently_viewed"}
    )
    return state


VALID_CONFIG = {"version": 1, "enabled": True, "placements": {}}


def test_health_needs_no_token(client):
    assert client.get("/api/health").status_code == 200


def test_get_config_needs_no_token(client):
    response = client.get("/api/config")
    assert response.status_code == 200
    assert response.json()["has_previous"] is True


def test_put_without_a_token_is_refused(client):
    response = client.put("/api/config", json=VALID_CONFIG)
    assert response.status_code == 401


def test_put_with_a_wrong_token_is_refused(client):
    response = client.put(
        "/api/config", json=VALID_CONFIG, headers={"X-YMAL-Token": "wrong"}
    )
    assert response.status_code == 401


def test_put_with_the_right_token_succeeds(client):
    response = client.put(
        "/api/config", json=VALID_CONFIG, headers={"X-YMAL-Token": TOKEN}
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_an_invalid_config_returns_422_with_field_errors(client):
    bad = {
        "version": 1,
        "enabled": True,
        "placements": {"home": [{"block": "trending", "heading": "H", "slots": 40, "enabled": True}]},
    }
    response = client.put("/api/config", json=bad, headers={"X-YMAL-Token": TOKEN})

    assert response.status_code == 422
    errors = response.json()["errors"]
    assert errors[0]["path"] == "placements.home[0].slots"
    assert "between 2 and 12" in errors[0]["message"]


def test_an_invalid_config_is_not_written(client, monkeypatch):
    written = []
    monkeypatch.setattr(
        config_store, "write", lambda config, updated_by: written.append(config)
    )

    client.put(
        "/api/config",
        json={"version": 99, "enabled": True, "placements": {}},
        headers={"X-YMAL-Token": TOKEN},
    )

    assert written == []


def test_an_unauthenticated_invalid_config_is_refused_before_validation(client):
    # 401 beats 422: an anonymous caller should not learn which of their
    # fields were wrong.
    response = client.put("/api/config", json={"version": 99})
    assert response.status_code == 401


def test_undo_without_a_token_is_refused(client):
    assert client.post("/api/config/undo").status_code == 401


def test_undo_without_a_previous_config_returns_409(client, monkeypatch):
    def raise_no_previous():
        raise config_store.NoPreviousConfig("nothing to restore")

    monkeypatch.setattr(config_store, "undo", raise_no_previous)

    response = client.post("/api/config/undo", headers={"X-YMAL-Token": TOKEN})
    assert response.status_code == 409


def test_blocks_lists_five_with_publish_state(client):
    blocks = client.get("/api/blocks").json()

    assert len(blocks) == 5
    by_id = {b["id"]: b for b in blocks}
    assert by_id["recently_viewed"]["list_published"] is True
    assert by_id["trending"]["list_published"] is False
    assert by_id["featured"]["supported_page_templates"] == ["product"]


def test_blocks_still_answers_when_shopify_is_unreachable(client, monkeypatch):
    def raise_network():
        raise RuntimeError("connection refused")

    monkeypatch.setattr(config_store, "published_block_ids", raise_network)

    blocks = client.get("/api/blocks").json()

    assert len(blocks) == 5
    assert all(b["list_published"] is False for b in blocks)


def test_page_templates_lists_nine(client):
    templates = client.get("/api/page-templates").json()

    assert len(templates) == 9
    assert {t["id"] for t in templates if t["live"]} == {"product", "home"}


def test_a_shopify_failure_is_not_flattened_into_an_empty_config(client, monkeypatch):
    def raise_network():
        raise RuntimeError("connection refused")

    monkeypatch.setattr(config_store, "read", raise_network)

    response = client.get("/api/config")
    assert response.status_code == 502


def test_what_get_returns_can_be_sent_straight_back_to_put(client, monkeypatch):
    """
    The regression test for the bug that made this branch unusable on day two.

    config_store stamps updated_at/updated_by into the stored document, and
    config_schema rejects both on the way in. When GET handed them back inside
    `config`, the console spread them into its next PUT and every save after a
    page reload failed with 422. The suite was green because no test ever
    completed the round trip.
    """
    stored = {
        "version": 1,
        "enabled": True,
        "placements": {},
        "updated_at": "2026-09-05T00:00:00Z",
        "updated_by": "web-team",
    }
    monkeypatch.setattr(
        config_store, "read", lambda: {"config": stored, "has_previous": True}
    )

    fetched = client.get("/api/config").json()

    # The stamps travel as siblings, not inside the document.
    assert fetched["updated_by"] == "web-team"
    assert "updated_by" not in fetched["config"]

    replayed = client.put(
        "/api/config", json=fetched["config"], headers={"X-YMAL-Token": TOKEN}
    )
    assert replayed.status_code == 200


def test_a_config_with_no_stamps_yet_reports_them_as_null(client):
    fetched = client.get("/api/config").json()

    assert fetched["updated_at"] is None
    assert fetched["updated_by"] is None


def test_a_non_ascii_token_is_refused_not_a_server_error(client):
    # Starlette decodes headers as latin-1 and compare_digest refuses non-ASCII
    # str, so an unguarded comparison turns junk into a 500 on an
    # unauthenticated path.
    # Sent as raw bytes, the way a real client puts them on the wire: httpx
    # refuses to encode a non-ASCII str into a header at all.
    response = client.put(
        "/api/config",
        json=VALID_CONFIG,
        headers={"X-YMAL-Token": "café".encode("latin-1")},
    )
    assert response.status_code == 401


def test_undo_also_strips_the_stamps_from_what_it_returns(client, monkeypatch):
    # Undo returns a stored document, so it carries the same stamps GET does.
    # Without the split the console would re-send them and hit 422 - the same
    # bug through a second door.
    monkeypatch.setattr(
        config_store,
        "undo",
        lambda: {
            "version": 1,
            "enabled": True,
            "placements": {},
            "updated_at": "2026-09-04T00:00:00Z",
            "updated_by": "web-team",
        },
    )

    body = client.post("/api/config/undo", headers={"X-YMAL-Token": TOKEN}).json()

    assert body["updated_by"] == "web-team"
    assert "updated_by" not in body["config"]

    replayed = client.put(
        "/api/config", json=body["config"], headers={"X-YMAL-Token": TOKEN}
    )
    assert replayed.status_code == 200
