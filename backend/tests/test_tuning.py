"""
The ranking knobs, as the console may set them.

Two things are checked here. First, that a bad tuning document is rejected
rather than repaired - a silently-clamped weight is a console showing a number
the pipeline is not using. Second, that applying one only ever changes the
values it names, and that an absent tuning restores the settings.py defaults
rather than leaving the previous run's numbers behind.

No network and no files.
"""

import pytest

from ymal import config_schema, settings, tuning


def config(**extra):
    base = {"version": 1, "enabled": True, "placements": {}}
    base.update(extra)
    return base


def paths(errors):
    return [e["path"] for e in errors]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestTuningIsOptional:
    def test_a_config_with_no_tuning_is_valid(self):
        assert config_schema.validate(config()) == []

    def test_an_empty_tuning_is_valid(self):
        """Means "use every default", which is a legitimate thing to save."""
        assert config_schema.validate(config(tuning={})) == []

    def test_tuning_must_be_an_object(self):
        errors = config_schema.validate(config(tuning=0.4))
        assert paths(errors) == ["tuning"]


class TestPopularityWeight:
    def test_accepts_a_float(self):
        assert config_schema.validate(config(tuning={"popularity_weight": 0.8})) == []

    def test_accepts_an_int(self):
        assert config_schema.validate(config(tuning={"popularity_weight": 1})) == []

    def test_accepts_zero(self):
        """Zero is meaningful: rank on content alone, ignoring sales."""
        assert config_schema.validate(config(tuning={"popularity_weight": 0})) == []

    def test_rejects_negative(self):
        """A negative weight would rank the WORST sellers first."""
        errors = config_schema.validate(config(tuning={"popularity_weight": -0.1}))
        assert paths(errors) == ["tuning.popularity_weight"]

    def test_rejects_above_the_maximum(self):
        errors = config_schema.validate(config(tuning={"popularity_weight": 99}))
        assert paths(errors) == ["tuning.popularity_weight"]

    def test_rejects_a_string(self):
        errors = config_schema.validate(config(tuning={"popularity_weight": "0.4"}))
        assert paths(errors) == ["tuning.popularity_weight"]

    def test_rejects_a_bool(self):
        """bool is an int in Python; True must not read as a weight of 1.0."""
        errors = config_schema.validate(config(tuning={"popularity_weight": True}))
        assert paths(errors) == ["tuning.popularity_weight"]


class TestIdfPower:
    def test_accepts_the_default(self):
        assert config_schema.validate(config(tuning={"idf_power": 2.0})) == []

    def test_rejects_zero(self):
        """Zero flattens every IDF to 1.0, making rare and universal tags equal."""
        errors = config_schema.validate(config(tuning={"idf_power": 0}))
        assert paths(errors) == ["tuning.idf_power"]

    def test_rejects_above_the_maximum(self):
        errors = config_schema.validate(config(tuning={"idf_power": 10}))
        assert paths(errors) == ["tuning.idf_power"]


class TestWeights:
    def test_accepts_a_full_set(self):
        weights = {f: 1.0 for f in tuning.WEIGHT_FACETS}
        assert config_schema.validate(config(tuning={"weights": weights})) == []

    def test_accepts_a_partial_set(self):
        """Naming one facet leaves the rest at their defaults."""
        assert config_schema.validate(config(tuning={"weights": {"motif": 4.0}})) == []

    def test_rejects_an_unknown_facet(self):
        errors = config_schema.validate(config(tuning={"weights": {"sparkle": 1.0}}))
        assert paths(errors) == ["tuning.weights.sparkle"]

    def test_rejects_a_negative_weight(self):
        errors = config_schema.validate(config(tuning={"weights": {"motif": -1}}))
        assert paths(errors) == ["tuning.weights.motif"]

    def test_rejects_above_the_maximum(self):
        errors = config_schema.validate(config(tuning={"weights": {"motif": 1000}}))
        assert paths(errors) == ["tuning.weights.motif"]

    def test_accepts_zero(self):
        """Zero switches a facet off, which is a real thing to want to try."""
        assert config_schema.validate(config(tuning={"weights": {"colour": 0}})) == []

    def test_weights_must_be_an_object(self):
        errors = config_schema.validate(config(tuning={"weights": [1, 2]}))
        assert paths(errors) == ["tuning.weights"]

    def test_rejects_all_weights_at_zero(self):
        """
        Every facet at zero gives every candidate a content score of zero, and
        build_pool drops anything scoring zero - so every pool would come out
        empty. Saving that is never intended.
        """
        weights = {f: 0 for f in tuning.WEIGHT_FACETS}
        errors = config_schema.validate(config(tuning={"weights": weights}))
        assert paths(errors) == ["tuning.weights"]


class TestUnknownKeys:
    def test_rejects_an_unknown_tuning_key(self):
        """
        A typo must fail loudly. Silently ignored, the console would show a
        setting it believes is in effect and the pipeline would not use it -
        which is the failure this whole file exists to prevent.
        """
        errors = config_schema.validate(config(tuning={"popularty_weight": 0.4}))
        assert paths(errors) == ["tuning.popularty_weight"]

    def test_reports_every_problem_not_just_the_first(self):
        errors = config_schema.validate(
            config(tuning={"popularity_weight": -1, "idf_power": 99})
        )
        assert sorted(paths(errors)) == ["tuning.idf_power", "tuning.popularity_weight"]


# ---------------------------------------------------------------------------
# Applying
# ---------------------------------------------------------------------------

