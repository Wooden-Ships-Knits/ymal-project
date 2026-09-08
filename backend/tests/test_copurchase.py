"""
Co-purchase scoring and reranking.

The safety property worth testing hardest: reranking must never change who is
in a pool. That is the whole argument for why a co-purchase pair cannot break
the season or eligibility rules.
"""

from ymal import copurchase, evaluate, settings


STYLE_OF = {"gid1": "A", "gid2": "B", "gid3": "C", "gid9": "OTHER"}


def item(pid, style, score):
    return {"product_id": pid, "handle": pid, "title": style,
            "style_key": style, "score": score}


def test_colorways_collapse_to_one_style():
    # Two colorways of A in one basket is not a co-purchase of A with itself.
    style_of = {"p1": "A", "p2": "A", "p3": "B"}
    out = copurchase.style_baskets([{"p1", "p2", "p3"}], style_of)

    assert out == [{"A", "B"}]


def test_a_basket_of_one_style_is_dropped():
    style_of = {"p1": "A", "p2": "A"}
    assert copurchase.style_baskets([{"p1", "p2"}], style_of) == []


def test_products_outside_the_eligible_set_are_dropped():
    style_of = {"p1": "A", "p2": "B"}
    out = copurchase.style_baskets([{"p1", "p2", "unknown"}], style_of)

    assert out == [{"A", "B"}]


def test_pairs_are_counted_once_not_once_per_direction():
    singles, pairs, total = copurchase.count_pairs([{"A", "B"}, {"B", "A"}])

    assert pairs == {("A", "B"): 2}
    assert total == 2


def test_lift_is_zero_below_the_pair_floor():
    # Two products bought together once say nothing.
    singles = {"A": 10, "B": 10}
    pairs = {("A", "B"): 1}

    assert copurchase.lift("A", "B", singles, pairs, 100) == 0.0


def test_lift_above_one_means_more_than_chance():
    # A and B appear in 10 baskets each out of 100, together in 10 - they
    # always co-occur, which is far above chance.
    singles = {"A": 10, "B": 10}
    pairs = {("A", "B"): 10}

    assert copurchase.lift("A", "B", singles, pairs, 100) > 1.0


def test_lift_is_symmetric():
    singles = {"A": 10, "B": 20}
    pairs = {("A", "B"): 5}

    assert copurchase.lift("A", "B", singles, pairs, 100) == copurchase.lift(
        "B", "A", singles, pairs, 100
    )


def test_a_bestseller_in_everything_does_not_score_high():
    # The reason lift is used instead of raw counts: a product in every basket
    # co-occurs with everything, which is chance, not a signal.
    baskets = [{"BEST", chr(65 + i)} for i in range(20)]
    singles, pairs, total = copurchase.count_pairs(baskets)

    assert copurchase.lift("BEST", "A", singles, pairs, total) == 0.0


def test_reranking_never_changes_pool_membership():
    pool = [item("1", "A", 5.0), item("2", "B", 4.0), item("3", "C", 3.0)]
    scores = copurchase.build_scores(
        [{"gid2", "gid3"}] * 10, STYLE_OF
    )

    after = copurchase.rerank(pool, "A", scores)

    assert {i["product_id"] for i in after} == {"1", "2", "3"}
    assert len(after) == 3


def test_a_candidate_with_no_history_keeps_its_content_order():
    # The cold-start path, and the permanent one for anything launched today.
    pool = [item("1", "A", 5.0), item("2", "B", 4.0)]
    scores = {"singles": {}, "pairs": {}, "total": 0}

    after = copurchase.rerank(pool, "Z", scores)

    assert [i["title"] for i in after] == ["A", "B"]
    assert all(i["copurchase_lift"] == 0.0 for i in after)


def test_a_co_purchased_candidate_moves_up():
    pool = [item("1", "A", 5.0), item("2", "B", 4.0)]
    # OTHER and B each appear in 20 of 100 baskets and 15 of those together -
    # far above the 4 that chance predicts. OTHER must NOT be in every basket,
    # or its co-occurrence with B is exactly chance and scores nothing.
    baskets = [{"gid9", "gid2"}] * 15
    baskets += [{"gid9", "gid1"}] * 5
    baskets += [{"gid2", "gid1"}] * 5
    baskets += [{"gid1", "gid3"}] * 75
    scores = copurchase.build_scores(baskets, STYLE_OF)

    after = copurchase.rerank(pool, "OTHER", scores)

    assert after[0]["title"] == "B"


def test_the_boost_is_capped():
    # A single extreme pair must not drag an unrelated product to the top of a
    # pool it barely belongs in.
    pool = [item("1", "A", 10.0), item("2", "B", 1.0)]
    baskets = [{"gid9", "gid2"}] * 50
    scores = copurchase.build_scores(baskets, STYLE_OF)

    after = copurchase.rerank(pool, "OTHER", scores)

    # B's score can rise by at most the rerank weight, nowhere near 10.
    b = next(i for i in after if i["title"] == "B")
    assert b["final_score"] <= 1.0 * (1 + settings.COPURCHASE_RERANK_WEIGHT)
    assert after[0]["title"] == "A"


def test_the_self_check_catches_changed_membership():
    before = {"1": [item("2", "B", 4.0)]}
    after = {"1": [item("3", "C", 4.0)]}

    assert any("membership changed" in p for p in copurchase.check(before, after))


def test_holdout_takes_the_most_recent_baskets():
    # Orders come back newest first, so the test set is the front slice.
    baskets = [{"newest"}, {"b"}, {"c"}, {"d"}, {"e"},
               {"f"}, {"g"}, {"h"}, {"i"}, {"oldest"}]
    train, test = evaluate.split_by_recency(baskets, 0.1)

    assert test == [{"newest"}]
    assert len(train) == 9


def test_hit_rate_counts_a_pool_containing_the_co_bought_style():
    pools = {"p1": [item("2", "B", 1.0)]}
    style_of = {"p1": "A"}

    result = evaluate.hit_rate_at_k(pools, [{"A", "B"}], style_of, k=6)

    assert result["questions"] == 1
    assert result["hits"] == 1


def test_an_anchor_with_no_pool_is_unanswerable_not_a_miss():
    # Both rankings must be compared on the same questions. Each basket asks
    # in both directions - A predicting B and B predicting A - so a basket of
    # two styles with no pools is two unanswerable questions, not one.
    result = evaluate.hit_rate_at_k({}, [{"A", "B"}], {"p1": "A"}, k=6)

    assert result["questions"] == 0
    assert result["unanswerable"] == 2
