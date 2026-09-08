"""
Publish eligibility to Shopify, so the theme can enforce the rule at render time.

The rule itself lives in eligibility.py and is computed offline. The theme
cannot recompute it: Liquid sees `product.available` and store-wide inventory
totals, but never inventory BY LOCATION, so it has no way to know a product is
stocked at Bali To Produce. This module is how it finds out.

One boolean metafield per active product:

    product.metafields.ymal.eligible   true | false

Written for EVERY active product, not just the eligible ones. A product that
stops being eligible must be flipped to false; writing only the true values
would leave a stale true behind and keep showing something the rule now
excludes.

The theme fails closed - a missing metafield hides the product - so a product
this has never seen is never shown. That is deliberate: the failure mode of
this job silently lapsing should be an empty block someone notices, not a
markdown item quietly reappearing in the widget.
"""

import json

from ymal import settings
from ymal.shopify import graphql

NAMESPACE = "ymal"
ELIGIBLE_KEY = "eligible"

# metafieldsSet accepts at most 25 metafields per call.
BATCH_SIZE = 25

SET_MUTATION = """
mutation PublishEligibility($metafields: [MetafieldsSetInput!]!) {
  metafieldsSet(metafields: $metafields) {
    metafields { key }
    userErrors { field message }
  }
}
"""


class PublishError(RuntimeError):
    """Shopify accepted the request and rejected the write."""


def load_products() -> list[dict]:
    path = settings.PHASE1_DIR / "active_products.json"
    if not path.exists():
        raise SystemExit(
            f"{path} not found. Run `python -m scripts.fetch_products` first - "
            "this publishes what that produces, it does not recompute it."
        )
    return json.loads(path.read_text())


def build_metafields(products: list[dict]) -> list[dict]:
    """One MetafieldsSetInput per product. Pure - no I/O, so it is testable."""
    return [
        {
            "ownerId": product["product_gid"],
            "namespace": NAMESPACE,
            "key": ELIGIBLE_KEY,
            "type": "boolean",
            # Shopify's boolean metafield takes the STRING "true"/"false".
            # Passing a JSON boolean is rejected at the type check.
            "value": "true" if product["eligible"] else "false",
        }
        for product in products
    ]


def batched(items: list, size: int = BATCH_SIZE):
    """Yield successive chunks. metafieldsSet caps at 25 per call."""
    for start in range(0, len(items), size):
        yield items[start : start + size]


def publish(products: list[dict], dry_run: bool = False) -> dict:
    """
    Write the eligible flag for every product given.

    Returns counts. Raises PublishError on the first batch Shopify rejects,
    rather than continuing and leaving a partially-updated catalog with no
    record of where it stopped.
    """
    metafields = build_metafields(products)
    eligible = sum(1 for p in products if p["eligible"])

    if dry_run:
        return {
            "products": len(products),
            "eligible": eligible,
            "not_eligible": len(products) - eligible,
            "batches": len(list(batched(metafields))),
            "written": 0,
            "dry_run": True,
        }

    written = 0
    for index, batch in enumerate(batched(metafields), start=1):
        result = graphql(SET_MUTATION, {"metafields": batch})
        errors = result["metafieldsSet"]["userErrors"]
        if errors:
            raise PublishError(
                f"Shopify rejected batch {index} of "
                f"{len(list(batched(metafields)))} ({written} products already "
                f"written): {errors}"
            )
        written += len(batch)

    return {
        "products": len(products),
        "eligible": eligible,
        "not_eligible": len(products) - eligible,
        "batches": index,
        "written": written,
        "dry_run": False,
    }


# ------------------------------------------------------------------
# Phase 5 — pools and block lists
# ------------------------------------------------------------------
# Product references, not our own JSON copy of the product. A reference hands
# Liquid the LIVE product object - current title, price, image and available -
# so a list written at 03:00 cannot render yesterday's price at noon. It also
# means this job never needs to fetch an image or a price at all.
# See docs/config-contract.md section 2.
FEATURED_KEY = "featured"
BLOCK_KEYS = ("trending", "top_selling", "new_arrivals")

REFERENCE_LIST_TYPE = "list.product_reference"

DEFINITIONS_MUTATION = """
mutation CreateDefinition($definition: MetafieldDefinitionInput!) {
  metafieldDefinitionCreate(definition: $definition) {
    createdDefinition { id key }
    userErrors { field message code }
  }
}
"""

