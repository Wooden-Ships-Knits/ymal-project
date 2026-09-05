# Console API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI service the YMAL console talks to, so placing a block in Setup Widgets writes a validated config document to the shop's `ymal.config` metafield.

**Architecture:** A thin HTTP layer in `backend/app/` over three new pure-ish modules in `backend/ymal/`: a registry of blocks and page templates, a validator with no I/O, and a metafield store built on the existing GraphQL client. The browser never holds a Shopify credential — it calls our API, our API calls Shopify.

**Tech Stack:** Python 3.10+, FastAPI, uvicorn, pytest, `requests` (already present). React 18 + Vite on the frontend.

**Spec:** `docs/superpowers/specs/2026-09-05-console-api-design.md`

## Global Constraints

- **No emoji** anywhere in code, output, comments, or commit messages. Use plain text labels (`WARNING:`, `OK:`).
- **Python naming:** lowercase modules and packages (PEP 8). Logic goes in `ymal/`, runnable things outside it. Stated in `backend/README.md`.
- **`config_schema.py` performs no I/O.** It imports nothing that touches the network or disk. This mirrors `eligibility.py` and is what makes the rules testable offline.
- **Reject, never repair.** A validator that silently fixes a config makes the console show something other than the truth.
- **Shopify API version:** `2026-01`, from `settings.API_VERSION`. Do not hardcode it elsewhere.
- **Shop domain:** `wooden-ships.myshopify.com`, from `settings.SHOP`.
- **Metafield namespace:** `ymal`. Keys `config` and `config_previous`, type `json`, owner `shop`.
- **Error shape for 422:** `{"errors": [{"path": "...", "message": "..."}]}` — from `config-contract.md` §9. `frontend/src/api.js` already reads `body.errors`.
- **Auth header name:** `X-YMAL-Token`.
- **Branch:** `feat/console-api`. Commit after every task.
- **Nothing in this plan edits the Shopify theme.** No task makes anything visible to a shopper.

---

### Task 1: Test harness and dependencies

Nothing in this repo is tested yet and neither FastAPI nor pytest is installed. This task makes the next six possible and is worth its own commit so a failure here is unambiguous.

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_harness.py`
- Create: `backend/pytest.ini`

**Interfaces:**
- Consumes: nothing
- Produces: a working `pytest` invocation from `backend/`

- [ ] **Step 1: Add the dependencies**

Replace `backend/requirements.txt` with:

```
requests>=2.31.0
python-dotenv>=1.0.0
fastapi>=0.115.0
uvicorn[standard]>=0.30.0

# Test-only. Kept here rather than in a separate requirements-dev.txt: the
# image builds from this file, and a test suite that is not installed in the
# container is a test suite nobody runs in CI later.
pytest>=8.0.0
httpx>=0.27.0
```

`httpx` is required by FastAPI's `TestClient` and is used in Task 5.

- [ ] **Step 2: Install them**

Run: `pip install -r backend/requirements.txt`
Expected: installs without error. Confirm with `python3 -c "import fastapi, pytest, httpx"` printing nothing.

- [ ] **Step 3: Configure pytest**

Create `backend/pytest.ini`:

```ini
[pytest]
# Tests import `ymal` and `app`, both of which live under backend/. Running
# pytest from backend/ puts that on the path via rootdir.
testpaths = tests
python_files = test_*.py
```

- [ ] **Step 4: Write a harness test**

Create `backend/tests/__init__.py` as an empty file.

Create `backend/tests/test_harness.py`:

```python
"""
Proves the test harness can import the package under test.

Not a placeholder: `ymal` importing cleanly from `backend/` is the thing every
other test file assumes, and it is worth one test that says so out loud.
"""

def test_ymal_package_imports():
    from ymal import settings

    assert settings.SHOP == "wooden-ships.myshopify.com"
```

- [ ] **Step 5: Run it**

Run: `cd backend && python -m pytest -v`
Expected: PASS, 1 test.

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/pytest.ini backend/tests/
git commit -m "test: add pytest harness and API dependencies"
```

---

### Task 2: The registry

The five blocks and nine page templates, server-side, plus the rule for which block may go on which template. Everything downstream validates against this.

**Files:**
- Create: `backend/ymal/registry.py`
- Create: `backend/tests/test_registry.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `BLOCKS: list[dict]` — each `{id, label, description, requires_anchor, default_heading, default_slots}`
  - `PAGE_TEMPLATES: list[dict]` — each `{id, label, live, anchor}`
  - `block_ids() -> set[str]`
  - `page_template_ids() -> set[str]`
  - `block_by_id(block_id: str) -> dict | None`
  - `template_by_id(template_id: str) -> dict | None`
  - `block_allowed_on(block_id: str, template_id: str) -> bool`
  - `supported_page_templates(block_id: str) -> list[str]`
  - `MAX_BLOCKS_PER_TEMPLATE: int` (= 4)

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_registry.py`:

