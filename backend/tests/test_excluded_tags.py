"""
Excluded tags - products the store still sells but Top Selling (MYNTS) and
Trending must stop recommending, e.g. Halloween sweaters after the shipping
cutoff. The matching rules, then the console routes with config_store stubbed.
"""

import os

import pytest
from fastapi.testclient import TestClient

TOKEN = "test-token-value"
os.environ["YMAL_API_TOKEN"] = TOKEN

from app import main  # noqa: E402
from app.main import app  # noqa: E402

from ymal import config_store, excluded_tags  # noqa: E402

main.API_TOKEN = TOKEN

PRODUCTS = [
    {"product_gid": "gid://1", "tags": "autumn, Halloween, spooky season"},
    {"product_gid": "gid://2", "tags": "autumn, halloween gift"},
    {"product_gid": "gid://3", "tags": "christmas, holiday"},
    {"product_gid": "gid://4", "tags": ""},
]


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def test_matches_a_whole_tag_ignoring_case():
    assert excluded_tags.matching(PRODUCTS, ["halloween"]) == {"gid://1"}


def test_a_tag_does_not_match_a_longer_tag_containing_it():
    # "halloween" must not quietly sweep up "halloween gift" - each is listed.
    assert "gid://2" not in excluded_tags.matching(PRODUCTS, ["halloween"])
    assert excluded_tags.matching(PRODUCTS, ["halloween", "halloween gift"]) == {
        "gid://1",
        "gid://2",
    }


def test_no_tags_excludes_nothing():
    assert excluded_tags.matching(PRODUCTS, []) == set()


def test_counts_products_per_tag():
    assert excluded_tags.counts(PRODUCTS, ["halloween", "christmas", "easter"]) == {
        "halloween": 1,
        "christmas": 1,
        "easter": 0,
    }


def test_clean_lowercases_trims_and_drops_repeats():
    assert excluded_tags.clean(["  Halloween ", "halloween", "", "Spooky  Season"]) == [
        "halloween",
        "spooky season",
    ]


def test_every_known_tag_once_lowercased():
    assert excluded_tags.known(PRODUCTS) == [
        "autumn", "christmas", "halloween", "halloween gift", "holiday", "spooky season",
    ]


def test_load_falls_back_to_nothing_when_the_shop_cannot_be_read(monkeypatch):
    def boom():
        raise RuntimeError("Shopify down")

    monkeypatch.setattr(config_store, "read", boom)
    assert excluded_tags.load() == []


def test_load_reads_the_saved_list(monkeypatch):
    monkeypatch.setattr(
        config_store,
        "read",
        lambda: {"config": {"excluded_tags": ["halloween"]}, "has_previous": False},
    )
    assert excluded_tags.load() == ["halloween"]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

PLACEMENTS = {"product": [{"block": "featured", "heading": "You May Also Like",
                          "slots": 6, "enabled": True}]}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def stub_store(monkeypatch):
    state = {
        "config": {
            "version": 1,
            "enabled": True,
            "placements": PLACEMENTS,
            "tuning": {"popularity_weight": 1.0},
            "personalized": ["MONOGRAM CREW CHUNKY"],
            "updated_at": "2026-10-20T00:00:00Z",
            "updated_by": "web-team",
        }
    }

    def write(config, updated_by):
        state["config"] = {**config, "updated_by": updated_by,
                           "updated_at": "2026-10-26T00:00:00Z"}
        return state["config"]

    monkeypatch.setattr(
        config_store, "read", lambda: {"config": state["config"], "has_previous": True}
    )
    monkeypatch.setattr(config_store, "write", write)
    monkeypatch.setattr(excluded_tags, "products", lambda: PRODUCTS)
    return state


def put(client, tags, token=TOKEN):
    return client.put("/api/excluded-tags", json={"tags": tags},
                      headers={"X-YMAL-Token": token})


def test_get_is_empty_when_nothing_is_saved(client, stub_store):
    body = client.get("/api/excluded-tags").json()
    assert body["tags"] == []
    assert body["blocks"] == ["trending", "top_selling"]
    assert "halloween" in body["known_tags"]


def test_get_reports_how_many_products_each_tag_catches(client, stub_store):
    put(client, ["halloween"])
    assert client.get("/api/excluded-tags").json()["counts"] == {"halloween": 1}


def test_put_requires_a_token(client, stub_store):
    assert put(client, ["halloween"], token="").status_code == 401


def test_put_saves_cleaned_tags(client, stub_store):
    r = put(client, [" Halloween ", "spooky season", "halloween"])
    assert r.status_code == 200
    assert stub_store["config"]["excluded_tags"] == ["halloween", "spooky season"]


def test_put_leaves_everything_else_alone(client, stub_store):
    put(client, ["halloween"])
    assert stub_store["config"]["placements"] == PLACEMENTS
    assert stub_store["config"]["tuning"] == {"popularity_weight": 1.0}
    assert stub_store["config"]["personalized"] == ["MONOGRAM CREW CHUNKY"]


def test_an_empty_list_removes_the_key(client, stub_store):
    put(client, ["halloween"])
    put(client, [])
    assert "excluded_tags" not in stub_store["config"]


def test_put_rejects_a_non_list(client, stub_store):
    r = client.put("/api/excluded-tags", json={"tags": "halloween"},
                   headers={"X-YMAL-Token": TOKEN})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Which blocks the list applies to
# ---------------------------------------------------------------------------

def test_top_selling_and_trending_skip_the_excluded():
    eligible = {"gid://1", "gid://2", "gid://3"}
    for block in ("top_selling", "trending"):
        assert excluded_tags.pool_for(block, eligible, {"gid://1"}) == {"gid://2", "gid://3"}


def test_new_arrivals_is_untouched():
    eligible = {"gid://1", "gid://2"}
    assert excluded_tags.pool_for("new_arrivals", eligible, {"gid://1"}) == eligible
