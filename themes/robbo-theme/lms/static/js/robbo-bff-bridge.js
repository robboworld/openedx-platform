/**
 * After LMS login, establish LK BFF session (lk_bff_session) in the background
 * so LK + RS recognize the user without a separate Sign in step.
 *
 * Runs silent SSO in a hidden iframe: the page never navigates away, so a BFF
 * failure (lost PKCE state, LMS lookup error, …) can no longer drop the user
 * on the LK login page. The iframe lands on a tiny LMS asset on success.
 * The cookie sticks only when LK and LMS are same-site (prod: *.robbo.ru);
 * otherwise LK/RS fall back to their own silent SSO on first visit.
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'robbo_bff_bridge_v2';
  var TIMEOUT_MS = 15000;
  var startBase = window.__ROBBO_BFF_SSO_START__;
  if (!startBase) {
    return;
  }

  // Learning MFE embeds courseware via /xblock/ iframes; also skips the bridge's own iframe.
  if (window !== window.top) {
    return;
  }

  var path = window.location.pathname || '';
  if (
    path.indexOf('/oauth2/') !== -1 ||
    path.indexOf('/xblock/') !== -1 ||
    path.indexOf('/login') === 0 ||
    path.indexOf('/logout') === 0
  ) {
    return;
  }

  try {
    if (window.sessionStorage.getItem(STORAGE_KEY) === 'done') {
      return;
    }
  } catch (e) {
    return;
  }

  var returnTo = window.location.origin + '/favicon.ico';
  var bridgeUrl = startBase;
  if (bridgeUrl.indexOf('return_to=') === -1) {
    bridgeUrl += (bridgeUrl.indexOf('?') === -1 ? '?' : '&') +
      'return_to=' + encodeURIComponent(returnTo);
  }

  var frame = null;
  var timer = null;

  function finish() {
    if (timer) {
      window.clearTimeout(timer);
      timer = null;
    }
    // One attempt per tab, success or not: a failed silent SSO must not repeat on every page.
    try {
      window.sessionStorage.setItem(STORAGE_KEY, 'done');
    } catch (e) {
      // ignore
    }
    if (frame && frame.parentNode) {
      frame.parentNode.removeChild(frame);
    }
    frame = null;
  }

  function start() {
    frame = document.createElement('iframe');
    frame.setAttribute('aria-hidden', 'true');
    frame.setAttribute('tabindex', '-1');
    frame.setAttribute('title', '');
    frame.hidden = true;
    frame.addEventListener('load', finish);
    timer = window.setTimeout(finish, TIMEOUT_MS);
    frame.src = bridgeUrl;
    document.body.appendChild(frame);
  }

  if (document.body) {
    start();
  } else {
    document.addEventListener('DOMContentLoaded', start);
  }
})();