@pytest.fixture
def restore():
    """
    Put settings.py back afterwards. These tests mutate module state on
    purpose - that is what tuning.apply does - so leaving it changed would
    make every later test depend on execution order.
    """
    before = (
        settings.POPULARITY_WEIGHT,
        settings.IDF_POWER,
        dict(settings.SIMILARITY_WEIGHTS),
    )
    yield
    settings.POPULARITY_WEIGHT, settings.IDF_POWER, weights = before
    settings.SIMILARITY_WEIGHTS = weights


class TestApply:
    def test_sets_popularity_weight(self, restore):
        tuning.apply({"popularity_weight": 1.5})
        assert settings.POPULARITY_WEIGHT == 1.5

    def test_sets_idf_power(self, restore):
        tuning.apply({"idf_power": 1.0})
        assert settings.IDF_POWER == 1.0

    def test_sets_one_weight_and_leaves_the_others(self, restore):
        before = dict(settings.SIMILARITY_WEIGHTS)
        tuning.apply({"weights": {"motif": 9.0}})
        assert settings.SIMILARITY_WEIGHTS["motif"] == 9.0
        for facet, value in before.items():
            if facet != "motif":
                assert settings.SIMILARITY_WEIGHTS[facet] == value

    def test_an_empty_tuning_changes_nothing(self, restore):
        before = (settings.POPULARITY_WEIGHT, dict(settings.SIMILARITY_WEIGHTS))
        tuning.apply({})
        assert (settings.POPULARITY_WEIGHT, settings.SIMILARITY_WEIGHTS) == before

    def test_none_changes_nothing(self, restore):
        before = settings.POPULARITY_WEIGHT
        tuning.apply(None)
        assert settings.POPULARITY_WEIGHT == before

    def test_applying_twice_does_not_compound(self, restore):
        """
        Each apply starts from the settings.py defaults, so dropping a key
        restores that default rather than leaving the previous value behind.
        The pipeline is long-lived in the api container; a sticky value would
        mean a run using a number nobody saved.
        """
        tuning.apply({"popularity_weight": 2.0})
        tuning.apply({})
        assert settings.POPULARITY_WEIGHT == tuning.DEFAULTS["popularity_weight"]

    def test_does_not_mutate_the_defaults(self, restore):
        tuning.apply({"weights": {"motif": 9.0}})
        assert tuning.DEFAULTS["weights"]["motif"] != 9.0

    def test_returns_what_it_changed(self, restore):
        changed = tuning.apply({"popularity_weight": 1.5})
        assert "popularity_weight" in changed

    def test_returns_nothing_when_a_value_equals_the_default(self, restore):
        same = tuning.DEFAULTS["popularity_weight"]
        assert tuning.apply({"popularity_weight": same}) == {}


class TestDefaults:
    def test_defaults_mirror_settings(self):
        """
        The console shows these as the "reset" values, so a drift between them
        and settings.py would show the wrong baseline.
        """
        assert tuning.DEFAULTS["popularity_weight"] == settings.POPULARITY_WEIGHT
        assert tuning.DEFAULTS["idf_power"] == settings.IDF_POWER
        assert tuning.DEFAULTS["weights"] == settings.SIMILARITY_WEIGHTS

    def test_weight_facets_match_the_settings_keys(self):
        assert set(tuning.WEIGHT_FACETS) == set(settings.SIMILARITY_WEIGHTS)


class TestLoadAndApply:
    """
    The pipeline's entry point. Stubs config_store, so no network.

    These exist because the first version of load_and_apply read `tuning`
    straight off config_store.read() - which returns the WRAPPER
    {"config": ..., "has_previous": ...}, not the config. Every saved tuning was
    silently ignored: the console showed a weight, the pipeline used the
    default, and nothing anywhere said they disagreed. The unit tests above all
    passed, because they tested apply() and never the read path.
    """

    def test_applies_the_saved_tuning(self, restore, monkeypatch):
        from ymal import config_store

        monkeypatch.setattr(
            config_store,
            "read",
            lambda: {
                "config": {"version": 1, "tuning": {"popularity_weight": 1.25}},
                "has_previous": False,
            },
        )
        tuning.load_and_apply()
        assert settings.POPULARITY_WEIGHT == 1.25

    def test_reads_tuning_from_the_config_not_the_wrapper(self, restore, monkeypatch):
        """A `tuning` sitting beside `config` must NOT be picked up."""
        from ymal import config_store

        monkeypatch.setattr(
            config_store,
            "read",
            lambda: {
                "config": {"version": 1},
                "tuning": {"popularity_weight": 2.9},
                "has_previous": False,
            },
        )
        tuning.load_and_apply()
        assert settings.POPULARITY_WEIGHT == tuning.DEFAULTS["popularity_weight"]

    def test_uses_defaults_when_nothing_is_saved(self, restore, monkeypatch):
        from ymal import config_store

        monkeypatch.setattr(
            config_store,
            "read",
            lambda: {"config": {"version": 1}, "has_previous": False},
        )
        assert tuning.load_and_apply() == {}

    def test_uses_defaults_when_shopify_is_unreachable(self, restore, monkeypatch):
        """
        A pipeline that refuses to build because a settings document could not
        be read would be worse than one that builds with the code defaults.
        """
        from ymal import config_store

        def boom():
            raise RuntimeError("network down")

        monkeypatch.setattr(config_store, "read", boom)
        assert tuning.load_and_apply() == {}
        assert settings.POPULARITY_WEIGHT == tuning.DEFAULTS["popularity_weight"]

    def test_returns_what_it_overrode(self, restore, monkeypatch):
        from ymal import config_store

        monkeypatch.setattr(
            config_store,
            "read",
            lambda: {
                "config": {"tuning": {"weights": {"motif": 7.0}}},
                "has_previous": False,
            },
        )
        changed = tuning.load_and_apply()
        assert changed["weights"] == {"motif": 7.0}
