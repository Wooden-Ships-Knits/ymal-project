# YMAL — Recommendation Logic

> **Status: empty on purpose.** To be filled during the logic discussion.
>
> This document should end up describing *how a recommendation is actually
> decided* — what signals feed in, how they're combined, and what rules
> override them. It is the part that differentiates us from Wiser, so it
> deserves its own conversation rather than a first-draft guess.

---

## 1. Signals

_What data do we use to decide two products are related?_

TBD

---

## 2. Scoring

_How each signal produces a score._

TBD

---

## 3. Blending

_How multiple signals combine into one ranked list._

TBD

---

## 4. Business rules

_Hard filters and merchandising overrides applied on top of the scores._

### 4.1 Eligibility rule — fixed stock and SALE (notes, 2026-09-03)

**Requirement, as stated:** products that sell fixed stock, and products on
sale, must **never** appear in the recommendation widget.

**Why it matters:** recommending a fixed-stock item drives demand at something
we cannot restock — the shopper hits an unavailable product, or we burn through
finite inventory we were holding. Recommending SALE items pushes traffic to
markdown when the widget's job is to sell at full price.

**How a product is identified as eligible ("unfix"):**

Both conditions must hold.

| # | Condition | Source |
|---|---|---|
| 1 | Stock is replenishable — produced at the **Bali** location | Inventory location |
| 2 | Title does **not** contain the marker **`*SALE*`** | Product title |

Fails either → excluded from the candidate pool.

**On the `*SALE*` marker (updated 2026-09-03):** the sale marker written into
product titles is asterisk-delimited — literally `*SALE*`, not the bare word.
Match on the full delimited token, not on `SALE` alone. This removes the
substring false-positive risk (`WHOLESALE` and similar) that a bare-word match
would have.

Implementation note for later: `*` is a regex metacharacter. Use literal string
containment, or escape it (`\*SALE\*`). An unescaped `*SALE*` in a regex means
something entirely different and will not match what we want.

**Where this runs:** serve time, not batch. Location/stock state and title can
change during the day, and this is precisely the staleness that Wiser gets
wrong (see `flow.md` §1). Checking it nightly and trusting it at render would
reproduce the bug we are trying to fix.

**Starting point:** enumerate currently active product pages and read their
location status, to see how the catalog actually splits. Not built yet — this
is the first thing to look at, but no pipeline until the questions in
`caveats.md` §1 are answered.

**Open questions — see `caveats.md` §1.** The rule above is written from a
verbal description and has not been validated against real catalog data.

---

## 5. Fallbacks

_What we show when the primary logic returns nothing._

TBD

---

## 6. Evaluation

_How we know the logic is good, and how we compare against Wiser._

TBD
