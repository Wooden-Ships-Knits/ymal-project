"""
Read and write the ymal.config shop metafield.

This is the only module that writes to Shopify. Everything it writes is inert
until a theme reads it: Liquid sees a metafield only if it explicitly asks for
shop.metafields.ymal.config, and no theme does yet.

Two metafields model one step of history — config and config_previous. Undo
swaps them. It is deliberately not chained: two metafields cannot represent two
steps, and letting someone undo twice expecting to go back twice is worse than
refusing.
"""

import copy
import json
from datetime import datetime, timezone

from ymal.config_schema import EMPTY_CONFIG
from ymal.shopify import graphql

NAMESPACE = "ymal"
CONFIG_KEY = "config"
PREVIOUS_KEY = "config_previous"

# Blocks whose lists the pipeline publishes as shop metafields. featured is a
# product-level metafield and recently_viewed has none at all.
PUBLISHED_BLOCK_KEYS = ("trending", "top_selling", "new_arrivals")


class NoPreviousConfig(RuntimeError):
    """Undo was called with nothing to go back to."""


class MetafieldWriteError(RuntimeError):
    """Shopify accepted the request and rejected the write."""


SHOP_ID_QUERY = """
query ShopId {
  shop { id }
}
"""

READ_QUERY = """
query YmalConfig {
  shop {
    config: metafield(namespace: "%s", key: "%s") { value }
    previous: metafield(namespace: "%s", key: "%s") { value }
  }
}
""" % (NAMESPACE, CONFIG_KEY, NAMESPACE, PREVIOUS_KEY)

PUBLISHED_QUERY = """
query YmalPublishedLists {
  shop {
    trending: metafield(namespace: "%s", key: "trending") { value }
    top_selling: metafield(namespace: "%s", key: "top_selling") { value }
    new_arrivals: metafield(namespace: "%s", key: "new_arrivals") { value }
  }
}
""" % (NAMESPACE, NAMESPACE, NAMESPACE)

SET_MUTATION = """
mutation SetYmalMetafields($metafields: [MetafieldsSetInput!]!) {
  metafieldsSet(metafields: $metafields) {
    metafields { key }
    userErrors { field message }
  }
}
"""


def read() -> dict:
    """
    The stored config, or an empty one if the shop has never been written to.

    A missing metafield is not an error. On a fresh shop there is simply no
    document, and the console should show an empty configuration rather than a
    failure. A failure to reach Shopify does raise — the difference between
    "no blocks are placed" and "we cannot tell you what is placed" is the whole
    point of the console's red banner.
    """
    shop = graphql(READ_QUERY)["shop"]
    stored = shop.get("config")
    previous = shop.get("previous")

    config = json.loads(stored["value"]) if stored else copy.deepcopy(EMPTY_CONFIG)
    return {"config": config, "has_previous": previous is not None}


def write(config: dict, updated_by: str) -> dict:
    """
    Store a config, keeping the current one as the undo point.

    Previous is written FIRST. If the second mutation fails, the shop still
    holds a coherent pair rather than a lost history.

    The caller validates. This function does not — validation lives in
    config_schema and is enforced at the HTTP boundary, so a bad document
    cannot reach here.
    """
    owner_id = _shop_id()
    current = read()["config"]

    stamped = dict(config)
    stamped["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    stamped["updated_by"] = updated_by

    # Both metafields in ONE mutation. Written as two, a failure on the second
    # left config_previous already overwritten with the current document — the
    # undo point destroyed by the write it was meant to protect. metafieldsSet
    # takes a list, so there is no reason to pay that risk.
    _set_metafields(
        owner_id,
        [(PREVIOUS_KEY, current), (CONFIG_KEY, stamped)],
    )
    return stamped


def undo() -> dict:
    """Restore config_previous into config."""
    # Check before fetching the shop id: there is no point paying a round trip
    # to discover there is nothing to restore.
    shop = graphql(READ_QUERY)["shop"]
    previous = shop.get("previous")

    if previous is None:
        raise NoPreviousConfig("there is no previous configuration to restore")

    restored = json.loads(previous["value"])
    _set_metafields(_shop_id(), [(CONFIG_KEY, restored)])
    return restored


def published_block_ids() -> set[str]:
    """
    Which blocks have a list published to Shopify.

    Today none of the pipeline's do — publishing is Phase 5 — so this reports
    only recently_viewed, which has nothing to publish and always works. That
    lets the console say "Trending is enabled on 2 pages but no list has been
    published yet" rather than leaving it to be discovered on the storefront.
    """
    shop = graphql(PUBLISHED_QUERY)["shop"]
    # `is not None`, not truthiness: a metafield holding an empty list is
    # present but publishes nothing, and counting it as published would defeat
    # the console warning this feeds.
    published = {key for key in PUBLISHED_BLOCK_KEYS if shop.get(key) is not None}
    published.add("recently_viewed")
    return published


_cached_shop_id: str | None = None


def _shop_id() -> str:
    """The shop's GID. Cached for the process — it never changes."""
    global _cached_shop_id
    if _cached_shop_id is None:
        _cached_shop_id = graphql(SHOP_ID_QUERY)["shop"]["id"]
    return _cached_shop_id


def _set_metafields(owner_id: str, documents: list[tuple[str, dict]]) -> None:
    """Write one or more metafields atomically, as a single mutation."""
    result = graphql(
        SET_MUTATION,
        {
            "metafields": [
                {
                    "ownerId": owner_id,
                    "namespace": NAMESPACE,
                    "key": key,
                    "type": "json",
                    "value": json.dumps(document),
                }
                for key, document in documents
            ]
        },
    )

    # Shopify returns userErrors with HTTP 200 and no GraphQL "errors" block,
    # so neither the status code nor shopify.graphql() catches this.
    errors = result["metafieldsSet"]["userErrors"]
    if errors:
        keys = ", ".join(f"{NAMESPACE}.{key}" for key, _ in documents)
        raise MetafieldWriteError(f"Shopify rejected the write to {keys}: {errors}")
