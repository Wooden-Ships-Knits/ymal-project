"""
The ranking knobs the console may change, and how they reach the pipeline.

settings.py holds the defaults and remains the only place they are written
down. This module lets the `tuning` block of the ymal.config metafield override
them for a run, so the web team can retune ranking without a deploy.

WHAT IS HERE, AND WHAT DELIBERATELY IS NOT

Only knobs that change the ORDER of a pool: the facet weights, how sharply rare
tags are favoured, and how much sales volume may lift a product. The worst a
bad value can do is produce a badly-ordered row.

Eligibility and the season filter stay in code. Those decide WHETHER a product
may be shown at all, and a wrong value there puts a markdown or out-of-season
product in front of a shopper - a different class of mistake from an ugly row,
and not one a slider should be able to make. docs/config-contract.md section 10
records the same split.

HOW THE OVERRIDE WORKS

By assigning to the settings module. That is blunt, and it works here because
every consumer reads `settings.POPULARITY_WEIGHT` at call time rather than
copying it into a local at import - checked, and there is a test in
test_similarity.py's neighbourhood that would break if that changed.

apply() always starts from DEFAULTS, so a key the console has dropped goes back
to its settings.py value instead of keeping the last run's number. The api
container is long-lived and serves preview requests with arbitrary tunings; a
sticky value there would mean a nightly run using a number nobody saved.
"""

import copy

from ymal import settings

# Ranges are wide enough to be useful and narrow enough that a fat finger is
# caught. They are not claims about what is sensible - 3.0 popularity is a bad
# idea, but it is a bad idea someone may legitimately want to look at.
MIN_POPULARITY_WEIGHT = 0.0
MAX_POPULARITY_WEIGHT = 3.0

# Below 1.0 rare tags count for LESS than common ones, which inverts the whole
# point of IDF. Zero would flatten every tag to equal weight.
MIN_IDF_POWER = 0.5
MAX_IDF_POWER = 4.0

MIN_WEIGHT = 0.0
MAX_WEIGHT = 10.0

WEIGHT_FACETS = tuple(settings.SIMILARITY_WEIGHTS)

# A deep copy taken at import, so nothing downstream can reach through and
# change what "reset to default" means.
DEFAULTS = {
    "popularity_weight": settings.POPULARITY_WEIGHT,
    "idf_power": settings.IDF_POWER,
    "weights": copy.deepcopy(settings.SIMILARITY_WEIGHTS),
}

KEYS = frozenset(DEFAULTS)


def resolve(given: dict | None) -> dict:
    """
    The tuning that will actually be used: DEFAULTS with `given` laid over it.

    Weights merge per facet rather than replacing the set, so a console that
    sends only `motif` does not silently zero the other five.
    """
    out = copy.deepcopy(DEFAULTS)
    if not given:
        return out

    if "popularity_weight" in given:
        out["popularity_weight"] = given["popularity_weight"]
    if "idf_power" in given:
        out["idf_power"] = given["idf_power"]
    for facet, value in (given.get("weights") or {}).items():
        if facet in out["weights"]:
            out["weights"][facet] = value
    return out


def apply(given: dict | None) -> dict:
    """
    Point settings.py at this tuning. Returns only what differs from the
    defaults, so a caller can log the override rather than the whole document.

    Validate before calling. This assigns whatever it is handed; the guard is
    config_schema.validate, which every write path already runs.
    """
    resolved = resolve(given)

    changed: dict = {}
    if resolved["popularity_weight"] != DEFAULTS["popularity_weight"]:
        changed["popularity_weight"] = resolved["popularity_weight"]
    if resolved["idf_power"] != DEFAULTS["idf_power"]:
        changed["idf_power"] = resolved["idf_power"]
    weights = {
        f: v for f, v in resolved["weights"].items() if v != DEFAULTS["weights"][f]
    }
    if weights:
        changed["weights"] = weights

    settings.POPULARITY_WEIGHT = resolved["popularity_weight"]
    settings.IDF_POWER = resolved["idf_power"]
    settings.SIMILARITY_WEIGHTS = resolved["weights"]

    return changed


def describe(changed: dict) -> str:
    """One line for a pipeline log. Empty when nothing is overridden."""
    if not changed:
        return "tuning: settings.py defaults"

    parts = []
    for key in ("popularity_weight", "idf_power"):
        if key in changed:
            parts.append(f"{key}={changed[key]}")
    for facet, value in sorted(changed.get("weights", {}).items()):
        parts.append(f"{facet}={value}")
    return "tuning: " + ", ".join(parts)


def load_and_apply() -> dict:
    """
    Read the shop's saved tuning and apply it. Returns what changed.

    Import is local: config_store talks to Shopify, and this module is imported
    by the pure scoring path as well as by the pipeline. A failure to reach
    Shopify must not stop a run - the defaults are a correct configuration, and
    a pipeline that refuses to build because a settings document could not be
    read would be worse than one that builds with the values in the code.
    """
    from ymal import config_store

    try:
        # read() returns the WRAPPER {"config": ..., "has_previous": ...}, not
        # the config. Reading `tuning` straight off it returned None every time,
        # so the pipeline silently used the defaults no matter what was saved -
        # the console would show a weight, the storefront would not use it, and
        # nothing would say so.
        result = config_store.read() or {}
        config = result.get("config") or {}
    except Exception as error:  # noqa: BLE001 - any failure means "use defaults"
        print(f"  WARNING: could not read saved tuning ({error}). Using defaults.")
        return apply(None)

    return apply(config.get("tuning"))
