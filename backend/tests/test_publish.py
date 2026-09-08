"""
Publishing eligibility to product metafields.

The batching and the boolean encoding are the parts worth pinning: Shopify caps
metafieldsSet at 25 per call, and its boolean type takes the STRING "true",
not a JSON boolean.
"""

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
