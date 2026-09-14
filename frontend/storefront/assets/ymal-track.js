/*
 * YMAL — storefront tracking.
 *
 * Defines window.ymalTrack(name, detail). The block scripts already call it and
 * do nothing when it is absent, so this file can be added or removed without
 * touching them.
 *
 * This is the training data for the ranking model and CANNOT be collected
 * retroactively - whatever is not captured from the first day is simply gone.
 *
 * Nothing here blocks the page. Events are queued and sent with sendBeacon,
 * which the browser delivers in its own time and does not wait for.
 *
 * NO PERSONAL DATA. The session id is a random string this browser generates
 * for itself, kept in sessionStorage, and sent nowhere else. It exists to tell
 * one visit's events apart from another's. There is no cookie, no identifier
 * that outlives the tab, and nothing that can be traced back to a person.
 */
(function () {
  'use strict';

  var ENDPOINT = 'https://ymal.pt-infashion.com/api/events';
  var SESSION_KEY = 'ymal:session';

  // The last YMAL card clicked, kept across page loads.
  //
  // Clicking a recommendation NAVIGATES to the product page, so the add to
  // cart happens on a different pageview with no YMAL row on it. Without this
  // there is nothing left to attribute the add to, which is why add_to_cart
  // was flat zero while clicks worked.
  var CLICK_KEY = 'ymal:lastclick';

  // How long a click may still explain an add. Long enough to read the page
  // and pick a size; short enough that an add an hour later is not credited to
  // a recommendation the shopper has forgotten.
  var ATTRIBUTION_MS = 30 * 60 * 1000;

  // The body IS json. The content type says text/plain so that this stays a
  // CORS "simple request" and the browser sends NO preflight.
  //
  // application/json is not on the CORS safelist, so it forces an OPTIONS
  // round trip first - and a beacon fired while the page is unloading loses
  // that race often enough to matter. The API parses the body by hand and does
  // not care what the header says.
  //
  // DO NOT "correct" this to application/json.
  var CONTENT_TYPE = 'text/plain;charset=UTF-8';

  // Events are batched and flushed on a timer rather than sent one by one: a
  // row of six products fires six impressions at once, and six requests to say
  // one thing is wasteful.
  var FLUSH_MS = 2000;
  var MAX_BATCH = 50;

  var queue = [];
  var timer = null;

  function session() {
    try {
      var existing = window.sessionStorage.getItem(SESSION_KEY);
      if (existing) return existing;
      // Random, not derived from anything about the visitor.
      var fresh = Math.random().toString(36).slice(2) + Date.now().toString(36);
      window.sessionStorage.setItem(SESSION_KEY, fresh);
      return fresh;
    } catch (e) {
      // Private browsing throws rather than returning null. Events still send;
      // they just cannot be grouped into a visit.
      return 'no-storage';
    }
  }

  function send() {
    timer = null;
    if (!queue.length) return;

    var batch = queue.splice(0, MAX_BATCH);
    var body = JSON.stringify({ events: batch });

    try {
      if (navigator.sendBeacon) {
        navigator.sendBeacon(ENDPOINT, new Blob([body], { type: CONTENT_TYPE }));
      } else {
        // Older browsers: keepalive lets the request outlive the page.
        fetch(ENDPOINT, {
          method: 'POST',
          body: body,
          headers: { 'Content-Type': CONTENT_TYPE },
          keepalive: true,
          mode: 'cors'
        }).catch(function () {});
      }
    } catch (e) {
      /* Tracking must never break a storefront. */
    }
  }

  function queueEvent(type, detail) {
    detail = detail || {};
    if (!detail.block) return;

    queue.push({
      type: type,
      block: detail.block,
      page_type: detail.page_type || 'unknown',
      session: session(),
      handle: detail.handle || null,
      anchor: detail.anchor || null,
      position: detail.position || null
    });

    if (queue.length >= MAX_BATCH) {
      send();
    } else if (!timer) {
      timer = setTimeout(send, FLUSH_MS);
    }
  }

  function rememberClick(detail) {
    if (!detail.handle) return;
    try {
      window.sessionStorage.setItem(CLICK_KEY, JSON.stringify({
        block: detail.block,
        page_type: detail.page_type,
        anchor: detail.anchor || null,
        handle: detail.handle,
        ts: Date.now()
      }));
    } catch (e) {
      /* private browsing throws; add_to_cart is simply not attributed */
    }
  }

  function lastClick() {
    try {
      var raw = window.sessionStorage.getItem(CLICK_KEY);
      if (!raw) return null;
      var click = JSON.parse(raw);
      if (!click || !click.handle) return null;
      if (Date.now() - click.ts > ATTRIBUTION_MS) return null;
      return click;
    } catch (e) {
      return null;
    }
  }

  // The block scripts emit "ymal_impression" and "ymal_click"; strip the
  // prefix so the stored type is the plain event name.
  window.ymalTrack = function (name, detail) {
    var type = String(name || '').replace(/^ymal_/, '');
    if (type === 'impression' && detail && detail.handles) {
      // One impression per product in the row, so click rate has a real
      // denominator rather than one row counting as one view.
      detail.handles.forEach(function (handle, index) {
        queueEvent('impression', {
          block: detail.block,
          page_type: detail.page_type,
          anchor: detail.anchor,
          handle: handle,
          position: index + 1
        });
      });
      return;
    }
    // Remembered here rather than in the section's script, so the widget file
    // needs no change and any future block gets this for free.
    if (type === 'click') rememberClick(detail || {});
    queueEvent(type, detail);
  };

  /*
   * Add to cart.
   *
   * The theme dispatches `on:cart:add` on its product form, bubbling, carrying
   * only detail.variantId - see the CartForm/ProductForm component in main.js.
   * A variant id is not enough: we need the product handle to know whether
   * this is the product the shopper clicked in a YMAL row. /cart.js has it,
   * and the item is definitely there because the add has just succeeded.
   *
   * This is deliberately NOT a fetch interceptor. The theme gives us a real
   * event, and wrapping window.fetch on a live storefront to infer the same
   * thing would be guessing at someone else's internals.
   *
   * Only adds that match a recent YMAL click are recorded. An add from the
   * product page reached any other way is not ours to claim.
   */
  var lastAddSeen = 0;

  function recordAdd(click, handle) {
    queueEvent('add_to_cart', {
      block: click.block,
      page_type: click.page_type,
      anchor: click.anchor,
      handle: handle,
      // The row that caused this is on the previous page, so there is no
      // position to report.
      position: null
    });
    // Sent at once rather than waiting for the batch timer: the page may be
    // about to navigate to the cart.
    send();
  }

  function onCartAdd(event) {
    var variantId = event && event.detail && event.detail.variantId;
    if (!variantId) return;

    // The theme can fire this more than once for one add (form submit plus a
    // drawer refresh). One add is one event.
    var now = Date.now();
    if (now - lastAddSeen < 1500) return;
    lastAddSeen = now;

    var click = lastClick();
    if (!click) return;

    // On a product page the handle is in the URL, so the add can be recorded
    // synchronously. That matters: with the theme's "after add to cart" set to
    // `page`, it navigates to the cart 300ms later (main.js, the ProductForm
    // submit handler), and an in-flight /cart.js would lose the race.
    //
    // Quick buy has no such hurry - it opens in place and the page stays put -
    // so falling back to a lookup there is safe.
    var fromUrl = window.location.pathname.match(/\/products\/([^/?#]+)/);
    if (fromUrl) {
      if (fromUrl[1] !== click.handle) return;
      recordAdd(click, click.handle);
      return;
    }

    fetch('/cart.js', { credentials: 'same-origin' })
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (cart) {
        if (!cart || !cart.items) return;

        var added = null;
        for (var i = 0; i < cart.items.length; i++) {
          if (String(cart.items[i].variant_id) === String(variantId)) {
            added = cart.items[i];
            break;
          }
        }
        if (!added || added.handle !== click.handle) return;
        recordAdd(click, added.handle);
      })
      .catch(function () {
        /* tracking must never break a storefront */
      });
  }

  document.addEventListener('on:cart:add', onCartAdd);

  // Anything still queued when the page goes away. visibilitychange rather
  // than unload, which mobile browsers often skip entirely.
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'hidden') send();
  });
})();
