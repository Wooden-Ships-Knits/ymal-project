"""
The HTTP boundary. config_store is stubbed — these tests cover routing, auth
and status codes, not Shopify.
"""

import os

import pytest
from fastapi.testclient import TestClient

TOKEN = "test-token-value"
os.environ["YMAL_API_TOKEN"] = TOKEN

from app.main import app  # noqa: E402  — import after the env var is set

from ymal import config_store  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


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
