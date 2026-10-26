"""
The tuning routes. config_store and the feature table are both stubbed — this
covers routing, auth, validation and the leave-placements-alone rule, not
Shopify and not the scoring maths (tests/test_tuning.py and
tests/test_similarity.py have those).
"""

import os

import pytest
from fastapi.testclient import TestClient

TOKEN = "test-token-value"
os.environ["YMAL_API_TOKEN"] = TOKEN

from app import main  # noqa: E402
from app.main import app  # noqa: E402

from ymal import config_store, preview, settings  # noqa: E402

main.API_TOKEN = TOKEN

PLACEMENTS = {"product": [{"block": "featured", "heading": "You May Also Like",
                          "slots": 6, "enabled": True}]}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def stub_store(monkeypatch):
    """A shop that already has placements saved, so we can prove we keep them."""
    state = {
        "config": {
            "version": 1,
            "enabled": True,
            "placements": PLACEMENTS,
            "updated_at": "2026-09-11T00:00:00Z",
            "updated_by": "web-team",
        }
    }

    def write(config, updated_by):
        state["config"] = {
            **config,
            "updated_by": updated_by,
            "updated_at": "2026-09-12T00:00:00Z",
        }
        return state["config"]

    monkeypatch.setattr(
        config_store, "read", lambda: {"config": state["config"], "has_previous": True}
    )
    monkeypatch.setattr(config_store, "write", write)
    return state


@pytest.fixture(autouse=True)
def stub_features(monkeypatch):
    """
    Three products, enough to rank. Stubbed at the features() boundary so no
    test depends on whether the pipeline has run on this machine.
    """
    rows = [
        {
            "product_id": "1", "product_gid": "gid://shopify/Product/1",
            "handle": "anchor", "title": "ANCHOR CREW", "style_key": "ANCHOR CREW",
            "season": "autumn", "product_type_normalised": "crewneck",
            "signal_tags": ["pumpkin", "chunky blend", "halloween"],
            "collections": ["chunky-1"],
        },
        {
            "product_id": "2", "product_gid": "gid://shopify/Product/2",
            "handle": "near", "title": "NEAR MATCH CREW", "style_key": "NEAR MATCH CREW",
            "season": "autumn", "product_type_normalised": "crewneck",
            "signal_tags": ["pumpkin", "chunky blend"],
            "collections": ["chunky-1"],
        },
        {
            "product_id": "3", "product_gid": "gid://shopify/Product/3",
            "handle": "far", "title": "FAR CREW", "style_key": "FAR CREW",
            "season": "autumn", "product_type_normalised": "crewneck",
            "signal_tags": ["chunky blend"],
            "collections": [],
        },
    ]
    monkeypatch.setattr(preview, "features", lambda: rows)
    # (per-product units, build_blocks' per-style map). None means an older
    # units.json, so preview derives totals from the rows above.
    monkeypatch.setattr(preview, "units", lambda: ({}, None))
    monkeypatch.setattr(preview, "_prepared_cache", {})
    return rows


# ---------------------------------------------------------------------------
# GET /api/tuning
# ---------------------------------------------------------------------------

class TestGetTuning:
    def test_reports_defaults_when_nothing_is_saved(self, client):
        body = client.get("/api/tuning").json()
        assert body["saved"] == {}
        assert body["effective"]["popularity_weight"] == settings.POPULARITY_WEIGHT

    def test_exposes_the_allowed_ranges(self, client):
        """The console draws its sliders from these, so they must be present."""
        limits = client.get("/api/tuning").json()["limits"]
        assert limits["popularity_weight"][0] < limits["popularity_weight"][1]
        assert set(limits) == {"popularity_weight", "idf_power", "weight"}

    def test_lists_the_facets(self, client):
        facets = client.get("/api/tuning").json()["facets"]
        assert "motif" in facets and "collection" in facets

    def test_needs_no_token(self, client):
        assert client.get("/api/tuning").status_code == 200


# ---------------------------------------------------------------------------
# PUT /api/tuning
# ---------------------------------------------------------------------------

