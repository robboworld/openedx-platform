/**
 * Header copy tweaks when Indigo (or other) templates are not overridden from this repo.
 */
(function () {
  'use strict';

  function apply() {
    document.querySelectorAll('a.register-btn').forEach(function (anchor) {
      var t = (anchor.textContent || '').trim();
      if (t === 'Register for free' || t.indexOf('Register') === 0) {
        anchor.textContent = 'Регистрация';
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', apply);
  } else {
    apply();
  }
}());
