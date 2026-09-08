"""
Publishing eligibility to product metafields.

The batching and the boolean encoding are the parts worth pinning: Shopify caps
metafieldsSet at 25 per call, and its boolean type takes the STRING "true",
not a JSON boolean.
"""

import json

import pytest

from ymal import publish


PRODUCTS = [
    {"product_gid": "gid://shopify/Product/1", "title": "A", "eligible": True},
    {"product_gid": "gid://shopify/Product/2", "title": "B *SALE*", "eligible": False},
]


@pytest.fixture
def calls(monkeypatch):
    recorded = []

    def fake_graphql(query, variables=None):
        recorded.append(variables or {})
        return {"metafieldsSet": {"metafields": [], "userErrors": []}}

    monkeypatch.setattr(publish, "graphql", fake_graphql)
    return recorded


def test_booleans_are_encoded_as_strings():
    # Shopify's boolean metafield rejects a JSON true at the type check.
    fields = publish.build_metafields(PRODUCTS)

    assert fields[0]["value"] == "true"
    assert fields[1]["value"] == "false"
    assert all(isinstance(f["value"], str) for f in fields)


def test_every_product_is_written_not_only_the_eligible_ones():
    # A product that stops being eligible must be flipped to false. Writing
    # only the true values would leave a stale true behind.
    fields = publish.build_metafields(PRODUCTS)

    assert len(fields) == 2
    assert {f["ownerId"] for f in fields} == {
        "gid://shopify/Product/1",
        "gid://shopify/Product/2",
    }


def test_metafields_target_the_right_namespace_and_key():
    field = publish.build_metafields(PRODUCTS)[0]

    assert field["namespace"] == "ymal"
    assert field["key"] == "eligible"
    assert field["type"] == "boolean"


def test_batches_never_exceed_shopifys_limit():
    many = [
        {"product_gid": f"gid://shopify/Product/{i}", "eligible": True}
        for i in range(428)
    ]
    batches = list(publish.batched(publish.build_metafields(many)))

    assert all(len(b) <= 25 for b in batches)
    assert sum(len(b) for b in batches) == 428


def test_dry_run_writes_nothing(calls):
    result = publish.publish(PRODUCTS, dry_run=True)

    assert calls == []
    assert result["written"] == 0
    assert result["dry_run"] is True
    assert result["eligible"] == 1


def test_publish_writes_every_product(calls):
    result = publish.publish(PRODUCTS)

    assert len(calls) == 1
    assert result["written"] == 2
    assert result["not_eligible"] == 1


def test_a_rejected_batch_raises_and_says_how_far_it_got(monkeypatch):
    # A partial write with no record of where it stopped is worse than a loud
    # failure: the catalog is half-updated and nobody knows which half.
    seen = {"n": 0}

    def fake_graphql(query, variables=None):
        seen["n"] += 1
        if seen["n"] == 2:
            return {
                "metafieldsSet": {
                    "metafields": [],
                    "userErrors": [{"field": ["value"], "message": "denied"}],
                }
            }
        return {"metafieldsSet": {"metafields": [], "userErrors": []}}

    monkeypatch.setattr(publish, "graphql", fake_graphql)

    many = [
        {"product_gid": f"gid://shopify/Product/{i}", "eligible": True}
        for i in range(50)
    ]

    with pytest.raises(publish.PublishError) as exc:
        publish.publish(many)

    assert "denied" in str(exc.value)
    assert "25 products already written" in str(exc.value)


# ------------------------------------------------------------------
# Phase 5 — pools and block lists
# ------------------------------------------------------------------

ROWS = [
    {"product_id": "1", "product_gid": "gid://shopify/Product/1"},
    {"product_id": "2", "product_gid": "gid://shopify/Product/2"},
    {"product_id": "3", "product_gid": "gid://shopify/Product/3"},
]


def test_a_pool_is_written_as_product_references():
    # References, not our own copy of the product: Liquid then gets the LIVE
    # product, so a list written at 03:00 cannot render yesterday's price.
    pools = {"1": [{"product_id": "2"}, {"product_id": "3"}]}

    fields = publish.build_pool_metafields(pools, ROWS)

    assert len(fields) == 1
    assert fields[0]["type"] == "list.product_reference"
    assert fields[0]["ownerId"] == "gid://shopify/Product/1"
    assert json.loads(fields[0]["value"]) == [
        "gid://shopify/Product/2",
        "gid://shopify/Product/3",
    ]


def test_pool_order_is_preserved_in_the_metafield():
    # The list IS the ranking. Reordering it silently reorders the widget.
    pools = {"1": [{"product_id": "3"}, {"product_id": "2"}]}

    value = json.loads(publish.build_pool_metafields(pools, ROWS)[0]["value"])

    assert value == ["gid://shopify/Product/3", "gid://shopify/Product/2"]


def test_a_pool_entry_with_no_known_gid_is_dropped_not_written_as_null():
    pools = {"1": [{"product_id": "2"}, {"product_id": "999"}]}

    value = json.loads(publish.build_pool_metafields(pools, ROWS)[0]["value"])

    assert value == ["gid://shopify/Product/2"]


def test_block_lists_are_shop_owned():
    fields = publish.build_block_metafields(
        "gid://shopify/Shop/1", {"trending": ["gid://shopify/Product/2"]}
    )

    assert fields[0]["ownerId"] == "gid://shopify/Shop/1"
    assert fields[0]["key"] == "trending"
    assert fields[0]["type"] == "list.product_reference"


def test_churn_reports_nothing_on_a_first_run():
    result = publish.churn({}, {"1": [{"product_id": "2"}]})

    assert result["comparable"] == 0
    assert result["mean_replaced_pct"] is None


def test_an_identical_rerun_reports_zero_churn():
    # The idempotency guarantee, which is what makes this safe on a schedule.
    pools = {"1": [{"product_id": "2"}, {"product_id": "3"}]}

    result = publish.churn(pools, pools)

    assert result["unchanged"] == 1
    assert result["mean_replaced_pct"] == 0.0


def test_a_fully_replaced_pool_is_flagged():
    before = {"1": [{"product_id": "2"}]}
    after = {"1": [{"product_id": "3"}]}

    result = publish.churn(before, after)

    assert result["unchanged"] == 0
    assert result["mean_replaced_pct"] == 100.0
    assert result["churned_over_half"] == 1


def test_a_new_product_is_not_counted_as_churn():
    # It has nothing to be compared against, so counting it would read as
    # instability that did not happen.
    result = publish.churn({"1": [{"product_id": "2"}]}, {"1": [{"product_id": "2"}], "9": []})

    assert result["comparable"] == 1
    assert result["unchanged"] == 1
