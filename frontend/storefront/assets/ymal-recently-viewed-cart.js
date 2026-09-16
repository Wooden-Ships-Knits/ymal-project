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
 *
 * KEEPING UP WITH THE CART. Rendered once at page load, the block went stale
 * the moment the cart changed: add the sweater you are looking at and the
 * drawer opened with that same sweater under Recently Viewed. It now re-renders
 * whenever the theme reports a cart change, and reads the cart from /cart.js.
 * (It used to collect every /products/ link on the page, which also swept up
 * the YMAL rows, the menu and anything else linking to a product.)
 *
 * ADDING FROM THE BLOCK tells the theme with the theme's own on:cart:change
 * event, so the cart list, subtotal and header count update like any other add
 * - and the same event re-renders this block without the product just added.
 */
(function () {
  'use strict';

  // Loaded by a snippet inside the drawer; run once however often it appears.
  if (window.__ymalRecentlyViewedCart) return;
  window.__ymalRecentlyViewedCart = true;

  var KEY = 'ymal:viewed';
  var CARD_VIEW = 'ymal-card-compact';
  var BLOCK = 'recently_viewed';
  // Fetch more than are shown, because the gate rejects some and a drawer with
  // one card in it looks like a bug.
  var OVERFETCH = 4;

  // Symmetry's names. on:cart:change is fired after any cart update the theme
  // makes; on:cart:after-merge once the drawer's markup has caught up;
  // on:cart:add by the product form. Listening to all three costs one debounced
  // render and does not depend on which path a given add took.
  var CART_EVENTS = ['on:cart:change', 'on:cart:after-merge', 'on:cart:add'];
  var SELECTOR = '.ymal-rv[data-ymal-page="cart"]';

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

  // Never recommend something already in the cart - the drawer is showing it
  // three inches above. A failed read shows the history unfiltered rather than
  // nothing.
  function cartHandles() {
    return fetch('/cart.js', { credentials: 'same-origin', cache: 'no-store' })
      .then(function (res) { return res.ok ? res.json() : { items: [] }; })
      .then(function (cart) {
        return (cart.items || []).map(function (item) { return item.handle; });
      })
      .catch(function () { return []; });
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

  // The cart attribute that attributes a later purchase to this block - the
  // same one every other YMAL row writes.
  function attribute() {
    return fetch('/cart/update.js', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ attributes: { 'YMAL block': BLOCK } })
    }).catch(function () {});
  }

  function notifyTheme() {
    document.dispatchEvent(
      new CustomEvent('on:cart:change', { bubbles: true, cancelable: false })
    );
  }

  function buildControl(card) {
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
          track('ymal_add_to_cart', { block: BLOCK, page_type: 'cart', handle: handle });
          // Attribute before the theme re-reads the cart, then let it refresh.
          // Its on:cart:change also re-renders this block, which drops the
          // product just added and brings in the next one.
          return attribute().then(notifyTheme);
        })
        .catch(function () {
          button.disabled = false;
          button.textContent = 'Add';
        });
    });

    wrap.appendChild(button);
    return { button: wrap, select: select };
  }

  function drawerOf(section) {
    return section.closest('cart-drawer, .drawer');
  }

  function drawerIsOpen(section) {
    var drawer = drawerOf(section);
    // Not inside a drawer (a cart page, say): it is on screen when rendered.
    return !drawer || drawer.hasAttribute('open');
  }

  // Once per opening of the drawer, and only while it is open. Counting at page
  // load recorded an impression on every page view, drawer opened or not; and
  // counting each re-render counted one opening two or three times, because a
  // single add fires several cart events. Either would flatter every click rate
  // built on it.
  function impression(section) {
    var shown = section.__ymalShown || [];
    if (!shown.length || section.__ymalSeen) return;
    section.__ymalSeen = true;
    track('ymal_impression', { block: BLOCK, page_type: 'cart', handles: shown });
  }

  // Watches the drawer's own `open` attribute rather than the theme's open
  // event, so it works however the drawer was opened - cart icon, an add, or
  // the theme's own script - and whether or not that event reaches document.
  function watchDrawer(section) {
    var drawer = drawerOf(section);
    if (!drawer || drawer.__ymalWatched || !('MutationObserver' in window)) return;
    drawer.__ymalWatched = true;

    new MutationObserver(function () {
      var open = drawer.hasAttribute('open');
      each(function (s) {
        if (!drawer.contains(s)) return;
        if (!open) {
          s.__ymalSeen = false;
          return;
        }
        // An add opens the drawer a moment before this block has re-rendered
        // without the product just added. Counting now would record the old
        // cards; the render counts it instead when it lands.
        if (pending || s.__ymalBusy) return;
        impression(s);
      });
    }).observe(drawer, { attributes: true, attributeFilter: ['open'] });
  }

  // One card at a time: the strip is a scroll-snap row, so a swipe needs no
  // script. The arrows step it by exactly one card, and stay hidden when there
  // is only one - a control that cannot do anything.
  function wireArrows(section) {
    var list = section.querySelector('[data-ymal-items]');
    var prev = section.querySelector('[data-ymal-prev]');
    var next = section.querySelector('[data-ymal-next]');
    if (!list || !prev || !next) return;

    var many = (section.__ymalShown || []).length > 1;
    prev.hidden = !many;
    next.hidden = !many;

    // Listeners survive a re-render: the buttons live in the snippet's markup,
    // only the cards below them are replaced.
    if (section.__ymalArrows) return;
    section.__ymalArrows = true;

    function step(direction) {
      var card = list.querySelector('.ymal-rv__card');
      // Card width plus the gap in the snippet's CSS.
      var by = card ? card.getBoundingClientRect().width + 8 : list.clientWidth;
      list.scrollBy({ left: direction * by, behavior: 'smooth' });
    }

    prev.addEventListener('click', function () { step(-1); });
    next.addEventListener('click', function () { step(1); });
  }

  function render(section) {
    var list = section.querySelector('[data-ymal-items]');
    if (!list) return;

    // Cart events arrive in bursts, and each render is several fetches. Only
    // the newest render may touch the block.
    var generation = (section.__ymalGeneration || 0) + 1;
    section.__ymalGeneration = generation;
    section.__ymalBusy = true;

    var slots = parseInt(section.getAttribute('data-ymal-slots'), 10) || 3;
    var viewed = read()
      .map(function (p) { return p && p.handle; })
      .filter(Boolean);

    if (!viewed.length) {
      section.hidden = true;
      section.__ymalBusy = false;
      return;
    }

    cartHandles()
      .then(function (inCart) {
        var handles = viewed
          .filter(function (h) { return inCart.indexOf(h) === -1; })
          .slice(0, slots * OVERFETCH);
        return Promise.all(handles.map(fetchCard)).then(function (cards) {
          return { handles: handles, cards: cards };
        });
      })
      .then(function (result) {
        if (section.__ymalGeneration !== generation) return;

        // Built off-screen and swapped in at once, so a re-render never shows
        // a half-empty block.
        var fragment = document.createDocumentFragment();
        var shown = [];

        result.cards.forEach(function (html, i) {
          if (!html || shown.length >= slots) return;

          var holder = document.createElement('div');
          holder.innerHTML = html;
          var card = holder.querySelector('.ymal-rv__card');
          if (!card) return;

          var control = buildControl(card);
          if (!control) return;

          if (control.select) card.querySelector('.ymal-rv__meta').appendChild(control.select);
          card.appendChild(control.button);

          fragment.appendChild(card);
          shown.push(result.handles[i]);
        });

        while (list.firstChild) list.removeChild(list.firstChild);
        list.appendChild(fragment);

        section.__ymalShown = shown;
        section.__ymalBusy = false;
        // An empty heading is worse than no block.
        section.hidden = shown.length === 0;
        wireArrows(section);
        if (shown.length && drawerIsOpen(section)) impression(section);
      })
      .catch(function () {
        if (section.__ymalGeneration === generation) section.__ymalBusy = false;
      });
  }

  function each(fn) {
    document.querySelectorAll(SELECTOR).forEach(fn);
  }

  // Declared before watchDrawer's observer can fire; null when no render is
  // waiting to start.
  var pending = null;
  function renderAllSoon() {
    clearTimeout(pending);
    pending = setTimeout(function () {
      pending = null;
      each(render);
    }, 150);
  }

  function init() {
    each(function (section) {
      if (section.dataset.ymalReady) return;
      section.dataset.ymalReady = '1';
      watchDrawer(section);
      render(section);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  CART_EVENTS.forEach(function (name) {
    document.addEventListener(name, renderAllSoon);
  });
})();
