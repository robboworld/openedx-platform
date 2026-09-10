/**
 * After LMS login, establish LK BFF session (lk_bff_session on localhost:8080)
 * so LK + RS recognize the user without a separate Sign in step.
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'robbo_bff_bridge_v1';
  var startBase = window.__ROBBO_BFF_SSO_START__;
  if (!startBase) {
    return;
  }

  var path = window.location.pathname || '';
  if (
    path.indexOf('/oauth2/') !== -1 ||
    path.indexOf('/login') === 0 ||
    path.indexOf('/logout') === 0
  ) {
    return;
  }

  var state = null;
  try {
    state = window.sessionStorage.getItem(STORAGE_KEY);
  } catch (e) {
    return;
  }

  if (state === 'done') {
    return;
  }
  if (state === 'pending') {
    try {
      window.sessionStorage.setItem(STORAGE_KEY, 'done');
    } catch (e) {
      // ignore
    }
    return;
  }

  var returnTo = window.location.href;
  var bridgeUrl = startBase;
  if (bridgeUrl.indexOf('return_to=') === -1) {
    bridgeUrl += (bridgeUrl.indexOf('?') === -1 ? '?' : '&') +
      'return_to=' + encodeURIComponent(returnTo);
  }

  try {
    window.sessionStorage.setItem(STORAGE_KEY, 'pending');
  } catch (e) {
    return;
  }
  window.location.replace(bridgeUrl);
})();
