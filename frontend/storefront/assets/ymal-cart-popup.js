/*
 * YMAL — the add to cart popup.
 *
 * Opens the moment a product is added, with a few things that go with it. It is
 * the one moment a shopper has already decided to buy, which is why upsell apps
 * all fight for it.
 *
 *   on:cart:add (the theme's own event)
 *     -> /cart.js                          what was added: handle, title
 *     -> /products/<h>?view=ymal-ibyv      that product's Featured list
 *     -> /products/<h>?view=ymal-card-compact   a card for each
 *
 * WHY THE FEATURED LIST. The nightly pass orders it by co-purchase - what
 * shoppers actually buy in the same order - which beat content similarity by
 * 16.5% to 29.4% on a year of held-out baskets. For "you just added this", that
 * is the right question; "looks similar" is the wrong one, and would offer a
 * second sweater almost identical to the one already in the bag.
 *
 * NOT ANOTHER COLORWAY of what they just added: they have bought that sweater.
 * One card per style, nothing already in the cart, and nothing at all if fewer
 * than two survive - a popup holding one product reads as a bug.
 *
 * The pure functions are exported for `node --test`; the browser half only runs
 * where there is a document.
 */
(function (root) {
  'use strict';

  var BLOCK = 'cart_popup';
  var MINIMUM = 2;

  // ---------------------------------------------------------------------------
  // Pure - tested in frontend/storefront/tests/ymal-cart-popup.test.js
  // ---------------------------------------------------------------------------

  /*
   * Which of a product's Featured list to offer.
   *
   *   source   { handles, styles } from the ymal-ibyv template, in order
   *   added    { handle, style } the product just added
   *   inCart   handles already in the cart, the added one included
   *   slots    how many to show
   */
  function offers(source, added, inCart, slots) {
    var handles = (source && source.handles) || [];
    var styles = (source && source.styles) || [];
    var seen = Object.create(null);
    var out = [];

    if (added && added.style) seen[added.style] = true;

    handles.forEach(function (handle, i) {
      if (out.length >= slots) return;
      if (!handle || handle === (added && added.handle)) return;
      if ((inCart || []).indexOf(handle) !== -1) return;

      // A handle with no style counts as its own, which is how this behaved
      // before the template sent styles at all.
      var style = styles[i] || handle;
      if (seen[style]) return;

      seen[style] = true;
      out.push(handle);
    });

    return out;
  }

  var api = { offers: offers, MINIMUM: MINIMUM, BLOCK: BLOCK };
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (typeof document === 'undefined') return;

  // ---------------------------------------------------------------------------
  // Browser
  // ---------------------------------------------------------------------------

  if (root.__ymalCartPopup) return;
  root.__ymalCartPopup = true;

  function panel() {
    return document.querySelector('[data-ymal-popup]');
  }

  function getJSON(url) {
    return fetch(url, { credentials: 'same-origin', cache: 'no-store' })
      .then(function (res) { return res.ok ? res.json() : null; })
      .catch(function () { return null; });
  }

  function getText(url) {
    return fetch(url, { credentials: 'same-origin' })
      .then(function (res) { return res.ok ? res.text() : ''; })
      .catch(function () { return ''; });
  }

  function track(name, detail) {
    if (typeof root.ymalTrack === 'function') root.ymalTrack(name, detail);
  }

  // The same pair every YMAL placement writes: the block for "this order
  // involved YMAL", the handle for the stricter "YMAL sold this".
  function attribute(handle) {
    return fetch('/cart/update.js', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        attributes: { 'YMAL block': BLOCK, 'YMAL product': handle }
      })
    }).catch(function () {});
  }

  function notifyTheme() {
    document.dispatchEvent(
      new CustomEvent('on:cart:change', { bubbles: true, cancelable: false })
    );
  }

  // What the theme's event gives us is a variant id; the cart knows the rest,
  // and knows it AFTER the add, which is exactly when this runs.
  function addedProduct(variantId) {
    return getJSON('/cart.js').then(function (cart) {
      if (!cart) return null;
      var items = cart.items || [];
      var match = null;
      items.forEach(function (item) {
        if (String(item.variant_id) === String(variantId)) match = item;
      });
      // No variant id (a theme that does not pass one): the newest line is the
      // best guess, and it is right whenever the shopper just added something.
      if (!match) match = items[items.length - 1];
      if (!match) return null;
      return {
        handle: match.handle,
        style: (match.product_title || '').trim().toUpperCase(),
        title: match.product_title || '',
        inCart: items.map(function (item) { return item.handle; })
      };
    });
  }

  function sourceFor(handle) {
    return getText('/products/' + encodeURIComponent(handle) + '?view=ymal-ibyv')
      .then(function (text) {
        try {
          return JSON.parse(text);
        } catch (e) {
          return { handles: [], styles: [] };
        }
      });
  }

  function cardFor(handle) {
    return getText(
      '/products/' + encodeURIComponent(handle) + '?view=ymal-card-compact'
    ).then(function (html) { return html.trim(); });
  }

  function buildAdd(card, onAdded) {
    var ids = JSON.parse(card.getAttribute('data-variants') || '[]');
    var titles = JSON.parse(card.getAttribute('data-variant-titles') || '[]');
    var available = JSON.parse(card.getAttribute('data-variant-available') || '[]');
    var handle = card.getAttribute('data-handle');

    var sellable = ids
      .map(function (id, i) { return { id: id, title: titles[i], ok: available[i] }; })
      .filter(function (v) { return v.ok; });
    if (!sellable.length) return null;

    var select = null;
    if (sellable.length > 1) {
      select = document.createElement('select');
      select.className = 'ymal-rv__variant';
      select.setAttribute('aria-label', 'Choose a size');
      sellable.forEach(function (v) {
        var option = document.createElement('option');
        option.value = v.id;
        option.textContent = v.title;
        select.appendChild(option);
      });
    }

    var button = document.createElement('button');
    button.type = 'button';
    button.className = 'ymal-rv__add';
    button.textContent = 'Add';
    button.addEventListener('click', function () {
      button.disabled = true;
      button.textContent = 'Adding';
      fetch('/cart/add.js', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          items: [{ id: select ? Number(select.value) : sellable[0].id, quantity: 1 }]
        })
      })
        .then(function (res) {
          if (!res.ok) throw new Error('add failed');
          track('ymal_add_to_cart', { block: BLOCK, page_type: pageType(), handle: handle });
          return attribute(handle).then(function () {
            button.textContent = 'Added';
            notifyTheme();
            onAdded(handle);
          });
        })
        .catch(function () {
          button.disabled = false;
          button.textContent = 'Add';
        });
    });

    return { button: button, select: select };
  }

  function pageType() {
    var el = panel();
    return (el && el.getAttribute('data-ymal-page')) || 'unknown';
  }

  function close() {
    var el = panel();
    if (!el) return;
    el.hidden = true;
    document.documentElement.classList.remove('ymal-pop-open');
  }

  function open(el, handles, added) {
    el.hidden = false;
    document.documentElement.classList.add('ymal-pop-open');
    track('ymal_impression', {
      block: BLOCK, page_type: pageType(), anchor: added.handle, handles: handles
    });
    var first = el.querySelector('.ymal-rv__add, [data-ymal-close]');
    if (first) first.focus();
  }

  function fill(el, handles, added) {
    var list = el.querySelector('[data-ymal-items]');
    if (!list) return Promise.resolve(false);

    return Promise.all(handles.map(cardFor)).then(function (cards) {
      var fragment = document.createDocumentFragment();
      var shown = [];

      cards.forEach(function (html, i) {
        if (!html) return;
        var holder = document.createElement('div');
        holder.innerHTML = html;
        var card = holder.querySelector('.ymal-rv__card');
        if (!card) return;

        var control = buildAdd(card, function () {});
        if (!control) return;

        if (control.select) card.querySelector('.ymal-rv__meta').appendChild(control.select);
        card.appendChild(control.button);
        fragment.appendChild(card);
        shown.push(handles[i]);
      });

      // Below two, this is not a row of suggestions - it is one product in a
      // box, and it reads as something that failed to load.
      if (shown.length < MINIMUM) return false;

      while (list.firstChild) list.removeChild(list.firstChild);
      list.appendChild(fragment);

      var added_ = el.querySelector('[data-ymal-added]');
      if (added_) added_.textContent = added.title;

      open(el, shown, added);
      return true;
    });
  }

  function onAdd(event) {
    var el = panel();
    if (!el || !el.hidden) return;

    var variantId = event && event.detail && event.detail.variantId;
    addedProduct(variantId).then(function (added) {
      if (!added || !added.handle) return;
      return sourceFor(added.handle).then(function (source) {
        var slots = parseInt(el.getAttribute('data-ymal-slots'), 10) || 3;
        var handles = offers(source, added, added.inCart, slots);
        if (handles.length < MINIMUM) return false;
        return fill(el, handles, added);
      });
    }).catch(function () {
      /* an upsell is never worth breaking a storefront over */
    });
  }

  function init() {
    var el = panel();
    if (!el) return;

    el.addEventListener('click', function (event) {
      if (event.target.closest('[data-ymal-close]')) {
        event.preventDefault();
        close();
        return;
      }

      var card = event.target.closest('.ymal-rv__card');
      var link = event.target.closest('a[href*="/products/"]');
      if (!card || !link) return;

      track('ymal_click', {
        block: BLOCK,
        page_type: pageType(),
        handle: card.getAttribute('data-handle')
      });
      attribute(card.getAttribute('data-handle'));
    });

    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && !el.hidden) close();
    });

    document.addEventListener('on:cart:add', onAdd);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})(typeof window !== 'undefined' ? window : this);
