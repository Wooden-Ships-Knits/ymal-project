/*
 * YMAL — Recently Viewed
 *
 * The only block with no backend behind it. The browser is the storage: a list
 * of product handles in localStorage, written on each product page and read
 * back to render. Nothing leaves the device, no login is involved, and there is
 * no customer record on our side to hold or secure.
 *
 * Cards are fetched from the theme itself (/products/<handle>?view=ymal-card)
 * rather than built here, so they use the theme's own product-card markup and
 * look native. That also keeps price and availability live — a handle stored
 * three weeks ago still renders today's price, and a sold-out product renders
 * as an empty string and is skipped.
 */
(function () {
  'use strict';

  // Run once per page. Both the recorder snippet and the display snippet load
  // this file, and a page with both would otherwise record the product twice
  // and append every card twice - the second <script src> for the same file
  // still executes. ymal-recently-viewed-cart.js guards the same way, per
  // section.
  if (window.__ymalRecentlyViewed) return;
  window.__ymalRecentlyViewed = true;

  var KEY = 'ymal:viewed';
  var MAX_STORED = 20;      // deep enough to survive filtering, cheap to keep
  var CARD_VIEW = 'ymal-card';

  // How many candidates to fetch per slot. The card template is the
  // eligibility gate, so a stored handle may render nothing - fixed stock,
  // *SALE*, sold out, unpublished. Fetching exactly `slots` and filtering
  // afterwards makes the block thin out for precisely the shoppers who browse
  // most, which is why the list stores 20 in the first place.
  //
  // 3x is the compromise: on this catalog roughly 60% of active products are
  // eligible, so three candidates per slot fills it in almost every case
  // without fetching all 20 every time.
  var OVERFETCH = 3;

  // The cart attribute that carries the list into checkout. Deliberately plain:
  // the shopper can see their own cart attributes.
  var ATTRIBUTE = 'YMAL viewed';
  var ATTRIBUTE_MAX = 12;       // 12 ids stay well inside the attribute's limit
  var SENT_KEY = 'ymal:viewed-sent';
  var VERIFY_AFTER_MS = 2500;   // past the other apps' own cart writes
  var SYNC_ATTEMPTS = 3;

  // localStorage throws in some privacy modes rather than returning null, so
  // every access is guarded. A browser that refuses storage simply never shows
  // the block.
  function read() {
    try {
      var raw = window.localStorage.getItem(KEY);
      var list = raw ? JSON.parse(raw) : [];
      return Array.isArray(list) ? list : [];
    } catch (e) {
      return [];
    }
  }

  function write(list) {
    try {
      window.localStorage.setItem(KEY, JSON.stringify(list));
    } catch (e) {
      /* quota, private mode, storage disabled — not worth surfacing */
    }
  }

  // Newest first, one entry per product. Only the handle, id and eligibility
  // are stored: title, price and image are fetched fresh at render, so nothing
  // here goes stale.
  function record(entry) {
    if (!entry || !entry.handle) return;
    var next = read().filter(function (p) { return p.handle !== entry.handle; });
    next.unshift({
      handle: entry.handle,
      id: entry.id,
      eligible: entry.eligible === true,
      ts: Date.now()
    });
    write(next.slice(0, MAX_STORED));
  }

  // ---------------------------------------------------------------------------
  // Carrying the list into checkout
  //
  // A checkout extension runs in a sandbox on another origin: it cannot read
  // this localStorage list, and there is no Liquid there either. The cart is
  // the one thing that travels from the storefront into checkout, so the list
  // rides along as a cart attribute.
  //
  // IDS, NOT HANDLES. A handle runs to 50 characters and the attribute has a
  // size limit; an id is 14. Only products that passed the eligibility gate at
  // view time are included - see the recorder snippet.
  // ---------------------------------------------------------------------------

  function hasCart() {
    // No cart means no checkout to carry anything into, and writing an
    // attribute would create a cart for every product-page visitor.
    return document.cookie.indexOf('cart=') !== -1;
  }

  function attributeValue() {
    return read()
      .filter(function (p) { return p && p.eligible && p.id; })
      .slice(0, ATTRIBUTE_MAX)
      .map(function (p) { return String(p.id); })
      .join(',');
  }

  function remembered() {
    try {
      return window.sessionStorage.getItem(SENT_KEY);
    } catch (e) {
      // Private mode: post every time rather than not at all.
      return null;
    }
  }

  function remember(value) {
    try {
      window.sessionStorage.setItem(SENT_KEY, value);
    } catch (e) {
      /* nothing to remember with; the next view posts again */
    }
  }

  function postAttribute(value) {
    var attributes = {};
    attributes[ATTRIBUTE] = value;
    return fetch('/cart/update.js', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ attributes: attributes })
    })
      // fetch resolves for a 4xx too, and a write that never landed must not
      // be remembered as sent - the list would silently stop following the
      // shopper into checkout.
      .then(function (res) { return res.ok; })
      .catch(function () { return false; });
  }

  function liveAttribute() {
    return fetch('/cart.js', { credentials: 'same-origin', cache: 'no-store' })
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (cart) { return cart ? cart.attributes[ATTRIBUTE] || null : null; })
      .catch(function () { return null; });
  }

  // Write, then CHECK. This store runs other apps that write cart attributes of
  // their own, and two writes moments apart can be committed from the same
  // starting snapshot - the second one silently puts the old value back. Seen
  // on every product page here: Redo posts redo_loaded_on_cart about 300ms
  // after this one, and the cart comes back carrying the previous list.
  //
  // So the value is verified a beat later and rewritten if it was reverted, and
  // only a verified value is remembered as sent.
  function syncAttribute(attempt) {
    if (!hasCart()) return;

    var value = attributeValue();
    if (!value || remembered() === value) return;

    postAttribute(value).then(function (ok) {
      if (!ok) return;
      window.setTimeout(function () {
        liveAttribute().then(function (live) {
          if (live === value) {
            remember(value);
            return;
          }
          if ((attempt || 0) + 1 < SYNC_ATTEMPTS) syncAttribute((attempt || 0) + 1);
        });
      }, VERIFY_AFTER_MS);
    });
  }

  function fetchCard(handle) {
    return fetch('/products/' + encodeURIComponent(handle) + '?view=' + CARD_VIEW, {
      credentials: 'same-origin'
    })
      .then(function (res) { return res.ok ? res.text() : ''; })
      .then(function (html) { return html.trim(); })
      // Deleted, unpublished, or renamed handle — skip it rather than break
      // the block.
      .catch(function () { return ''; });
  }

  function track(name, detail) {
    if (typeof window.ymalTrack === 'function') window.ymalTrack(name, detail);
  }

  function render(section) {
    var list = section.querySelector('[data-ymal-items]');
    if (!list) return;

    var anchor = section.getAttribute('data-ymal-anchor') || '';
    var slots = parseInt(section.getAttribute('data-ymal-slots'), 10) || 4;
    var pageType = section.getAttribute('data-ymal-page') || '';

    // Take more candidates than slots, because the card template gates on
    // eligibility and many will render nothing. Trim to `slots` AFTER
    // filtering, not before.
    var handles = read()
      .filter(function (p) { return String(p.id) !== String(anchor); })
      .slice(0, slots * OVERFETCH)
      .map(function (p) { return p.handle; });

    if (!handles.length) return;

    Promise.all(handles.map(fetchCard)).then(function (cards) {
      var shown = [];

      cards.forEach(function (html, i) {
        // An empty card means the theme chose not to render it — ineligible,
        // sold out, unpublished, gone. That decision belongs in Liquid, where
        // the live product object is, and this script does not second-guess it.
        if (!html) return;
        if (shown.length >= slots) return;

        var li = document.createElement('li');
        li.className = 'ymal__card';
        li.setAttribute('data-ymal-handle', handles[i]);
        li.setAttribute('data-ymal-position', String(shown.length + 1));
        li.innerHTML = html;
        list.appendChild(li);
        shown.push(handles[i]);
      });

      // Never a heading with nothing under it.
      if (!shown.length) return;
      section.hidden = false;

      // Fires once per pageview, when the block actually comes into view —
      // an impression the shopper never saw is not an impression.
      if ('IntersectionObserver' in window) {
        var seen = false;
        var io = new IntersectionObserver(function (entries) {
          entries.forEach(function (entry) {
            if (!entry.isIntersecting || seen) return;
            seen = true;
            io.disconnect();
            track('ymal_impression', {
              block: 'recently_viewed',
              page_type: pageType,
              anchor: anchor,
              handles: shown
            });
          });
        }, { threshold: 0.5 });
        io.observe(section);
      }

      // Delegated, so it survives cards being added or replaced.
      list.addEventListener('click', function (event) {
        var card = event.target.closest('[data-ymal-handle]');
        if (!card) return;
        track('ymal_click', {
          block: 'recently_viewed',
          page_type: pageType,
          anchor: anchor,
          handle: card.getAttribute('data-ymal-handle'),
          position: Number(card.getAttribute('data-ymal-position'))
        });
      });
    });
  }

  function init() {
    // Record first: a shopper landing on a product page should find it in the
    // list on the next page, and should not see it in the block on this one.
    var seed = document.getElementById('ymal-current-product');
    if (seed) {
      try {
        record(JSON.parse(seed.textContent));
      } catch (e) {
        /* malformed seed — recording is not worth breaking the page over */
      }
    }

    // Never the cart drawer's block: ymal-recently-viewed-cart.js owns that
    // one, with its own compact cards and cart-aware refresh. Filling it here
    // as well appended grid cards into the drawer and counted every drawer
    // opening twice. (The cart snippet no longer carries data-ymal-block, so
    // this is the second of two guards - it covers a drawer snippet copied
    // before that change.)
    document
      .querySelectorAll('[data-ymal-block="recently_viewed"]:not([data-ymal-page="cart"])')
      .forEach(render);

    syncAttribute();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // A shopper on their first product page has no cart, so nothing was written.
  // The moment they add something, there is one to write to.
  ['on:cart:add', 'on:cart:change'].forEach(function (name) {
    document.addEventListener(name, function () {
      setTimeout(syncAttribute, 150);
    });
  });
})();
