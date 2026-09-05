"""
config_store against a stubbed GraphQL client.

The store is thin, so these tests cover the parts that are not: that a missing
metafield reads as an empty config rather than an error, that a write stamps
the server-owned fields, and that userErrors are raised rather than ignored
(Shopify returns them with HTTP 200, so nothing else would catch them).
"""

import json

import pytest

from ymal import config_store


class Calls(list):
    """
    A list of recorded graphql() calls that also carries the queued responses.

    A plain list cannot hold an attribute, so this subclass exists purely so a
    test can write both `calls.responses.append(...)` and `for c in calls`.
    """

    def __init__(self):
        super().__init__()
        self.responses = []


@pytest.fixture
def calls(monkeypatch):
    """Record every graphql() call and return canned responses in order."""
    recorded = Calls()

    def fake_graphql(query, variables=None):
        recorded.append({"query": query, "variables": variables or {}})
        return recorded.responses.pop(0)

    monkeypatch.setattr(config_store, "graphql", fake_graphql)
    return recorded


def metafield_response(config=None, previous=None):
    return {
        "shop": {
            "config": {"value": json.dumps(config)} if config is not None else None,
            "previous": {"value": json.dumps(previous)} if previous is not None else None,
        }
    }


def test_missing_metafield_reads_as_an_empty_config(calls):
    calls.responses.append(metafield_response())

    result = config_store.read()

    assert result["config"]["placements"] == {}
    assert result["config"]["version"] == 1
    assert result["has_previous"] is False


def test_existing_metafield_is_returned_as_parsed_json(calls):
    stored = {"version": 1, "enabled": True, "placements": {"home": []}}
    calls.responses.append(metafield_response(config=stored, previous=stored))

    result = config_store.read()

    assert result["config"] == stored
    assert result["has_previous"] is True


def test_read_does_not_hand_back_the_shared_empty_config(calls):
    # A caller mutating the result must not corrupt EMPTY_CONFIG for the
    # process. read() deep-copies for exactly this reason.
    calls.responses.append(metafield_response())

    result = config_store.read()
    result["config"]["placements"]["home"] = ["mutated"]

    from ymal.config_schema import EMPTY_CONFIG

    assert EMPTY_CONFIG["placements"] == {}


def test_write_stamps_the_server_owned_fields(calls):
    calls.responses.append({"shop": {"id": "gid://shopify/Shop/1"}})
    calls.responses.append(metafield_response(config={"old": True}))
    calls.responses.append({"metafieldsSet": {"metafields": [], "userErrors": []}})
    calls.responses.append({"metafieldsSet": {"metafields": [], "userErrors": []}})

    stored = config_store.write(
        {"version": 1, "enabled": True, "placements": {}}, updated_by="web-team"
    )

    assert stored["updated_by"] == "web-team"
    assert stored["updated_at"].endswith("Z")


def test_write_does_not_mutate_the_config_it_was_given(calls):
    calls.responses.append({"shop": {"id": "gid://shopify/Shop/1"}})
    calls.responses.append(metafield_response())
    calls.responses.append({"metafieldsSet": {"metafields": [], "userErrors": []}})
    calls.responses.append({"metafieldsSet": {"metafields": [], "userErrors": []}})

    original = {"version": 1, "enabled": True, "placements": {}}
    config_store.write(original, "web-team")

    assert "updated_at" not in original


def test_write_copies_the_current_config_to_previous_first(calls):
    calls.responses.append({"shop": {"id": "gid://shopify/Shop/1"}})
    calls.responses.append(metafield_response(config={"old": True}))
    calls.responses.append({"metafieldsSet": {"metafields": [], "userErrors": []}})
    calls.responses.append({"metafieldsSet": {"metafields": [], "userErrors": []}})

    config_store.write({"version": 1, "enabled": True, "placements": {}}, "web-team")

    mutations = [c for c in calls if "metafieldsSet" in c["query"]]
    assert len(mutations) == 2
    first = mutations[0]["variables"]["metafields"][0]
    second = mutations[1]["variables"]["metafields"][0]
    assert first["key"] == "config_previous"
    assert json.loads(first["value"]) == {"old": True}
    assert second["key"] == "config"


def test_user_errors_are_raised(calls):
    calls.responses.append({"shop": {"id": "gid://shopify/Shop/1"}})
    calls.responses.append(metafield_response())
    calls.responses.append(
        {
            "metafieldsSet": {
                "metafields": [],
                "userErrors": [{"field": ["value"], "message": "denied"}],
            }
        }
    )

    with pytest.raises(config_store.MetafieldWriteError) as exc:
        config_store.write({"version": 1, "enabled": True, "placements": {}}, "web-team")

    assert "denied" in str(exc.value)


def test_undo_without_a_previous_config_raises(calls):
    calls.responses.append({"shop": {"id": "gid://shopify/Shop/1"}})
    calls.responses.append(metafield_response(config={"current": True}))

    with pytest.raises(config_store.NoPreviousConfig):
        config_store.undo()


def test_undo_restores_the_previous_document(calls):
    calls.responses.append({"shop": {"id": "gid://shopify/Shop/1"}})
    calls.responses.append(
        metafield_response(config={"current": True}, previous={"older": True})
    )
    calls.responses.append({"metafieldsSet": {"metafields": [], "userErrors": []}})

    restored = config_store.undo()

    assert restored == {"older": True}
    mutations = [c for c in calls if "metafieldsSet" in c["query"]]
    assert mutations[0]["variables"]["metafields"][0]["key"] == "config"


def test_published_block_ids_reports_recently_viewed_even_with_no_metafields(calls):
    calls.responses.append(
        {"shop": {"trending": None, "top_selling": None, "new_arrivals": None}}
    )

    assert config_store.published_block_ids() == {"recently_viewed"}


def test_published_block_ids_includes_a_block_with_a_metafield(calls):
    calls.responses.append(
        {
            "shop": {
                "trending": {"value": "[]"},
                "top_selling": None,
                "new_arrivals": None,
            }
        }
    )

    assert config_store.published_block_ids() == {"recently_viewed", "trending"}
