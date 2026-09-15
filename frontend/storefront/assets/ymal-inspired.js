/*
 * YMAL — Inspired By Your Views.
 *
 * Builds a row from the shopper's browsing history: the first 4 Featured
 * products of each of their last 5 viewed products, minus anything they have
 * already viewed or put in the cart, shuffled once per visit.
 *
 *   history (localStorage, written by the Recently Viewed recorder)
 *     -> last 5 viewed, not counting the product on this page
 *     -> /products/<h>?view=ymal-ibyv   first 4 that would appear in its YMAL row
 *     -> combine, drop duplicates, drop viewed + in cart + this product
 *     -> order by a seed that lives for the visit
 *     -> one colorway per style
 *     -> /products/<h>?view=ymal-block  the theme's own product card
 *
 * WHY THIS PRODUCT IS NOT A SOURCE. On a product page the recorder has just
 * added it to the history, so it would always be one of the last 5. Its
 * Featured top 4 is exactly what the YMAL row on the same page already shows,
 * and repeating those products a scroll later adds nothing.
 *
 * SHUFFLED ONCE PER VISIT. Each product's position comes from a hash of the
 * visit's seed and its handle, never from the list it is in. So the order is
 * identical on every page of a visit, a new visit gets a new order, and when
 * browsing adds candidates mid-visit the products already on show keep their
 * relative order - new ones slot in between rather than reshuffling the row.
 *
 * The same file is loaded by `node --test`. The pure functions are exported for
 * that; the browser half only runs where there is a document.
 */
