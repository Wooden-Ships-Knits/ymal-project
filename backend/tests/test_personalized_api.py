"""
The personalized-products routes. config_store is stubbed, as in
test_tuning_api.py - this covers routing, auth, cleaning, validation and the
leave-everything-else-alone rule, not Shopify.
"""

import os

import pytest
from fastapi.testclient import TestClient

TOKEN = "test-token-value"
os.environ["YMAL_API_TOKEN"] = TOKEN

from app import main  # noqa: E402
from app.main import app  # noqa: E402

from ymal import config_store, personalized  # noqa: E402

main.API_TOKEN = TOKEN

PLACEMENTS = {"product": [{"block": "featured", "heading": "You May Also Like",
                          "slots": 6, "enabled": True}]}
TUNING = {"popularity_weight": 1.0}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def stub_store(monkeypatch):
    """A shop with placements and tuning saved, so we can prove we keep them."""
    state = {
        "config": {
            "version": 1,
            "enabled": True,
            "placements": PLACEMENTS,
            "tuning": TUNING,
            "updated_at": "2026-10-01T00:00:00Z",
            "updated_by": "web-team",
        }
    }

    def write(config, updated_by):
        state["config"] = {
            **config,
            "updated_by": updated_by,
            "updated_at": "2026-10-07T00:00:00Z",
        }
        return state["config"]

    monkeypatch.setattr(
        config_store, "read", lambda: {"config": state["config"], "has_previous": True}
    )
    monkeypatch.setattr(config_store, "write", write)
    return state


@pytest.fixture(autouse=True)
def stub_titles(monkeypatch):
    monkeypatch.setattr(
        personalized,
        "known_titles",
        lambda: ["CUSTOMIZABLE NUMBER JERSEY COTTON", "KEY WEST CHUNKY CREW COTTON"],
    )


def put(client, titles, token=TOKEN):
    return client.put(
        "/api/personalized",
        json={"titles": titles},
        headers={"X-YMAL-Token": token},
    )


class TestGetPersonalized:
    def test_empty_when_nothing_is_saved(self, client):
        r = client.get("/api/personalized")
        assert r.status_code == 200
        assert r.json()["titles"] == []

    def test_offers_the_catalog_titles(self, client):
        r = client.get("/api/personalized")
        assert "KEY WEST CHUNKY CREW COTTON" in r.json()["known_titles"]

    def test_needs_no_token(self, client):
        assert client.get("/api/personalized").status_code == 200


class TestPutPersonalized:
    def test_requires_a_token(self, client):
        assert put(client, ["X"], token="").status_code == 401

    def test_saves_the_list(self, client, stub_store):
        r = put(client, ["CUSTOMIZABLE NUMBER JERSEY COTTON"])
        assert r.status_code == 200
        assert stub_store["config"]["personalized"] == ["CUSTOMIZABLE NUMBER JERSEY COTTON"]

    def test_matches_textify_case_insensitively(self, client, stub_store):
        """
        Stored upper-cased and trimmed, and the theme compares upper-cased, so
        "Monogram Crew Chunky " still matches the product titled in capitals.
        """
        put(client, ["  Monogram Crew Chunky "])
        assert stub_store["config"]["personalized"] == ["MONOGRAM CREW CHUNKY"]

    def test_drops_blanks_and_duplicates(self, client, stub_store):
        put(client, ["A JERSEY", "", "a jersey", "  "])
        assert stub_store["config"]["personalized"] == ["A JERSEY"]

    def test_leaves_placements_and_tuning_untouched(self, client, stub_store):
        put(client, ["A JERSEY"])
        assert stub_store["config"]["placements"] == PLACEMENTS
        assert stub_store["config"]["tuning"] == TUNING

    def test_empty_list_removes_the_key(self, client, stub_store):
        put(client, ["A JERSEY"])
        put(client, [])
        assert "personalized" not in stub_store["config"]

    def test_rejects_a_non_list(self, client):
        r = client.put(
            "/api/personalized",
            json={"titles": "A JERSEY"},
            headers={"X-YMAL-Token": TOKEN},
        )
        assert r.status_code == 422

    def test_rejects_a_non_string_title(self, client):
        assert put(client, ["A JERSEY", 7]).status_code == 422
