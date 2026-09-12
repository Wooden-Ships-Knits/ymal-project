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
    queueEvent(type, detail);
  };

  // Anything still queued when the page goes away. visibilitychange rather
  // than unload, which mobile browsers often skip entirely.
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'hidden') send();
  });
})();
