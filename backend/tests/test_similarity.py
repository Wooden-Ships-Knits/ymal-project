"""
Content similarity. Pure scoring, so all of it runs offline.

A wrong score is invisible until a customer sees a bad recommendation, which
is why the ranking rules get direct tests rather than being trusted.
"""

from ymal import settings, similarity


def row(pid, title, style, tags, season="autumn", ptype="crewneck"):
    return {
        "product_id": pid,
        "handle": title.lower().replace(" ", "-"),
        "title": title,
        "style_key": style,
        "product_type_normalised": ptype,
        "season": season,
        "signal_tags": tags,
    }


def test_a_plural_collapses_onto_its_singular():
    # stripe/stripes are separate tags in this catalog. Left alone, two
    # products sharing both look twice as similar as they are.
    vocab = {"stripe", "stripes"}
    assert similarity.depluralise("stripes", vocab) == "stripe"


def test_a_word_ending_in_s_is_not_mangled():
    # "dress" must not become "dres".
    assert similarity.depluralise("dress", {"dress"}) == "dress"


def test_facets_match_on_substring():
    assert similarity.facet_of("chunky blend") == "fabric"
    assert similarity.facet_of("cotton-vo") == "fabric"
    assert similarity.facet_of("stripe") == "motif"
    assert similarity.facet_of("neutral") == "colour"
    assert similarity.facet_of("ess 2026 release") is None


def test_a_rare_tag_outweighs_a_common_one():
    # Nearly everything is cotton; almost nothing is football.
    tag_sets = [{"cotton", "football"}] + [{"cotton"} for _ in range(99)]
    idf = similarity.inverse_document_frequency(tag_sets)

    assert idf["football"] > idf["cotton"]


def test_identical_tag_sets_score_higher_than_disjoint_ones():
    idf = {"a": 1.0, "b": 1.0}

    assert similarity.weighted_jaccard({"a"}, {"a"}, idf) == 1.0
    assert similarity.weighted_jaccard({"a"}, {"b"}, idf) == 0.0


def test_empty_tag_sets_do_not_divide_by_zero():
    assert similarity.weighted_jaccard(set(), set(), {}) == 0.0


def test_a_pool_never_contains_the_anchors_own_style():
    rows = [
        row("1", "CHARLOTTE CREW", "CHARLOTTE CREW", ["stripe", "cotton"]),
        row("2", "CHARLOTTE CREW", "CHARLOTTE CREW", ["stripe", "cotton"]),
        row("3", "ARDEN CREW", "ARDEN CREW", ["stripe", "cotton"]),
    ]
    pools = similarity.build_pools(rows)

    assert [c["style_key"] for c in pools["1"]] == ["ARDEN CREW"]


def test_a_pool_shows_one_product_per_style():
    rows = [
        row("1", "ANCHOR", "ANCHOR", ["stripe", "cotton"]),
        row("2", "ARDEN CREW", "ARDEN CREW", ["stripe", "cotton"]),
        row("3", "ARDEN CREW", "ARDEN CREW", ["stripe", "cotton"]),
    ]
    pools = similarity.build_pools(rows)

    assert len(pools["1"]) == 1


def test_a_different_season_is_excluded():
    rows = [
        row("1", "ANCHOR", "ANCHOR", ["stripe"], season="autumn"),
        row("2", "SPRING THING", "SPRING THING", ["stripe"], season="spring"),
    ]
    pools = similarity.build_pools(rows)

    assert pools["1"] == []


def test_a_product_with_no_season_still_gets_a_pool():
    # 4 of 258 products carry no season tag. Under a hard season rule they
    # would match nothing, so they ignore it rather than ship an empty pool.
    rows = [
        row("1", "ANCHOR", "ANCHOR", ["stripe"], season=None),
        row("2", "OTHER", "OTHER", ["stripe"], season="spring"),
    ]
    pools = similarity.build_pools(rows)

    assert len(pools["1"]) == 1


def test_the_same_silhouette_scores_higher():
    rows = [
        row("1", "ANCHOR", "ANCHOR", ["stripe"], ptype="crewneck"),
        row("2", "SAME SHAPE", "SAME SHAPE", ["stripe"], ptype="crewneck"),
        row("3", "OTHER SHAPE", "OTHER SHAPE", ["stripe"], ptype="vneck"),
    ]
    pools = similarity.build_pools(rows)

    assert pools["1"][0]["title"] == "SAME SHAPE"


def test_pools_are_capped_at_the_requested_depth():
    rows = [row("1", "ANCHOR", "ANCHOR", ["stripe"])]
    rows += [row(str(i), f"P{i}", f"P{i}", ["stripe"]) for i in range(2, 20)]

    pools = similarity.build_pools(rows, depth=5)

    assert len(pools["1"]) == 5


def test_ties_break_deterministically():
    # Two runs must produce the same list, or a "nothing changed" diff is noise.
    rows = [row("1", "ANCHOR", "ANCHOR", ["stripe"])]
    rows += [row(str(i), f"P{i}", f"P{i}", ["stripe"]) for i in range(2, 8)]

    first = similarity.build_pools(rows)["1"]
    second = similarity.build_pools(rows)["1"]

    assert [c["product_id"] for c in first] == [c["product_id"] for c in second]


def test_a_clean_set_of_pools_passes_the_self_check():
    rows = [
        row("1", "ANCHOR", "ANCHOR", ["stripe", "cotton"]),
        row("2", "OTHER", "OTHER", ["stripe", "cotton"]),
    ]
    pools = similarity.build_pools(rows)

    assert similarity.check(rows, pools) == []


def test_an_empty_pool_is_caught():
    rows = [
        row("1", "ANCHOR", "ANCHOR", ["stripe"], season="autumn"),
        row("2", "OTHER", "OTHER", ["stripe"], season="spring"),
    ]
    pools = similarity.build_pools(rows)

    assert any("empty pool" in p for p in similarity.check(rows, pools))
