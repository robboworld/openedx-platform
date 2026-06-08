/**
 * Copyright (C) 2024-2026 Robbo <https://robbo.ru>
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Part of the Robbo Open edX distribution. See NOTICE at edx-platform repository root.
 *
 * Гостевой лендинг: topbar sticky; зелёный фон и белый логотип после прокрутки мимо intro-блока.
 */
(function () {
  'use strict';

  var topbar = document.querySelector('.robbo-guest-topbar');
  var sentinel = document.querySelector('.robbo-guest-home__sentinel');
  if (!topbar || !sentinel) {
    return;
  }

  function setScrolled(pastIntro) {
    topbar.classList.toggle('robbo-guest-topbar--scrolled', pastIntro);
  }

  if (typeof IntersectionObserver === 'undefined') {
    function fallbackUpdate() {
      setScrolled(sentinel.getBoundingClientRect().bottom <= 0);
    }
    fallbackUpdate();
    window.addEventListener('scroll', fallbackUpdate, { passive: true });
    window.addEventListener('resize', fallbackUpdate);
    return;
  }

  var observer = new IntersectionObserver(
    function (entries) {
      entries.forEach(function (entry) {
        setScrolled(!entry.isIntersecting);
      });
    },
    {
      root: null,
      threshold: 0,
    }
  );

  observer.observe(sentinel);
})();
