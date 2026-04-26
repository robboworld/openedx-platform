/**
 * /courses stub interest buttons — placeholder until backend API exists.
 */
(function () {
  'use strict';

  document.addEventListener('click', function (e) {
    var btn = e.target && e.target.closest && e.target.closest('button.robbo-courses-catalog__stub-notify');
    if (!btn) {
      return;
    }
    var id = btn.getAttribute('data-stub-id');
    if (id) {
      console.debug('[robbo-courses-catalog] notify interest:', id);
    }
  });
}());
