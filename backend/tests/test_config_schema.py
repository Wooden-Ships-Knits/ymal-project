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
        {"block": "trending", "heading": "For You", "slots": 4, "enabled": True}
    )
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
