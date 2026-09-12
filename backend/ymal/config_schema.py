"""
Validation for the ymal.config document — docs/config-contract.md section 6.

Pure functions, no I/O. The rule this file enforces is that a malformed config
never reaches the shop: a config that silently blanks every block is invisible
until traffic drops, so we reject rather than repair, and reject unknown fields
rather than ignore them.

Returns a list of {path, message} in the shape the contract specifies and
frontend/src/api.js already reads.
"""

from ymal import registry, tuning

CURRENT_VERSION = 1

# The theme refuses a document it does not understand rather than
# half-rendering one, so the server must not write a version the theme has
# never heard of. Widen this only alongside the theme.
SUPPORTED_VERSIONS = (1,)

MIN_HEADING = 1
MAX_HEADING = 60
MIN_SLOTS = 2
MAX_SLOTS = 12

TOP_LEVEL_FIELDS = frozenset({"version", "enabled", "placements", "tuning"})

# Written by the server on every save. A client that supplies them is asking
# us to record an audit trail it authored, which is not an audit trail.
SERVER_OWNED_FIELDS = frozenset({"updated_at", "updated_by"})

ENTRY_FIELDS = frozenset({"block", "heading", "slots", "enabled"})

EMPTY_CONFIG = {
    "version": CURRENT_VERSION,
    "enabled": True,
    "placements": {},
}


def validate(config: object) -> list[dict]:
    """
    Check a config document. Returns [] if valid, otherwise every problem
    found — all of them, not just the first, so the console can show a form
    with each bad field marked rather than one error at a time.
    """
    if not isinstance(config, dict):
        return [{"path": "", "message": "config must be an object"}]

    errors: list[dict] = []
    errors += _check_top_level(config)
    errors += _check_placements(config.get("placements"))
    errors += _check_tuning(config.get("tuning"))
    return errors


def _check_top_level(config: dict) -> list[dict]:
    errors: list[dict] = []

    version = config.get("version")
    if not _is_int(version):
        errors.append({"path": "version", "message": "must be an integer"})
    elif version not in SUPPORTED_VERSIONS:
        supported = ", ".join(str(v) for v in SUPPORTED_VERSIONS)
        errors.append(
            {"path": "version", "message": f"unsupported version, expected one of: {supported}"}
        )

    if not isinstance(config.get("enabled"), bool):
        errors.append({"path": "enabled", "message": "must be true or false"})

    if "placements" not in config:
        errors.append({"path": "placements", "message": "is required"})
    elif not isinstance(config["placements"], dict):
        errors.append({"path": "placements", "message": "must be an object"})

    for field in sorted(set(config) - TOP_LEVEL_FIELDS):
        if field in SERVER_OWNED_FIELDS:
            errors.append(
                {"path": field, "message": "is set by the server and must not be sent"}
            )
        else:
            errors.append({"path": field, "message": "is not a known field"})

    return errors


def _check_placements(placements: object) -> list[dict]:
    if not isinstance(placements, dict):
        return []  # already reported by _check_top_level

    errors: list[dict] = []
    known_templates = registry.page_template_ids()

    for template_id, entries in placements.items():
        path = f"placements.{template_id}"

        if template_id not in known_templates:
            errors.append({"path": path, "message": "is not a known page template"})
            continue

        if not isinstance(entries, list):
            errors.append({"path": path, "message": "must be a list of blocks"})
            continue

        if len(entries) > registry.MAX_BLOCKS_PER_TEMPLATE:
            errors.append(
                {
                    "path": path,
                    "message": f"at most {registry.MAX_BLOCKS_PER_TEMPLATE} blocks per page",
                }
            )

        errors += _check_entries(template_id, entries)

    return errors