(function (root) {
  'use strict';

  var PER_SOURCE = 4;
  var SOURCES = 5;

  // ---------------------------------------------------------------------------
  // Pure functions - tested in frontend/storefront/tests/ymal-inspired.test.js
  // ---------------------------------------------------------------------------

  // FNV-1a, 32-bit. Deterministic in every browser and in Node, which a
  // Math.random shuffle is not - and determinism is what keeps the order fixed
  // for the whole visit.
  function hash(text) {
    var h = 0x811c9dc5;
    for (var i = 0; i < text.length; i++) {
      h ^= text.charCodeAt(i);
      h = Math.imul(h, 0x01000193);
    }
    return h >>> 0;
  }

  // The first `perSource` of each source, in source order, duplicates dropped
  // at their later appearance. A source is null or empty when that product had
  // nothing eligible or its fetch failed.
  function candidates(sources, perSource) {
    var seen = {};
    var out = [];
    (sources || []).forEach(function (source) {
      if (!source || !source.length) return;
      source.slice(0, perSource).forEach(function (handle) {
        if (!handle || seen[handle]) return;
        seen[handle] = true;
        out.push(handle);
      });
    });
    return out;
  }

  function exclude(handles, excluded) {
    return handles.filter(function (handle) {
      return !excluded.has(handle);
    });
  }

  // Sorted by hash(seed | handle), never shuffled in place. A product's rank
  // depends only on itself and the seed, which is what makes it stable as the
  // candidate list grows. Ties broken by handle so the result is total.
  function seededOrder(handles, seed) {
    return handles
      .map(function (handle) {
        return { handle: handle, rank: hash(String(seed) + '|' + handle) };
      })
      .sort(function (a, b) {
        if (a.rank !== b.rank) return a.rank - b.rank;
        return a.handle < b.handle ? -1 : a.handle > b.handle ? 1 : 0;
      })
      .map(function (item) {
        return item.handle;
      });
  }

  // One card per style. A style's colorways are separate products with
  // separate handles, and two viewed products often recommend different
  // colorways of the same sweater - which filled the row with one jersey.
  // Runs AFTER ordering, so the colorway kept is whichever the visit's shuffle
  // put first, and that stays the same for the whole visit. A handle with no
  // known style counts as a style of its own.
  function uniqueStyles(handles, styles) {
    var seen = Object.create(null);
    return handles.filter(function (handle) {
      var key = (styles && styles[handle]) || handle;
      if (seen[key]) return false;
      seen[key] = true;
      return true;
    });
  }

  function plan(options) {
    var pool = candidates(options.sources, options.perSource);
    var ordered = seededOrder(exclude(pool, options.excluded), options.seed);
    return uniqueStyles(ordered, options.styles);
  }

  var api = {
    hash: hash,
    candidates: candidates,
    exclude: exclude,
    seededOrder: seededOrder,
    uniqueStyles: uniqueStyles,
    plan: plan,
    PER_SOURCE: PER_SOURCE,
    SOURCES: SOURCES
  };

  if (typeof module === 'object' && module.exports) {
    module.exports = api;
  }

  if (typeof document === 'undefined') return;

  // ---------------------------------------------------------------------------
  // Browser
  // ---------------------------------------------------------------------------

  // Run once per page, however many times the script tag appears.
  if (root.__ymalInspired) return;
  root.__ymalInspired = true;

  var VIEWED_KEY = 'ymal:viewed';
  var SEED_KEY = 'ymal:ibyv-seed';
  var BLOCK = 'inspired_by_views';

  function readViewed() {
    try {
      var list = JSON.parse(root.localStorage.getItem(VIEWED_KEY) || '[]');
      return Array.isArray(list) ? list : [];
    } catch (e) {
      // Private browsing throws rather than returning null. No history means
      // no row, which is the correct outcome.
      return [];
    }
  }

  function visitSeed() {
    try {
      var seed = root.sessionStorage.getItem(SEED_KEY);
      if (!seed) {
        seed = Math.random().toString(36).slice(2);
        root.sessionStorage.setItem(SEED_KEY, seed);
      }
      return seed;
    } catch (e) {
      // Without sessionStorage there is no visit to be stable across; a
      // per-page seed is the honest fallback.
      return Math.random().toString(36).slice(2);
    }
  }

  function getText(url) {
    return fetch(url, { credentials: 'same-origin' })
      .then(function (res) { return res.ok ? res.text() : ''; })
      .catch(function () { return ''; });
  }

  // { handles, styles } - styles[i] is the style of handles[i]. A template
  // from before styles were added has no `styles`, and every product then
  // counts as its own style, which is how the row behaved before.
  function sourceFor(handle) {
    return getText('/products/' + encodeURIComponent(handle) + '?view=ymal-ibyv')
      .then(function (text) {
        try {
          var data = JSON.parse(text);
          return {
            handles: Array.isArray(data.handles) ? data.handles : [],
            styles: Array.isArray(data.styles) ? data.styles : []
          };
        } catch (e) {
          // Deleted, unpublished or renamed product - no source, not an error.
          return { handles: [], styles: [] };
        }
      });
  }

  function cartHandles() {
    return fetch('/cart.js', { credentials: 'same-origin' })
      .then(function (res) { return res.ok ? res.json() : { items: [] }; })
      .then(function (cart) {
        return (cart.items || []).map(function (item) { return item.handle; });
      })
      .catch(function () { return []; });
  }

  function cardFor(handle) {
    return getText('/products/' + encodeURIComponent(handle) + '?view=ymal-block')
      .then(function (html) { return html.trim(); });
  }

  function track(name, detail) {
    if (typeof root.ymalTrack === 'function') root.ymalTrack(name, detail);
  }

  // Fetch cards in planned order until the row is full. In batches rather than
  // all at once: most candidates survive, so twice the slots is usually one
  // round, and a stock change that blanks a card just pulls from the next batch.
  function fillCards(ordered, slots) {
    var shown = [];
    var cursor = 0;

    function nextBatch() {
      if (shown.length >= slots || cursor >= ordered.length) {
        return Promise.resolve(shown);
      }
      var batch = ordered.slice(cursor, cursor + slots * 2);
      cursor += batch.length;
      return Promise.all(batch.map(cardFor)).then(function (cards) {
        cards.forEach(function (html, i) {
          if (html && shown.length < slots) shown.push({ handle: batch[i], html: html });
        });
        return nextBatch();
      });
    }

    return nextBatch();
  }

  function render(section, cards) {
    var grid = section.querySelector('[data-ymal-items]');
    if (!grid) return [];
    // The theme's carousel only moves children marked as slides.
    var carousel = section.querySelector('carousel-slider');

    cards.forEach(function (card, index) {
      var holder = document.createElement('template');
      holder.innerHTML = card.html;
      var node = holder.content.firstElementChild;
      if (!node) return;
      node.setAttribute('data-ymal-handle', card.handle);
      node.setAttribute('data-ymal-position', String(index + 1));
      if (carousel) {
        var slide = document.createElement('div');
        slide.className = 'slider__item';
        slide.appendChild(node);
        grid.appendChild(slide);
      } else {
        grid.appendChild(node);
      }
    });

    return cards.map(function (card) { return card.handle; });
  }

  // The theme's <carousel-slider> set itself up while the page parsed, when
  // this row had no slides, and switched itself off. refresh() is its own
  // re-initialise hook. It measures card widths, so the row must already be
  // visible when this runs.
  function refreshCarousel(section) {
    var carousel = section.querySelector('carousel-slider');
    if (!carousel || typeof carousel.refresh !== 'function') return;
    try {
      carousel.refresh();
    } catch (e) {
      /* without the carousel the cards still show, just not as a slider */
    }
  }

  function wireTracking(section, handles, pageType, anchor) {
    if ('IntersectionObserver' in root) {
      var seen = false;
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting || seen) return;
          seen = true;
          io.disconnect();
          // Counted when half the row is on screen - an impression nobody saw
          // would flatter every click rate built on it.
          track('ymal_impression', {
            block: BLOCK, page_type: pageType, anchor: anchor, handles: handles
          });
        });
      }, { threshold: 0.5 });
      io.observe(section);
    }

    section.addEventListener('click', function (event) {
      var card = event.target.closest('[data-ymal-handle]');
      if (!card || !section.contains(card)) return;

      track('ymal_click', {
        block: BLOCK,
        page_type: pageType,
        anchor: anchor,
        handle: card.getAttribute('data-ymal-handle'),
        position: Number(card.getAttribute('data-ymal-position'))
      });

      // The cart attribute that attributes a later purchase to this block -
      // the same one every other YMAL row writes. ymal-track.js remembers the
      // click itself, so add to cart is recorded without anything here.
      try {
        fetch('/cart/update.js', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ attributes: { 'YMAL block': BLOCK } })
        }).catch(function () {});
      } catch (e) {
        /* attribution is never worth breaking a storefront over */
      }
    });
  }

  function build(section) {
    var current = section.getAttribute('data-ymal-current') || '';
    var pageType = section.getAttribute('data-ymal-page') || 'unknown';
    var slots = parseInt(section.getAttribute('data-ymal-slots'), 10) || 4;

    var viewed = readViewed().map(function (item) { return item && item.handle; })
      .filter(Boolean);

    var sourceHandles = viewed
      .filter(function (handle) { return handle !== current; })
      .slice(0, SOURCES);

    // No history beyond this page: nothing to be inspired by. Stay hidden.
    if (!sourceHandles.length) return;

    Promise.all([
      Promise.all(sourceHandles.map(sourceFor)),
      cartHandles()
    ]).then(function (results) {
      var sources = results[0];
      var styles = {};
      sources.forEach(function (source) {
        source.handles.forEach(function (handle, i) {
          if (source.styles[i]) styles[handle] = source.styles[i];
        });
      });

      var excluded = new Set(viewed.concat(results[1], [current]));
      var ordered = plan({
        sources: sources.map(function (source) { return source.handles; }),
        perSource: PER_SOURCE,
        excluded: excluded,
        seed: visitSeed(),
        styles: styles
      });
      if (!ordered.length) return null;
      return fillCards(ordered, slots);
    }).then(function (cards) {
      if (!cards || !cards.length) return;
      var handles = render(section, cards);
      // Never a heading with nothing under it.
      if (!handles.length) return;
      section.hidden = false;
      refreshCarousel(section);
      wireTracking(section, handles, pageType, current);
    }).catch(function () {
      /* a recommendation row is never worth breaking a product page over */
    });
  }

  function start(section) {
    if (section.getAttribute('data-ymal-ready')) return;
    section.setAttribute('data-ymal-ready', '1');

    // Do nothing until the shopper scrolls near it. Up to five source fetches
    // and a handful of cards should not compete with the product page loading.
    //
    // Watch the section's wrapper, never the row itself: the row is `hidden`
    // until it has cards, and a display:none element never intersects
    // anything - observing it directly meant the row waited forever.
    var watched = section.parentElement;
    if (!('IntersectionObserver' in root) || !watched) {
      build(section);
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        io.disconnect();
        build(section);
      });
    }, { rootMargin: '0px 0px 600px 0px' });
    io.observe(watched);
  }

  function init() {
    document.querySelectorAll('[data-ymal-ibyv]').forEach(start);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})(typeof window !== 'undefined' ? window : this);
