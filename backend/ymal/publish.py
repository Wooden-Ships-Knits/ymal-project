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