```python
"""
The registry mirrors frontend/src/lib/blocks.js and lib/pageTemplates.js.
Two copies exist on purpose (spec section 7) — these tests pin the server's,
which is authoritative.
"""

from ymal import registry


def test_five_blocks():
    assert registry.block_ids() == {
        "featured",
        "trending",
        "top_selling",
        "new_arrivals",
        "recently_viewed",
    }


def test_nine_page_templates():
    assert registry.page_template_ids() == {
        "product",
        "home",
        "cart",
        "collection",
        "search",
        "not_found",
        "blog",
        "account",
        "thank_you",
    }


def test_only_product_carries_an_anchor_in_v1():
    anchored = {t["id"] for t in registry.PAGE_TEMPLATES if t["anchor"]}
    assert anchored == {"product"}


def test_featured_requires_an_anchor_so_only_product_accepts_it():
    assert registry.block_allowed_on("featured", "product") is True
    assert registry.block_allowed_on("featured", "home") is False
    assert registry.block_allowed_on("featured", "cart") is False


def test_anchorless_blocks_go_anywhere():
    for template_id in registry.page_template_ids():
        assert registry.block_allowed_on("trending", template_id) is True


def test_unknown_ids_are_not_allowed():
    assert registry.block_allowed_on("nonsense", "product") is False
    assert registry.block_allowed_on("trending", "nonsense") is False


def test_supported_page_templates_for_featured_is_product_only():
    assert registry.supported_page_templates("featured") == ["product"]


def test_product_and_home_are_the_v1_templates():
    live = {t["id"] for t in registry.PAGE_TEMPLATES if t["live"]}
    assert live == {"product", "home"}


def test_default_slots_match_the_contract():
    assert registry.block_by_id("featured")["default_slots"] == 6
    assert registry.block_by_id("recently_viewed")["default_slots"] == 4
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest tests/test_registry.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'ymal.registry'`

- [ ] **Step 3: Implement the registry**

Create `backend/ymal/registry.py`:

```python
"""
The block and page-template registry — docs/config-contract.md sections 4 and 5.

This is the server's copy. frontend/src/lib/blocks.js and lib/pageTemplates.js
hold a second one, kept deliberately as a static fallback so an API outage
degrades the console to "not connected" rather than a blank screen. When the
two disagree, this file is right.

Adding a block means editing both, plus adding it to ymal/blocks/ — a block
configured here with nothing computing it produces a page that renders nothing.
"""

# At most four blocks on one page. A page of nothing but recommendations sells
# nothing.
MAX_BLOCKS_PER_TEMPLATE = 4

BLOCKS = [
    {
        "id": "featured",
        "label": "Featured Products",
        "description": "Products sharing tags with the one being viewed.",
        "requires_anchor": True,
        "default_heading": "You May Also Like",
        "default_slots": 6,
    },
    {
        "id": "trending",
        "label": "Trending Products",
        "description": "Rising: selling more in the last 14 days than the 14 before.",
        "requires_anchor": False,
        "default_heading": "Trending Now",
        "default_slots": 6,
    },
    {
        "id": "top_selling",
        "label": "Top Selling",
        "description": "Plain volume over the last 90 days.",
        "requires_anchor": False,
        "default_heading": "Top Selling",
        "default_slots": 6,
    },
    {
        "id": "new_arrivals",
        "label": "New Arrivals",
        "description": "Published in the last 30 days, newest first.",
        "requires_anchor": False,
        "default_heading": "New Arrivals",
        "default_slots": 6,
    },
    {
        "id": "recently_viewed",
        "label": "Recently Viewed",
        "description": "The shopper's own history. Lives in their browser, not on our server.",
        "requires_anchor": False,
        "default_heading": "Recently Viewed",
        "default_slots": 4,
    },
]

# `anchor` marks a template that has a product to be "about". Only `product`
# does in v1: cart and thank_you could derive one from their contents, but
# "which of four items is the anchor" is a design decision with its own rules,
# deliberately left out (config-contract.md section 4).
#
# `live` marks the two that ship first. The list is complete from the start so
# that widening later is configuration rather than a schema migration.
PAGE_TEMPLATES = [
    {"id": "product", "label": "Product Page", "live": True, "anchor": True},
    {"id": "home", "label": "Home Page", "live": True, "anchor": False},
    {"id": "cart", "label": "Cart Page", "live": False, "anchor": False},
    {"id": "collection", "label": "Collection Pages", "live": False, "anchor": False},
    {"id": "search", "label": "Search Results", "live": False, "anchor": False},
    {"id": "not_found", "label": "404 Not Found", "live": False, "anchor": False},
    {"id": "blog", "label": "Blog Posts", "live": False, "anchor": False},
    {"id": "account", "label": "Account / Login", "live": False, "anchor": False},
    {"id": "thank_you", "label": "Thank-you Page", "live": False, "anchor": False},
]


def block_ids() -> set[str]:
    return {b["id"] for b in BLOCKS}


def page_template_ids() -> set[str]:
    return {t["id"] for t in PAGE_TEMPLATES}


def block_by_id(block_id: str) -> dict | None:
    return next((b for b in BLOCKS if b["id"] == block_id), None)


def template_by_id(template_id: str) -> dict | None:
    return next((t for t in PAGE_TEMPLATES if t["id"] == template_id), None)


def block_allowed_on(block_id: str, template_id: str) -> bool:
    """
    Whether this block may be placed on this page template.

    A block needing an anchor can only go where a product exists to anchor it.
    Unknown ids are not allowed — the caller validates them separately and gets
    a better error, but this must never answer True for something it does not
    recognise.
    """
    block = block_by_id(block_id)
    template = template_by_id(template_id)
    if block is None or template is None:
        return False
    return not block["requires_anchor"] or template["anchor"]


def supported_page_templates(block_id: str) -> list[str]:
    """Every template this block may be placed on, in registry order."""
    return [
        t["id"] for t in PAGE_TEMPLATES if block_allowed_on(block_id, t["id"])
    ]
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && python -m pytest tests/test_registry.py -v`
Expected: PASS, 9 tests.