def _check_entries(template_id: str, entries: list) -> list[dict]:
    errors: list[dict] = []
    seen: set[str] = set()
    known_blocks = registry.block_ids()

    for index, entry in enumerate(entries):
        path = f"placements.{template_id}[{index}]"

        if not isinstance(entry, dict):
            errors.append({"path": path, "message": "must be an object"})
            continue

        block = entry.get("block")
        if block not in known_blocks:
            errors.append({"path": f"{path}.block", "message": "is not a known block"})
        elif block in seen:
            errors.append(
                {"path": f"{path}.block", "message": "is already placed on this page"}
            )
        elif not registry.block_allowed_on(block, template_id):
            errors.append(
                {
                    "path": f"{path}.block",
                    "message": "needs an anchor product and this page has none",
                }
            )
        else:
            seen.add(block)

        heading = entry.get("heading")
        if not isinstance(heading, str):
            errors.append({"path": f"{path}.heading", "message": "must be a string"})
        elif not MIN_HEADING <= len(heading) <= MAX_HEADING:
            errors.append(
                {
                    "path": f"{path}.heading",
                    "message": f"must be {MIN_HEADING} to {MAX_HEADING} characters",
                }
            )

        slots = entry.get("slots")
        if not _is_int(slots):
            errors.append({"path": f"{path}.slots", "message": "must be an integer"})
        elif not MIN_SLOTS <= slots <= MAX_SLOTS:
            errors.append(
                {
                    "path": f"{path}.slots",
                    "message": f"must be between {MIN_SLOTS} and {MAX_SLOTS}",
                }
            )

        if not isinstance(entry.get("enabled"), bool):
            errors.append({"path": f"{path}.enabled", "message": "must be true or false"})

        for field in sorted(set(entry) - ENTRY_FIELDS):
            errors.append({"path": f"{path}.{field}", "message": "is not a known field"})

    return errors


def _check_tuning(given: object) -> list[dict]:
    """
    The ranking knobs — docs/config-contract.md section 10.

    Optional: a config with no `tuning` means "use the settings.py defaults",
    which is what every config written before this existed says.

    Ranges come from ymal/tuning.py so there is one definition of what is
    allowed. Out of range is REJECTED, not clamped: a clamped value leaves the
    console displaying a number the pipeline is not using, which is the exact
    class of bug that had Top Selling described as 90 days while computing 14.
    """
    if given is None:
        return []
    if not isinstance(given, dict):
        return [{"path": "tuning", "message": "must be an object"}]

    errors: list[dict] = []

    errors += _check_number(
        given,
        "popularity_weight",
        tuning.MIN_POPULARITY_WEIGHT,
        tuning.MAX_POPULARITY_WEIGHT,
    )
    errors += _check_number(
        given, "idf_power", tuning.MIN_IDF_POWER, tuning.MAX_IDF_POWER
    )
    errors += _check_weights(given.get("weights"))

    for field in sorted(set(given) - tuning.KEYS):
        errors.append(
            {"path": f"tuning.{field}", "message": "is not a known tuning setting"}
        )

    return errors


def _check_weights(weights: object) -> list[dict]:
    if weights is None:
        return []
    if not isinstance(weights, dict):
        return [{"path": "tuning.weights", "message": "must be an object"}]

    errors: list[dict] = []
    for facet in sorted(weights):
        path = f"tuning.weights.{facet}"
        if facet not in tuning.WEIGHT_FACETS:
            known = ", ".join(tuning.WEIGHT_FACETS)
            errors.append(
                {"path": path, "message": f"is not a known facet, expected one of: {known}"}
            )
            continue
        if not _is_number(weights[facet]):
            errors.append({"path": path, "message": "must be a number"})
        elif not tuning.MIN_WEIGHT <= weights[facet] <= tuning.MAX_WEIGHT:
            errors.append(
                {
                    "path": path,
                    "message": f"must be between {tuning.MIN_WEIGHT} and {tuning.MAX_WEIGHT}",
                }
            )

    # Every facet at zero scores every candidate at zero, and build_pool drops
    # a candidate scoring zero — so every pool would come out empty. Caught
    # here because the symptom (a storefront with no recommendations anywhere)
    # gives no hint of the cause.
    if not errors and weights:
        resolved = tuning.resolve({"weights": weights})["weights"]
        if all(value == 0 for value in resolved.values()):
            errors.append(
                {
                    "path": "tuning.weights",
                    "message": "at least one facet must be above zero, or every pool is empty",
                }
            )

    return errors


def _check_number(given: dict, field: str, low: float, high: float) -> list[dict]:
    if field not in given:
        return []
    value = given[field]
    path = f"tuning.{field}"
    if not _is_number(value):
        return [{"path": path, "message": "must be a number"}]
    if not low <= value <= high:
        return [{"path": path, "message": f"must be between {low} and {high}"}]
    return []


def _is_number(value: object) -> bool:
    """
    True for an int or float, but not a bool.

    bool is a subclass of int, so an unguarded check reads
    `popularity_weight: true` as a weight of 1.0.
    """
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_int(value: object) -> bool:
    """
    True for a genuine integer.

    bool is a subclass of int in Python, so `isinstance(True, int)` is True and
    an unguarded check would read `slots: true` as one slot.
    """
    return isinstance(value, int) and not isinstance(value, bool)