SHOP_ID_QUERY = """
query ShopId { shop { id } }
"""


def shop_id() -> str:
    return graphql(SHOP_ID_QUERY)["shop"]["id"]


def ensure_definitions() -> list[str]:
    """
    Create the metafield definitions if they do not exist.

    Values can be written without a definition, but then they show in the admin
    as untyped and nobody can see what they are for. TAKEN is not an error -
    the definition already exists, which is the normal case on every run after
    the first.
    """
    wanted = [
        ("PRODUCT", ELIGIBLE_KEY, "YMAL eligible", "boolean",
         "Whether this product may appear in a YMAL widget."),
        ("PRODUCT", FEATURED_KEY, "YMAL featured", REFERENCE_LIST_TYPE,
         "Products recommended alongside this one."),
    ] + [
        ("SHOP", key, f"YMAL {key.replace('_', ' ')}", REFERENCE_LIST_TYPE,
         f"The {key.replace('_', ' ')} block list.")
        for key in BLOCK_KEYS
    ]

    created = []
    for owner, key, name, field_type, description in wanted:
        result = graphql(
            DEFINITIONS_MUTATION,
            {
                "definition": {
                    "namespace": NAMESPACE,
                    "key": key,
                    "name": name,
                    "description": description,
                    "type": field_type,
                    "ownerType": owner,
                }
            },
        )
        payload = result["metafieldDefinitionCreate"]
        errors = payload["userErrors"]
        if errors:
            codes = {e.get("code") for e in errors}
            if "TAKEN" not in codes:
                raise PublishError(f"Could not define {NAMESPACE}.{key}: {errors}")
        else:
            created.append(key)
    return created


def build_pool_metafields(pools: dict, rows: list[dict]) -> list[dict]:
    """One metafield per product, holding its pool as product references."""
    gid_of = {r["product_id"]: r["product_gid"] for r in rows}
    fields = []
    for product_id, pool in pools.items():
        owner = gid_of.get(product_id)
        if not owner:
            continue
        references = [gid_of[item["product_id"]] for item in pool if item["product_id"] in gid_of]
        fields.append(
            {
                "ownerId": owner,
                "namespace": NAMESPACE,
                "key": FEATURED_KEY,
                "type": REFERENCE_LIST_TYPE,
                "value": json.dumps(references),
            }
        )
    return fields


def build_block_metafields(owner_id: str, blocks: dict[str, list[str]]) -> list[dict]:
    """One shop-level metafield per block list."""
    return [
        {
            "ownerId": owner_id,
            "namespace": NAMESPACE,
            "key": key,
            "type": REFERENCE_LIST_TYPE,
            "value": json.dumps(gids),
        }
        for key, gids in blocks.items()
    ]


def write_metafields(metafields: list[dict], label: str) -> int:
    """Write in batches of 25, raising on the first batch Shopify rejects."""
    written = 0
    batches = list(batched(metafields))
    for index, batch in enumerate(batches, start=1):
        result = graphql(SET_MUTATION, {"metafields": batch})
        errors = result["metafieldsSet"]["userErrors"]
        if errors:
            raise PublishError(
                f"Shopify rejected {label} batch {index} of {len(batches)} "
                f"({written} already written): {errors}"
            )
        written += len(batch)
    return written


def churn(previous: dict, current: dict) -> dict:
    """
    How much each pool changed since the last run.

    A nightly job that replaces most of every pool every night is not learning,
    it is thrashing - and it would make the widget look different to a returning
    shopper for no reason. Worth seeing before publishing rather than after.
    """
    if not previous:
        return {"comparable": 0, "unchanged": 0, "mean_replaced_pct": None, "churned_over_half": 0}

    comparable = 0
    unchanged = 0
    replaced_fractions = []
    big = 0

    for product_id, pool in current.items():
        before = previous.get(product_id)
        if before is None:
            continue
        comparable += 1
        was = {item["product_id"] for item in before}
        now = {item["product_id"] for item in pool}
        if was == now:
            unchanged += 1
        if was:
            fraction = len(was - now) / len(was)
            replaced_fractions.append(fraction)
            if fraction > 0.5:
                big += 1

    return {
        "comparable": comparable,
        "unchanged": unchanged,
        "mean_replaced_pct": (
            round(100 * sum(replaced_fractions) / len(replaced_fractions), 1)
            if replaced_fractions
            else None
        ),
        "churned_over_half": big,
    }
