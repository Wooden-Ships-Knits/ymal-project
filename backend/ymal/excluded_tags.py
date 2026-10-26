"""
Tags whose products Top Selling (MYNTS) and Trending must stop recommending.

For products the store still sells but should no longer push - Halloween
sweaters once the shipping cutoff has passed. They stay live and buyable; they
just drop out of the two store-wide sales lists, and the next best sellers move
up. Nothing here hides a product anywhere else.

Set from the console's Exclude by Tag tab, kept in the ymal.config document
beside tuning (so it inherits the validator, the previous-version copy and
undo), and applied by scripts/build_blocks.py on the next build - nightly, or at
once with Rebuild. The SOP for occasions is in docs/sop-excluded-tags.md.

A WHOLE tag matches, ignoring case: "halloween" does not also catch "halloween
gift". Prefix matching would sweep up tags nobody meant to list and give no
sign it had, so each tag is listed on its own and the console shows how many
products each one catches.
"""

import json

from ymal import settings

CONFIG_KEY = "excluded_tags"

# The blocks the list applies to, in the order the console names them.
BLOCKS = ("trending", "top_selling")

ACTIVE_PRODUCTS = settings.PHASE1_DIR / "active_products.json"


def _normalise(tag: str) -> str:
    return " ".join(tag.split()).lower()


def clean(tags: list) -> list:
    """
    Trim, lower-case, and drop blanks and repeats, keeping the order given.

    Only strings are cleaned. Anything else is passed through, so the validator
    reports it rather than this quietly dropping it.
    """
    seen: set[str] = set()
    cleaned = []
    for tag in tags:
        if not isinstance(tag, str):
            cleaned.append(tag)
            continue
        tag = _normalise(tag)
        if tag and tag not in seen:
            seen.add(tag)
            cleaned.append(tag)
    return cleaned


def tags_of(product: dict) -> set[str]:
    """A product's tags, lower-cased. Shopify gives them as one string."""
    raw = product.get("tags") or ""
    parts = raw if isinstance(raw, list) else raw.split(",")
    return {_normalise(t) for t in parts if isinstance(t, str) and t.strip()}


def matching(products: list[dict], tags: list[str]) -> set[str]:
    """The product gids carrying any of `tags`."""
    wanted = set(clean(tags))
    if not wanted:
        return set()
    return {p["product_gid"] for p in products if tags_of(p) & wanted}


def pool_for(block: str, eligible: set[str], excluded: set[str]) -> set[str]:
    """The products `block` may rank: eligible, minus the excluded for its blocks."""
    return eligible - excluded if block in BLOCKS else eligible


def counts(products: list[dict], tags: list[str]) -> dict[str, int]:
    """How many products each tag catches, so the console can show it."""
    return {tag: len(matching(products, [tag])) for tag in tags}


def known(products: list[dict]) -> list[str]:
    """Every tag in the catalog, for the console's picker."""
    found: set[str] = set()
    for product in products:
        found |= tags_of(product)
    return sorted(found)


def products() -> list[dict]:
    """The active products the nightly run fetched; empty before its first run."""
    try:
        return json.loads(ACTIVE_PRODUCTS.read_text())
    except FileNotFoundError:
        return []


def load() -> list[str]:
    """
    The saved list, for the pipeline.

    A failure to reach Shopify builds with nothing excluded, warned, the same
    as tuning: a pipeline that refuses to build because a settings document
    could not be read would leave every block stale.
    """
    from ymal import config_store

    try:
        config = (config_store.read() or {}).get("config") or {}
    except Exception as error:  # noqa: BLE001 - any failure means "exclude nothing"
        print(f"  WARNING: could not read excluded tags ({error}). Excluding nothing.")
        return []
    return list(config.get(CONFIG_KEY) or [])
