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

  var KEY = 'ymal:viewed';
  var MAX_STORED = 20;      // deep enough to survive filtering, cheap to keep
  var CARD_VIEW = 'ymal-card';

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

  // Newest first, one entry per product. Only the handle is stored: title,
  // price and image are fetched fresh at render, so nothing here goes stale.
  function record(entry) {
    if (!entry || !entry.handle) return;
    var next = read().filter(function (p) { return p.handle !== entry.handle; });
    next.unshift({ handle: entry.handle, id: entry.id, ts: Date.now() });
    write(next.slice(0, MAX_STORED));
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

    var handles = read()
      .filter(function (p) { return String(p.id) !== String(anchor); })
      .slice(0, slots)
      .map(function (p) { return p.handle; });

    if (!handles.length) return;

    Promise.all(handles.map(fetchCard)).then(function (cards) {
      var shown = [];

      cards.forEach(function (html, i) {
        // An empty card means the theme chose not to render it — sold out,
        // unpublished, gone. That check belongs in Liquid, not here.
        if (!html) return;
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

    document
      .querySelectorAll('[data-ymal-block="recently_viewed"]')
      .forEach(render);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
