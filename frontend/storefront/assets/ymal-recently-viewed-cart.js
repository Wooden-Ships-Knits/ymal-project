/*
 * YMAL — Recently Viewed, in the cart drawer.
 *
 * Reads the same localStorage list every other placement reads, written by
 * ymal-recently-viewed.js on each product page. This file only renders; it
 * never records.
 *
 * NEWEST FIRST. Someone looking at their cart is still deciding, and the most
 * recent thing they looked at is the strongest candidate.
 *
 * Cards come from the theme (/products/<handle>?view=ymal-card-compact) rather
 * than being built here, so the eligibility gate runs in Liquid where the live
 * product is - sold out, *SALE* and fixed-stock products render as nothing and
 * are skipped, and prices are always today's.
 */
(function () {
  'use strict';

  var KEY = 'ymal:viewed';
  var CARD_VIEW = 'ymal-card-compact';
  // Fetch more than are shown, because the gate rejects some and a drawer with
  // one card in it looks like a bug.
  var OVERFETCH = 4;

  function read() {
    try {
      var raw = window.localStorage.getItem(KEY);
      var list = raw ? JSON.parse(raw) : [];
      return Array.isArray(list) ? list : [];
    } catch (e) {
      // Private browsing throws rather than returning null. The block simply
      // never appears.
      return [];
    }
  }

  function cartHandles() {
    // Never recommend something already in the cart. The drawer is showing it
    // three inches above.
    var handles = [];
    document.querySelectorAll('a[href*="/products/"]').forEach(function (a) {
      var drawer = a.closest('[data-ymal-block]');
      if (drawer) return;
      var match = a.getAttribute('href').match(/\/products\/([^/?#]+)/);
      if (match) handles.push(match[1]);
    });
    return handles;
  }

  function fetchCard(handle) {
    return fetch('/products/' + encodeURIComponent(handle) + '?view=' + CARD_VIEW, {
      credentials: 'same-origin'
    })
      .then(function (res) { return res.ok ? res.text() : ''; })
      .then(function (html) { return html.trim(); })
      .catch(function () { return ''; });
  }

  function track(name, detail) {
    if (typeof window.ymalTrack === 'function') window.ymalTrack(name, detail);
  }

  function addToCart(id, quantity) {
    return fetch('/cart/add.js', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items: [{ id: id, quantity: quantity || 1 }] })
    }).then(function (res) {
      if (!res.ok) throw new Error('add failed');
      return res.json();
    });
  }

  function buildControl(card, onAdded) {
    var ids = JSON.parse(card.getAttribute('data-variants') || '[]');
    var titles = JSON.parse(card.getAttribute('data-variant-titles') || '[]');
    var available = JSON.parse(card.getAttribute('data-variant-available') || '[]');
    var handle = card.getAttribute('data-handle');

    var sellable = ids
      .map(function (id, i) { return { id: id, title: titles[i], ok: available[i] }; })
      .filter(function (v) { return v.ok; });

    if (!sellable.length) return null;

    var wrap = document.createElement('div');
    var select = null;

    // Only draw a picker when there is a choice to make. A one-variant product
    // with a dropdown of one is a control that does nothing.
    if (sellable.length > 1) {
      select = document.createElement('select');
      select.className = 'ymal-rv__variant';
      select.setAttribute('aria-label', 'Choose a variant');
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
      var id = select ? Number(select.value) : sellable[0].id;
      button.disabled = true;
      button.textContent = 'Adding';

      addToCart(id, 1)
        .then(function () {
          track('ymal_add_to_cart', {
            block: 'recently_viewed',
            page_type: 'cart',
            handle: handle
          });
          onAdded(handle);
        })
        .catch(function () {
          button.disabled = false;
          button.textContent = 'Add';
        });
    });

    wrap.appendChild(button);
    return { button: wrap, select: select };
  }

  function render(section) {
    var list = section.querySelector('[data-ymal-items]');
    if (!list) return;

    var slots = parseInt(section.getAttribute('data-ymal-slots'), 10) || 3;
    var inCart = cartHandles();

    var handles = read()
      .map(function (p) { return p.handle; })
      .filter(function (h) { return inCart.indexOf(h) === -1; })
      .slice(0, slots * OVERFETCH);

    if (!handles.length) return;

    Promise.all(handles.map(fetchCard)).then(function (cards) {
      var shown = [];

      cards.forEach(function (html, i) {
        if (!html || shown.length >= slots) return;

        var holder = document.createElement('div');
        holder.innerHTML = html;
        var card = holder.querySelector('.ymal-rv__card');
        if (!card) return;

        var control = buildControl(card, function (handle) {
          // Replaced, not removed: the row keeps its length so the drawer does
          // not jump, and the shopper gets another suggestion in its place.
          replace(section, card, handle);
        });
        if (!control) return;

        if (control.select) card.querySelector('.ymal-rv__meta').appendChild(control.select);
        card.appendChild(control.button);

        list.appendChild(card);
        shown.push(handles[i]);
      });

      if (!shown.length) return;
      section.hidden = false;

      track('ymal_impression', {
        block: 'recently_viewed',
        page_type: 'cart',
        handles: shown
      });
    });
  }

  // Pulls the next eligible product that is not already on screen.
  function replace(section, card, addedHandle) {
    var list = section.querySelector('[data-ymal-items]');
    var onScreen = Array.prototype.map.call(
      list.querySelectorAll('.ymal-rv__card'),
      function (c) { return c.getAttribute('data-handle'); }
    );
    var inCart = cartHandles();

    var next = read()
      .map(function (p) { return p.handle; })
      .filter(function (h) {
        return h !== addedHandle &&
               onScreen.indexOf(h) === -1 &&
               inCart.indexOf(h) === -1;
      })[0];

    if (!next) {
      // Nothing left to offer. Drop the card, and hide the whole block if it
      // was the last one - an empty heading is worse than no block.
      card.remove();
      if (!list.querySelector('.ymal-rv__card')) section.hidden = true;
      return;
    }

    fetchCard(next).then(function (html) {
      if (!html) { card.remove(); return; }
      var holder = document.createElement('div');
      holder.innerHTML = html;
      var fresh = holder.querySelector('.ymal-rv__card');
      if (!fresh) { card.remove(); return; }

      var control = buildControl(fresh, function (handle) {
        replace(section, fresh, handle);
      });
      if (!control) { card.remove(); return; }

      if (control.select) fresh.querySelector('.ymal-rv__meta').appendChild(control.select);
      fresh.appendChild(control.button);
      card.replaceWith(fresh);
    });
  }

  function init() {
    document
      .querySelectorAll('.ymal-rv[data-ymal-page="cart"]')
      .forEach(function (section) {
        if (section.dataset.ymalReady) return;
        section.dataset.ymalReady = '1';
        render(section);
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // The drawer is often re-rendered when the cart changes, which replaces the
  // block with a fresh empty one. Re-initialise when that happens.
  document.addEventListener('cart:updated', init);
  document.addEventListener('cart:refresh', init);
})();