- [ ] **Step 5: Commit**

```bash
git add backend/ymal/registry.py backend/tests/test_registry.py
git commit -m "feat: add the block and page-template registry"
```

---

### Task 3: Config validation

Every rule in `config-contract.md` §6, as pure functions. This is the task with the most tests and the least I/O, and it is where the project's guarantee that a malformed config cannot reach the shop actually lives.

**Files:**
- Create: `backend/ymal/config_schema.py`
- Create: `backend/tests/test_config_schema.py`

**Interfaces:**
- Consumes: `ymal.registry` — `block_ids`, `page_template_ids`, `block_allowed_on`, `MAX_BLOCKS_PER_TEMPLATE`
- Produces:
  - `SUPPORTED_VERSIONS: tuple[int, ...]` (= `(1,)`)
  - `CURRENT_VERSION: int` (= `1`)
  - `EMPTY_CONFIG: dict` — the document returned when the shop has none
  - `validate(config: object) -> list[dict]` — returns `[{"path": str, "message": str}, ...]`; empty list means valid
  - `SERVER_OWNED_FIELDS: frozenset[str]` (= `{"updated_at", "updated_by"}`)

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_config_schema.py`:

```python
"""
Every rule in docs/config-contract.md section 6.

No network, no disk — this is the piece the storefront's correctness rests on,
so it is the piece that should be easiest to verify.
"""

import copy

import pytest

from ymal import config_schema


VALID = {
    "version": 1,
    "enabled": True,
    "placements": {
        "product": [
            {"block": "featured", "heading": "You May Also Like", "slots": 6, "enabled": True},
            {"block": "trending", "heading": "Trending Now", "slots": 6, "enabled": True},
        ],
        "home": [
            {"block": "new_arrivals", "heading": "New Arrivals", "slots": 8, "enabled": True},
        ],
    },
}


def paths(errors):
    return [e["path"] for e in errors]


def test_a_valid_config_produces_no_errors():
    assert config_schema.validate(VALID) == []


def test_empty_placements_is_valid():
    assert config_schema.validate(
        {"version": 1, "enabled": True, "placements": {}}
    ) == []


def test_the_empty_config_constant_is_itself_valid():
    assert config_schema.validate(config_schema.EMPTY_CONFIG) == []


def test_not_an_object_is_rejected():
    errors = config_schema.validate([1, 2, 3])
    assert paths(errors) == [""]


def test_unknown_version_is_rejected():
    bad = copy.deepcopy(VALID)
    bad["version"] = 2
    assert "version" in paths(config_schema.validate(bad))


def test_non_integer_version_is_rejected():
    bad = copy.deepcopy(VALID)
    bad["version"] = "1"
    assert "version" in paths(config_schema.validate(bad))


def test_non_boolean_enabled_is_rejected():
    bad = copy.deepcopy(VALID)
    bad["enabled"] = "yes"
    assert "enabled" in paths(config_schema.validate(bad))


def test_unknown_top_level_field_is_rejected():
    bad = copy.deepcopy(VALID)
    bad["colour"] = "blue"
    assert "colour" in paths(config_schema.validate(bad))


def test_server_owned_fields_are_rejected_from_a_client():
    bad = copy.deepcopy(VALID)
    bad["updated_by"] = "someone-else"
    errors = config_schema.validate(bad)
    assert "updated_by" in paths(errors)
    assert "server" in errors[0]["message"].lower()


def test_unknown_page_template_is_rejected():
    bad = copy.deepcopy(VALID)
    bad["placements"]["prodcut"] = []
    assert "placements.prodcut" in paths(config_schema.validate(bad))


def test_unknown_block_is_rejected():
    bad = copy.deepcopy(VALID)
    bad["placements"]["home"][0]["block"] = "bestsellers"
    assert "placements.home[0].block" in paths(config_schema.validate(bad))


def test_block_not_allowed_on_that_template_is_rejected():
    bad = copy.deepcopy(VALID)
    bad["placements"]["home"][0]["block"] = "featured"
    errors = config_schema.validate(bad)
    assert "placements.home[0].block" in paths(errors)
    assert "anchor" in errors[0]["message"].lower()


def test_unknown_field_in_an_entry_is_rejected():
    bad = copy.deepcopy(VALID)
    bad["placements"]["home"][0]["colour"] = "blue"
    assert "placements.home[0].colour" in paths(config_schema.validate(bad))


@pytest.mark.parametrize("heading", ["", "x" * 61])
def test_heading_outside_one_to_sixty_characters_is_rejected(heading):
    bad = copy.deepcopy(VALID)
    bad["placements"]["home"][0]["heading"] = heading
    assert "placements.home[0].heading" in paths(config_schema.validate(bad))


@pytest.mark.parametrize("heading", ["x", "x" * 60])
def test_heading_at_the_boundaries_is_accepted(heading):
    ok = copy.deepcopy(VALID)
    ok["placements"]["home"][0]["heading"] = heading
    assert config_schema.validate(ok) == []


def test_non_string_heading_is_rejected():
    bad = copy.deepcopy(VALID)
    bad["placements"]["home"][0]["heading"] = 7
    assert "placements.home[0].heading" in paths(config_schema.validate(bad))