class TestPutTuning:
    def test_requires_a_token(self, client):
        r = client.put("/api/tuning", json={"tuning": {"popularity_weight": 1.0}})
        assert r.status_code == 401

    def test_rejects_a_wrong_token(self, client):
        r = client.put(
            "/api/tuning",
            json={"tuning": {"popularity_weight": 1.0}},
            headers={"X-YMAL-Token": "nope"},
        )
        assert r.status_code == 401

    def test_saves_with_the_right_token(self, client, stub_store):
        r = client.put(
            "/api/tuning",
            json={"tuning": {"popularity_weight": 1.0}},
            headers={"X-YMAL-Token": TOKEN},
        )
        assert r.status_code == 200
        assert stub_store["config"]["tuning"] == {"popularity_weight": 1.0}

    def test_leaves_placements_untouched(self, client, stub_store):
        """
        The whole reason this route exists instead of PUT /api/config. A tuning
        screen must not be able to lose the placements.
        """
        client.put(
            "/api/tuning",
            json={"tuning": {"idf_power": 1.5}},
            headers={"X-YMAL-Token": TOKEN},
        )
        assert stub_store["config"]["placements"] == PLACEMENTS

    def test_does_not_send_the_stamps_back(self, client, stub_store):
        """
        The stored document carries updated_at/updated_by and the validator
        rejects both on the way in. Stripping them is what stopped every save
        after a reload returning 422.
        """
        r = client.put(
            "/api/tuning",
            json={"tuning": {"idf_power": 1.5}},
            headers={"X-YMAL-Token": TOKEN},
        )
        assert r.status_code == 200

    def test_rejects_an_out_of_range_value(self, client, stub_store):
        r = client.put(
            "/api/tuning",
            json={"tuning": {"popularity_weight": 99}},
            headers={"X-YMAL-Token": TOKEN},
        )
        assert r.status_code == 422
        assert r.json()["errors"][0]["path"] == "tuning.popularity_weight"
        assert "tuning" not in stub_store["config"]

    def test_rejects_an_unknown_setting(self, client):
        r = client.put(
            "/api/tuning",
            json={"tuning": {"nonsense": 1}},
            headers={"X-YMAL-Token": TOKEN},
        )
        assert r.status_code == 422

    def test_null_tuning_removes_the_saved_block(self, client, stub_store):
        """
        "Reset to defaults" must delete the block, not store a copy of today's
        defaults — otherwise a later change to settings.py would be overridden
        by values nobody chose.
        """
        client.put(
            "/api/tuning",
            json={"tuning": {"popularity_weight": 2.0}},
            headers={"X-YMAL-Token": TOKEN},
        )
        client.put("/api/tuning", json={}, headers={"X-YMAL-Token": TOKEN})
        assert "tuning" not in stub_store["config"]


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

class TestPreview:
    def test_lists_products_to_preview_against(self, client):
        titles = [p["title"] for p in client.get("/api/tuning/products").json()]
        assert "ANCHOR CREW" in titles

    def test_ranks_under_an_unsaved_tuning(self, client):
        r = client.post(
            "/api/tuning/preview",
            json={"product_id": "1", "tuning": {"popularity_weight": 1.0}},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["anchor"]["title"] == "ANCHOR CREW"
        assert [i["title"] for i in body["items"]][0] == "NEAR MATCH CREW"

    def test_never_returns_the_anchor_itself(self, client):
        items = client.post("/api/tuning/preview", json={"product_id": "1"}).json()["items"]
        assert "ANCHOR CREW" not in [i["title"] for i in items]

    def test_saves_nothing(self, client, stub_store):
        client.post(
            "/api/tuning/preview",
            json={"product_id": "1", "tuning": {"popularity_weight": 3.0}},
        )
        assert "tuning" not in stub_store["config"]

    def test_does_not_leak_the_tuning_into_the_process(self, client):
        """
        tuning.apply assigns to the settings module, which is process-wide. A
        preview that left its values behind would change what the next nightly
        run published.
        """
        before = settings.POPULARITY_WEIGHT
        client.post(
            "/api/tuning/preview",
            json={"product_id": "1", "tuning": {"popularity_weight": 2.5}},
        )
        assert settings.POPULARITY_WEIGHT == before

    def test_restores_settings_even_when_the_product_is_missing(self, client):
        before = settings.IDF_POWER
        r = client.post(
            "/api/tuning/preview",
            json={"product_id": "nope", "tuning": {"idf_power": 3.0}},
        )
        assert r.status_code == 404
        assert settings.IDF_POWER == before

    def test_requires_a_product_id(self, client):
        assert client.post("/api/tuning/preview", json={}).status_code == 422

    def test_rejects_an_invalid_tuning(self, client):
        r = client.post(
            "/api/tuning/preview",
            json={"product_id": "1", "tuning": {"idf_power": 99}},
        )
        assert r.status_code == 422

    def test_rejects_a_silly_limit(self, client):
        r = client.post(
            "/api/tuning/preview", json={"product_id": "1", "limit": 500}
        )
        assert r.status_code == 422

    def test_needs_no_token(self, client):
        """It writes nothing, so it is a read."""
        assert client.post("/api/tuning/preview", json={"product_id": "1"}).status_code == 200

    def test_reports_the_tuning_actually_used(self, client):
        """
        The console shows this rather than what it thinks it sent, so a partial
        weights object visibly resolves against the defaults.
        """
        body = client.post(
            "/api/tuning/preview",
            json={"product_id": "1", "tuning": {"weights": {"motif": 5.0}}},
        ).json()
        assert body["tuning"]["weights"]["motif"] == 5.0
        assert body["tuning"]["weights"]["colour"] == settings.SIMILARITY_WEIGHTS["colour"]
