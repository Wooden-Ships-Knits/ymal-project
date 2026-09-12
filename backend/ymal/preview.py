"""
Score one product's pool with a tuning that has not been saved.

This is what makes the console's tuning screen usable. Without it, trying a
weight means saving it, running the whole pipeline, publishing to Shopify and
looking at the storefront - so nobody would try more than twice.

Reads the feature table and unit counts off disk. Writes nothing, publishes
nothing, and touches Shopify not at all.

TWO THINGS THIS HAS TO BE CAREFUL ABOUT

`tuning.apply` works by assigning to the settings module, which is process-wide.
The api container serves preview requests concurrently with everything else, so
every call here takes a lock, snapshots the three values, and restores them in a
finally block. A preview that leaked its tuning would silently change what the
next nightly run published.

`prepare()` walks all ~260 products to build the IDF tables, and the tag table
depends on IDF_POWER. It is cached on (feature-file mtime, idf_power) so moving
a weight slider does not recompute it, while changing idf_power or rebuilding
the features correctly does.
"""

import json
import threading

from ymal import settings, similarity, tuning

# Serialises the settings swap below. Previews are a single person moving a
# slider, so there is nothing to gain from concurrency here and a correctness
# problem to avoid.
_LOCK = threading.Lock()

_features: tuple[float, list[dict]] | None = None
_prepared_cache: dict[tuple[float, float], tuple] = {}
_units: tuple[float, dict, int] | None = None


def features_path():
    return settings.DATA_DIR / "phase2" / "features.json"


def units_path():
    return settings.DATA_DIR / "blocks" / "units.json"


class NotBuilt(RuntimeError):
    """The pipeline has not produced a feature table yet."""


def _mtime(path) -> float:
    return path.stat().st_mtime if path.exists() else 0.0


def features() -> list[dict]:
    """The eligible products, reloaded when the file on disk changes."""
    global _features
    path = features_path()
    if not path.exists():
        raise NotBuilt(
            "No feature table yet. Run `python -m scripts.build_features` first."
        )
    stamp = _mtime(path)
    if _features is None or _features[0] != stamp:
        _features = (stamp, json.loads(path.read_text()))
    return _features[1]


def units() -> tuple[dict, int]:
    """
    Units sold per product gid, and the catalog's best seller.

    Optional. Absent, every product scores as equally popular - the same
    fallback build_pools takes, so a preview before build_blocks has ever run
    shows content-only ranking rather than failing.
    """
    global _units
    path = units_path()
    if not path.exists():
        return {}, 0
    stamp = _mtime(path)
    if _units is None or _units[0] != stamp:
        data = json.loads(path.read_text())["units"]
        _units = (stamp, data, max(data.values()) if data else 0)
    return _units[1], _units[2]


def _prepared(rows: list[dict]):
    """
    prepare() memoised on the feature file and idf_power.

    Keyed on idf_power because the tag IDF table is raised to that power inside
    prepare. Weights and popularity_weight are applied later, in score() and
    build_pool, so they must NOT be part of this key or the cache never hits.
    """
    key = (_mtime(features_path()), settings.IDF_POWER)
    if key not in _prepared_cache:
        # One tuning at a time is enough; this is not a long-lived cache.
        _prepared_cache.clear()
        _prepared_cache[key] = similarity.prepare(rows)
    return _prepared_cache[key]


def styles() -> list[dict]:
    """
    The anchors a preview can be run against, one per style.

    One entry per style_key rather than per product: the console asks "show me
    what this product recommends", and twelve KEY WEST colorways are twelve
    rows of the same answer.
    """
    seen: dict[str, dict] = {}
    for row in features():
        key = row["style_key"]
        if key not in seen:
            seen[key] = {
                "product_id": row["product_id"],
                "title": row["title"],
                "season": row["season"],
            }
    return sorted(seen.values(), key=lambda s: s["title"])


def rank(product_id: str, given: dict | None, limit: int = 10) -> dict:
    """
    One anchor's pool under `given`, without saving anything.

    `given` is a tuning document as the console would send it; validate it
    first. Returns the resolved tuning alongside the ranking so the console can
    show what was actually in effect rather than what it thinks it sent.
    """
    rows = features()

    before = (
        settings.POPULARITY_WEIGHT,
        settings.IDF_POWER,
        settings.SIMILARITY_WEIGHTS,
    )
    with _LOCK:
        try:
            resolved = tuning.resolve(given)
            tuning.apply(given)

            anchor = next(
                (r for r in rows if str(r["product_id"]) == str(product_id)), None
            )
            if anchor is None:
                raise LookupError(f"No eligible product with id {product_id}")

            prepared, idf, collection_idf = _prepared(rows)
            prepared_anchor = next(
                r for r in prepared if r["product_id"] == anchor["product_id"]
            )
            sold, most = units()

            pool = similarity.build_pool(
                prepared_anchor,
                prepared,
                idf,
                limit,
                collection_idf,
                sold,
                most,
            )
        finally:
            (
                settings.POPULARITY_WEIGHT,
                settings.IDF_POWER,
                settings.SIMILARITY_WEIGHTS,
            ) = before

    return {
        "anchor": {
            "product_id": anchor["product_id"],
            "title": anchor["title"],
            "season": anchor["season"],
        },
        "tuning": resolved,
        "has_sales": bool(most),
        "items": pool,
    }