@pytest.mark.parametrize("slots", [1, 13, 0, -1])
def test_slots_outside_two_to_twelve_is_rejected(slots):
    bad = copy.deepcopy(VALID)
    bad["placements"]["home"][0]["slots"] = slots
    errors = config_schema.validate(bad)
    assert "placements.home[0].slots" in paths(errors)
    assert "between 2 and 12" in errors[0]["message"]


@pytest.mark.parametrize("slots", [2, 12])
def test_slots_at_the_boundaries_is_accepted(slots):
    ok = copy.deepcopy(VALID)
    ok["placements"]["home"][0]["slots"] = slots
    assert config_schema.validate(ok) == []


def test_boolean_slots_is_rejected():
    # bool is a subclass of int in Python. True would otherwise sail through
    # an isinstance(x, int) check and mean 1 slot.
    bad = copy.deepcopy(VALID)
    bad["placements"]["home"][0]["slots"] = True
    assert "placements.home[0].slots" in paths(config_schema.validate(bad))


def test_duplicate_block_on_one_template_is_rejected():
    bad = copy.deepcopy(VALID)
    bad["placements"]["home"].append(
        {"block": "new_arrivals", "heading": "Again", "slots": 4, "enabled": True}
    )
    errors = config_schema.validate(bad)
    assert "placements.home[1].block" in paths(errors)
    assert "already" in errors[0]["message"].lower()


def test_the_same_block_on_two_templates_is_fine():
    ok = copy.deepcopy(VALID)
    ok["placements"]["home"].append(
        {"block": "featured", "heading": "For You", "slots": 4, "enabled": True}
    )
    ok["placements"]["home"][-1]["block"] = "trending"
    assert config_schema.validate(ok) == []


def test_more_than_four_blocks_on_one_template_is_rejected():
    bad = copy.deepcopy(VALID)
    bad["placements"]["home"] = [
        {"block": b, "heading": "H", "slots": 4, "enabled": True}
        for b in ["trending", "top_selling", "new_arrivals", "recently_viewed", "featured"]
    ]
    errors = config_schema.validate(bad)
    assert "placements.home" in paths(errors)


def test_placements_value_must_be_a_list():
    bad = copy.deepcopy(VALID)
    bad["placements"]["home"] = {"block": "trending"}
    assert "placements.home" in paths(config_schema.validate(bad))


def test_missing_required_entry_field_is_rejected():
    bad = copy.deepcopy(VALID)
    del bad["placements"]["home"][0]["slots"]
    assert "placements.home[0].slots" in paths(config_schema.validate(bad))


