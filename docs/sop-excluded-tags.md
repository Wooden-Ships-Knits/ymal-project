# SOP: stop recommending occasion products after the shipping cutoff

Occasion products (Halloween, Christmas, Thanksgiving and so on) keep selling
right up to the event, so the **Top Selling (MYNTS)** and **Trending** blocks
keep recommending them after it is too late to deliver.

The fix is one Shopify tag: **`no-mynts`**. Any product carrying it is left out
of MYNTS and Trending. The product stays live and buyable everywhere else - it
is only no longer recommended in those two blocks.

## One-time setup

Done once; nobody needs to touch it again.

1. Open the YMAL console, **Exclude by Tag**.
2. Type `no-mynts`, press **Add**, then **Save**.

## On the cutoff day

The cutoff is **7 days before the event**.

| Occasion | Event | Cutoff |
|---|---|---|
| Valentine's Day | 14 Feb | 7 Feb |
| 4th of July | 4 Jul | 27 Jun |
| Halloween | 31 Oct | 24 Oct |
| Thanksgiving | 4th Thursday of November | 7 days before it (2026: 19 Nov) |
| Christmas | 25 Dec | 18 Dec |

1. In Shopify admin, open **Products**.
2. Filter to the occasion's products - for example by its collection.
3. Select all of them, then **More actions -> Add tags**, and add `no-mynts`.
4. In the YMAL console, **Exclude by Tag**, press **Rebuild and publish** - or
   wait for the nightly run at 20:00 Makassar.
5. After the rebuild, the count under `no-mynts` shows how many products carry
   it. Check it matches what you tagged.
6. Check the homepage: the MYNTS row should no longer show those products.

## After the season

Before the occasion comes round again next year, take the tag off so the
products are recommended again during their season:

1. In Shopify admin, **Products**, search for `no-mynts`.
2. Select the products to bring back, **More actions -> Remove tags**, and
   remove `no-mynts`.
3. Rebuild, or wait for the nightly run.

## Notes

- The tag works for anything, not only occasions - a style being wound down,
  for example.
- Do not remove `no-mynts` from the **Exclude by Tag** tab. That switches the
  rule off, and every tagged product would be recommended again.