def test_every_error_carries_a_path_and_a_message():
    bad = {"version": 99, "enabled": "no", "placements": {"nope": []}}
    errors = config_schema.validate(bad)
    assert len(errors) >= 3
    for e in errors:
        assert set(e) == {"path", "message"}
        assert isinstance(e["path"], str)
        assert e["message"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest tests/test_config_schema.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'ymal.config_schema'`

- [ ] **Step 3: Implement the validator**

Create `backend/ymal/config_schema.py`:

```python
"""
Validation for the ymal.config document — docs/config-contract.md section 6.

Pure functions, no I/O. The rule this file enforces is that a malformed config
never reaches the shop: a config that silently blanks every block is invisible
until traffic drops, so we reject rather than repair, and reject unknown fields
rather than ignore them.

Returns a list of {path, message} in the shape the contract specifies and
frontend/src/api.js already reads.
"""

from ymal import registry

CURRENT_VERSION = 1

# The theme refuses a document it does not understand rather than
# half-rendering one, so the server must not write a version the theme has
# never heard of. Widen this only alongside the theme.
SUPPORTED_VERSIONS = (1,)

MIN_HEADING = 1
MAX_HEADING = 60
MIN_SLOTS = 2
MAX_SLOTS = 12

TOP_LEVEL_FIELDS = frozenset({"version", "enabled", "placements"})

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


def _is_int(value: object) -> bool:
    """
    True for a genuine integer.

    bool is a subclass of int in Python, so `isinstance(True, int)` is True and
    an unguarded check would read `slots: true` as one slot.
    """
    return isinstance(value, int) and not isinstance(value, bool)
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && python -m pytest tests/test_config_schema.py -v`
Expected: PASS. If `test_block_not_allowed_on_that_template_is_rejected` or `test_duplicate_block_on_one_template_is_rejected` fail on `errors[0]`, it is because more than one error was produced — assert against the matching error rather than the first, and fix the test, not the validator.

- [ ] **Step 5: Run the whole suite**

Run: `cd backend && python -m pytest -v`
Expected: PASS, all tests.

- [ ] **Step 6: Commit**

```bash
git add backend/ymal/config_schema.py backend/tests/test_config_schema.py
git commit -m "feat: validate the config document against the contract"
```

---

### Task 4: The metafield store

Read and write `shop.ymal.config` through the existing GraphQL client.

**Files:**
- Create: `backend/ymal/config_store.py`
- Create: `backend/tests/test_config_store.py`

**Interfaces:**
- Consumes: `ymal.shopify.graphql`, `ymal.config_schema.EMPTY_CONFIG`, `ymal.registry`
- Produces:
  - `read() -> dict` — `{"config": dict, "has_previous": bool}`
  - `write(config: dict, updated_by: str) -> dict` — returns the stored document
  - `undo() -> dict` — returns the restored document
  - `published_block_ids() -> set[str]`
  - `NoPreviousConfig(RuntimeError)`
  - `MetafieldWriteError(RuntimeError)`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_config_store.py`. These stub `ymal.shopify.graphql` via monkeypatch — no network.

```python
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


def test_write_copies_the_current_config_to_previous_first(calls):
    calls.responses.append({"shop": {"id": "gid://shopify/Shop/1"}})
    calls.responses.append(metafield_response(config={"old": True}))
    calls.responses.append({"metafieldsSet": {"metafields": [], "userErrors": []}})
    calls.responses.append({"metafieldsSet": {"metafields": [], "userErrors": []}})

    config_store.write({"version": 1, "enabled": True, "placements": {}}, "web-team")

    mutations = [c for c in calls if "metafieldsSet" in c["query"]]
    assert len(mutations) == 2
    first_key = mutations[0]["variables"]["metafields"][0]["key"]
    second_key = mutations[1]["variables"]["metafields"][0]["key"]
    assert first_key == "config_previous"
    assert second_key == "config"


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
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest tests/test_config_store.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'ymal.config_store'`

- [ ] **Step 3: Implement the store**

Create `backend/ymal/config_store.py`:

```python
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
mutation SetYmalMetafield($metafields: [MetafieldsSetInput!]!) {
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

    _set_metafield(owner_id, PREVIOUS_KEY, current)

    stamped = dict(config)
    stamped["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    stamped["updated_by"] = updated_by

    _set_metafield(owner_id, CONFIG_KEY, stamped)
    return stamped


def undo() -> dict:
    """Restore config_previous into config."""
    owner_id = _shop_id()
    shop = graphql(READ_QUERY)["shop"]
    previous = shop.get("previous")

    if previous is None:
        raise NoPreviousConfig("there is no previous configuration to restore")

    restored = json.loads(previous["value"])
    _set_metafield(owner_id, CONFIG_KEY, restored)
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
    published = {key for key in PUBLISHED_BLOCK_KEYS if shop.get(key)}
    published.add("recently_viewed")
    return published


def _shop_id() -> str:
    return graphql(SHOP_ID_QUERY)["shop"]["id"]


def _set_metafield(owner_id: str, key: str, document: dict) -> None:
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
            ]
        },
    )

    # Shopify returns userErrors with HTTP 200 and no GraphQL "errors" block,
    # so neither the status code nor shopify.graphql() catches this.
    errors = result["metafieldsSet"]["userErrors"]
    if errors:
        raise MetafieldWriteError(
            f"Shopify rejected the write to {NAMESPACE}.{key}: {errors}"
        )
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && python -m pytest tests/test_config_store.py -v`
Expected: PASS, 8 tests.

- [ ] **Step 5: Commit**

```bash
git add backend/ymal/config_store.py backend/tests/test_config_store.py
git commit -m "feat: read and write the ymal.config shop metafield"
```

---

### Task 5: The API

The HTTP layer, the auth dependency, and the deployment changes that make the `api` service runnable. These land together because an API that compose cannot start is not a deliverable.

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/test_api.py`
- Modify: `.env.example`
- Modify: `docker-compose.yml:56-70` (remove the `api` profile gate)

**Interfaces:**
- Consumes: `ymal.config_store`, `ymal.config_schema`, `ymal.registry`
- Produces: an ASGI app at `app.main:app`, serving `GET /api/config`, `PUT /api/config`, `POST /api/config/undo`, `GET /api/blocks`, `GET /api/page-templates`, `GET /api/health`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_api.py`:

```python
"""
The HTTP boundary. config_store is stubbed — these tests cover routing, auth
and status codes, not Shopify.
"""

import os

import pytest
from fastapi.testclient import TestClient

TOKEN = "test-token-value"
os.environ["YMAL_API_TOKEN"] = TOKEN

from app.main import app  # noqa: E402  — import after the env var is set

from ymal import config_store  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def stub_store(monkeypatch):
    state = {"config": {"version": 1, "enabled": True, "placements": {}}}

    monkeypatch.setattr(
        config_store, "read", lambda: {"config": state["config"], "has_previous": True}
    )
    # Must include updated_at: put_config reads it off the returned document to
    # build its response, so a stub without it fails with a KeyError rather
    # than testing anything.
    monkeypatch.setattr(
        config_store,
        "write",
        lambda config, updated_by: {
            **config,
            "updated_by": updated_by,
            "updated_at": "2026-09-05T00:00:00Z",
        },
    )
    monkeypatch.setattr(config_store, "undo", lambda: state["config"])
    monkeypatch.setattr(
        config_store, "published_block_ids", lambda: {"recently_viewed"}
    )
    return state


VALID_CONFIG = {"version": 1, "enabled": True, "placements": {}}


def test_health_needs_no_token(client):
    assert client.get("/api/health").status_code == 200


def test_get_config_needs_no_token(client):
    response = client.get("/api/config")
    assert response.status_code == 200
    assert response.json()["has_previous"] is True


def test_put_without_a_token_is_refused(client):
    response = client.put("/api/config", json=VALID_CONFIG)
    assert response.status_code == 401


def test_put_with_a_wrong_token_is_refused(client):
    response = client.put(
        "/api/config", json=VALID_CONFIG, headers={"X-YMAL-Token": "wrong"}
    )
    assert response.status_code == 401


def test_put_with_the_right_token_succeeds(client):
    response = client.put(
        "/api/config", json=VALID_CONFIG, headers={"X-YMAL-Token": TOKEN}
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_an_invalid_config_returns_422_with_field_errors(client):
    bad = {
        "version": 1,
        "enabled": True,
        "placements": {"home": [{"block": "trending", "heading": "H", "slots": 40, "enabled": True}]},
    }
    response = client.put("/api/config", json=bad, headers={"X-YMAL-Token": TOKEN})

    assert response.status_code == 422
    errors = response.json()["errors"]
    assert errors[0]["path"] == "placements.home[0].slots"
    assert "between 2 and 12" in errors[0]["message"]


def test_an_invalid_config_is_not_written(client, monkeypatch):
    written = []
    monkeypatch.setattr(
        config_store, "write", lambda config, updated_by: written.append(config)
    )

    client.put(
        "/api/config",
        json={"version": 99, "enabled": True, "placements": {}},
        headers={"X-YMAL-Token": TOKEN},
    )

    assert written == []


def test_undo_without_a_previous_config_returns_409(client, monkeypatch):
    def raise_no_previous():
        raise config_store.NoPreviousConfig("nothing to restore")

    monkeypatch.setattr(config_store, "undo", raise_no_previous)

    response = client.post("/api/config/undo", headers={"X-YMAL-Token": TOKEN})
    assert response.status_code == 409


def test_blocks_lists_five_with_publish_state(client):
    blocks = client.get("/api/blocks").json()

    assert len(blocks) == 5
    by_id = {b["id"]: b for b in blocks}
    assert by_id["recently_viewed"]["list_published"] is True
    assert by_id["trending"]["list_published"] is False
    assert by_id["featured"]["supported_page_templates"] == ["product"]


def test_page_templates_lists_nine(client):
    templates = client.get("/api/page-templates").json()

    assert len(templates) == 9
    assert {t["id"] for t in templates if t["live"]} == {"product", "home"}


def test_a_shopify_failure_is_not_flattened_into_an_empty_config(client, monkeypatch):
    def raise_network():
        raise RuntimeError("connection refused")

    monkeypatch.setattr(config_store, "read", raise_network)

    response = client.get("/api/config")
    assert response.status_code == 502
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest tests/test_api.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 3: Implement the API**

Create `backend/app/__init__.py` as an empty file.

Create `backend/app/main.py`:

```python
"""
The console's API.

Thin on purpose: it parses requests, calls into ymal/, and formats responses.
Every rule lives in ymal/config_schema.py, every Shopify call in
ymal/config_store.py. Nothing here decides anything.

Run:  cd backend && uvicorn app.main:app --reload
"""

import os
import secrets

from dotenv import load_dotenv
from fastapi import Body, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

from ymal import config_schema, config_store, registry, settings

load_dotenv(settings.REPO_ROOT / ".env", override=True)

API_TOKEN = os.getenv("YMAL_API_TOKEN", "")

# Refuse to start rather than run open. A service that fails to start is a
# visible problem; a service quietly serving writes without auth is not.
# Follows fetch_products, which refuses to run when no location matches the
# Bali pattern rather than silently classifying the catalog as fixed stock.
if not API_TOKEN:
    raise RuntimeError(
        "YMAL_API_TOKEN is not set. Add it to .env at the repository root — "
        "the API will not start without it, because writes reach the live shop."
    )

app = FastAPI(title="YMAL Console API")


def require_token(x_ymal_token: str = Header(default="")) -> None:
    """
    Guard every write.

    compare_digest rather than == so a wrong token takes the same time to
    reject regardless of how much of it was right.
    """
    if not secrets.compare_digest(x_ymal_token, API_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid or missing API token")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/config")
def get_config() -> dict:
    try:
        return config_store.read()
    except Exception as exc:
        # Deliberately NOT an empty config. "We cannot tell you what is placed"
        # is a different answer from "nothing is placed", and the console's red
        # banner exists to show the difference.
        raise HTTPException(
            status_code=502, detail=f"Could not read the configuration: {exc}"
        )


@app.put("/api/config")
def put_config(
    config: dict = Body(...),
    x_ymal_token: str = Header(default=""),
) -> JSONResponse:
    require_token(x_ymal_token)

    errors = config_schema.validate(config)
    if errors:
        return JSONResponse(status_code=422, content={"errors": errors})

    try:
        stored = config_store.write(config, updated_by="web-team")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not save: {exc}")

    return JSONResponse(
        status_code=200,
        content={
            "ok": True,
            "version": stored["version"],
            "updated_at": stored["updated_at"],
        },
    )


@app.post("/api/config/undo")
def post_undo(x_ymal_token: str = Header(default="")) -> dict:
    require_token(x_ymal_token)

    try:
        restored = config_store.undo()
    except config_store.NoPreviousConfig as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not undo: {exc}")

    return {"ok": True, "config": restored}


@app.get("/api/blocks")
def get_blocks() -> list[dict]:
    try:
        published = config_store.published_block_ids()
    except Exception:
        # A block list we cannot check is reported as unpublished. The console
        # then warns about a block that may in fact be fine, which is the safe
        # direction to be wrong in.
        published = set()

    return [
        {
            "id": block["id"],
            "label": block["label"],
            "description": block["description"],
            "requires_anchor": block["requires_anchor"],
            "supported_page_templates": registry.supported_page_templates(block["id"]),
            "default_heading": block["default_heading"],
            "default_slots": block["default_slots"],
            "list_published": block["id"] in published,
        }
        for block in registry.BLOCKS
    ]


@app.get("/api/page-templates")
def get_page_templates() -> list[dict]:
    return [
        {"id": t["id"], "label": t["label"], "live": t["live"], "anchor": t["anchor"]}
        for t in registry.PAGE_TEMPLATES
    ]
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && python -m pytest tests/test_api.py -v`
Expected: PASS, 11 tests.

- [ ] **Step 5: Add the token to the env template**

Append to `.env.example`:

```
# Guards every write to the console API. The API refuses to start without it.
# Generate one with: python3 -c "import secrets; print(secrets.token_urlsafe(32))"
YMAL_API_TOKEN=
```

Then generate a real one and add it to `.env` (which is gitignored).

- [ ] **Step 6: Un-gate the api service**

In `docker-compose.yml`, in the `api` service, delete these two lines:

```yaml
    profiles: ["api"]
```

and replace the comment above the service:

```yaml
  # The console's API. No longer profile-gated: backend/app exists, so this
  # starts with `docker compose up` alongside the console.
  api:
```

Leave `web`'s missing `depends_on: api` exactly as it is — the comment there explains that nginx resolves the upstream lazily so the console loads and says "not connected" rather than failing to boot, and that property is still worth having.

- [ ] **Step 7: Run the whole suite**

Run: `cd backend && python -m pytest -v`
Expected: PASS, all tests.

- [ ] **Step 8: Smoke the real server**

```bash
cd backend && uvicorn app.main:app --port 8000 &
curl -s localhost:8000/api/health
curl -s localhost:8000/api/page-templates
```

Expected: `{"ok":true}` and the nine templates. `GET /api/config` will reach Shopify — a 200 or a 502 both prove the wiring; a 502 here is the metafield scope blocker, not a bug in this task.

- [ ] **Step 9: Commit**

```bash
git add backend/app/ backend/tests/test_api.py .env.example docker-compose.yml
git commit -m "feat: serve the console API"
```

---

### Task 6: The token prompt

The console must send the token without it being compiled into the bundle, where anyone opening the page could read it.

**Files:**
- Create: `frontend/src/auth/useToken.js`
- Create: `frontend/src/auth/TokenPrompt.jsx`
- Modify: `frontend/src/api.js`
- Modify: `frontend/src/setup/SetupWidgets.jsx`

**Interfaces:**
- Consumes: `app/main.py`'s 401 response and `X-YMAL-Token` header
- Produces:
  - `getToken() -> string`, `setToken(value)`, `clearToken()` from `auth/useToken.js`
  - `<TokenPrompt onSubmit={fn} onCancel={fn} />` from `auth/TokenPrompt.jsx`

- [ ] **Step 1: Store the token**

Create `frontend/src/auth/useToken.js`:

```javascript
/*
 * The console's write token.
 *
 * sessionStorage, never localStorage and never a VITE_ env var. A VITE_
 * variable is compiled into the bundle and readable by anyone who opens the
 * page, which would make a shared secret public. sessionStorage dies with the
 * tab, so a shared machine does not keep it.
 */
const KEY = 'ymal:token'

export function getToken() {
  try {
    return sessionStorage.getItem(KEY) || ''
  } catch (e) {
    // Private browsing throws rather than returning null.
    return ''
  }
}

export function setToken(value) {
  try {
    sessionStorage.setItem(KEY, value)
  } catch (e) {
    /* the write still works this session; it just will not survive a reload */
  }
}

export function clearToken() {
  try {
    sessionStorage.removeItem(KEY)
  } catch (e) {
    /* nothing to clear */
  }
}
```

- [ ] **Step 2: Send it on writes**

In `frontend/src/api.js`, add the import at the top:

```javascript
import { getToken } from './auth/useToken'
```

Then replace the `put` and `post` exports at the bottom of the file:

```javascript
// Writes carry the token; reads do not need one. The header name matches
// app/main.py's require_token.
const withToken = (options) => ({
  ...options,
  headers: { 'Content-Type': 'application/json', 'X-YMAL-Token': getToken() },
})

export const get = (path) => request(path)
export const put = (path, data) =>
  request(path, withToken({ method: 'PUT', body: JSON.stringify(data) }))
export const post = (path, data) =>
  request(path, withToken({ method: 'POST', body: JSON.stringify(data) }))
```

- [ ] **Step 3: Build the prompt**

Create `frontend/src/auth/TokenPrompt.jsx`:

```jsx
import { useState } from 'react'
import { setToken } from './useToken'

/*
 * Shown when a write comes back 401. Not a login screen — the console reads
 * fine without it, and this only appears at the moment someone tries to change
 * something.
 */
export default function TokenPrompt({ onSubmit, onCancel }) {
  const [value, setValue] = useState('')

  const submit = (event) => {
    event.preventDefault()
    if (!value) return
    setToken(value)
    onSubmit()
  }

  return (
    <form className="note" onSubmit={submit} style={{ marginBottom: 18 }}>
      <h3>Password needed to save</h3>
      <p>
        Saving writes to the live Shopify shop. Ask the web team for the console
        password if you do not have it.
      </p>
      <input
        type="password"
        value={value}
        autoFocus
        onChange={(e) => setValue(e.target.value)}
        style={{ padding: '6px 8px', minWidth: 260, marginRight: 8 }}
      />
      <button type="submit">Save and retry</button>
      <button type="button" onClick={onCancel} style={{ marginLeft: 8 }}>
        Cancel
      </button>
    </form>
  )
}
```

- [ ] **Step 4: Wire it into Setup Widgets**

In `frontend/src/setup/SetupWidgets.jsx`, add the import:

```javascript
import TokenPrompt from '../auth/TokenPrompt'
```

Add state beside the existing `useState` calls:

```javascript
const [needsToken, setNeedsToken] = useState(false)
const [pending, setPending] = useState(null)
```

Replace the body of `apply` with a version that remembers the attempted save so it can be retried after the password is entered:

```javascript
  const save = (next) => {
    setSaving(true)
    return saveConfig(next)
      .then(() => setNeedsToken(false))
      .catch((err) => {
        if (err.status === 401) {
          setNeedsToken(true)
          setPending(next)
        } else {
          setError(err.message)
        }
      })
      .finally(() => setSaving(false))
  }

  const apply = (templateId, rows) => {
    const next = {
      ...config,
      placements: { ...config.placements, [templateId]: rows },
    }
    setConfig(next)
    setEditing(null)
    save(next)
  }
```

Render the prompt above the existing error banner in the returned JSX:

```jsx
      {needsToken && (
        <TokenPrompt
          onSubmit={() => save(pending)}
          onCancel={() => setNeedsToken(false)}
        />
      )}
```

- [ ] **Step 5: Verify in the browser**

Run: `cd frontend && npm run dev`

With the API running, place a block and save. The password prompt appears. Enter a wrong password: the prompt stays and nothing is written. Enter the right one: it saves and the prompt disappears. Reload: the placement persists and no prompt appears for a read.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/auth/ frontend/src/api.js frontend/src/setup/SetupWidgets.jsx
git commit -m "feat: prompt for the write token instead of bundling it"
```

---

### Task 7: Unpublished-list warning

The console can now learn something it could not know on its own: that a block is placed but has no list behind it.

**Files:**
- Create: `frontend/src/setup/useBlockStatus.js`
- Modify: `frontend/src/setup/SetupWidgets.jsx`

**Interfaces:**
- Consumes: `GET /api/blocks` via the existing `getBlockStatus()` in `setup/api.js`
- Produces: `useBlockStatus() -> {byId, loaded}` where `byId` maps block id to the API's block object

- [ ] **Step 1: Fetch the status**

Create `frontend/src/setup/useBlockStatus.js`:

```javascript
import { useEffect, useState } from 'react'
import { getBlockStatus } from './api'

/*
 * Server-side block status, merged over the static list in lib/blocks.js.
 *
 * The static list stays as the fallback (spec section 7): if this fetch fails
 * the console still renders every card, it just cannot warn about unpublished
 * lists. A blank console would be worse than a console missing one warning.
 */
export default function useBlockStatus() {
  const [byId, setById] = useState({})
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    getBlockStatus()
      .then((blocks) => {
        setById(Object.fromEntries(blocks.map((b) => [b.id, b])))
        setLoaded(true)
      })
      .catch(() => setLoaded(false))
  }, [])

  return { byId, loaded }
}
```

- [ ] **Step 2: Warn about placed blocks with no list**

In `frontend/src/setup/SetupWidgets.jsx`, add:

```javascript
import useBlockStatus from './useBlockStatus'
```

Inside the component, beside the other hooks:

```javascript
  const { byId: blockStatus, loaded: statusLoaded } = useBlockStatus()

  // Blocks placed and enabled somewhere, whose list the pipeline has not
  // published. They render nothing on the storefront, and that should be
  // visible here rather than discovered there.
  const unpublished = statusLoaded
    ? [
        ...new Set(
          Object.values(config?.placements || {})
            .flat()
            .filter((row) => row.enabled)
            .map((row) => row.block)
            .filter((id) => blockStatus[id] && !blockStatus[id].list_published)
        ),
      ]
    : []
```

Render above the page-template cards:

```jsx
      {unpublished.length > 0 && (
        <div className="note" style={{ marginBottom: 18 }}>
          <h3>WARNING: placed, but nothing published yet</h3>
          <p>
            {unpublished.map((id) => blockStatus[id].label).join(', ')} —
            configured here, but the pipeline has not published a list. These
            blocks render nothing on the storefront until it does.
          </p>
        </div>
      )}
```

- [ ] **Step 3: Verify in the browser**

Run: `cd frontend && npm run dev`

Place Trending on the Home Page and save. The warning appears, because no list is published (Phase 5 has not happened). Untick the block and the warning goes.

- [ ] **Step 4: Run the full backend suite one more time**

Run: `cd backend && python -m pytest -v`
Expected: PASS, all tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/setup/
git commit -m "feat: warn when a placed block has no published list"
```

---

## Manual verification

Run after Task 7, from spec §8. Requires the metafield write scope (§9 blocker).

- [ ] Unset `YMAL_API_TOKEN` and start the API. It refuses to start.
- [ ] Set it, start again, open the console. The red banner is gone.
- [ ] Place Trending on the Home Page, "Trending Now", 8 slots. Save. Enter a wrong password: refused, nothing written. Enter the right one: saved.
- [ ] Reload. The placement persists.
- [ ] Read `shop.ymal.config` in the Shopify admin. It matches what the console shows, including `updated_at` and `updated_by`.
- [ ] Undo. The placement reverts, in the console and on the shop.
- [ ] `curl -X PUT` a config with 40 slots. 422, field-level message, stored document unchanged.
- [ ] Open the storefront. Visually identical throughout — no theme reads any of this.
