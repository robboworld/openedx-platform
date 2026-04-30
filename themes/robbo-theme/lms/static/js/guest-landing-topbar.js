/**
 * Copyright (C) 2024-2026 Robbo <https://robbo.ru>
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Part of the Robbo Open edX distribution. See NOTICE at edx-platform repository root.
 *
 * Гостевой лендинг: topbar fixed; зелёный фон и белый логотип только после того, как блок hero
 * полностью вышел из viewport (пользователь «прокрутил мимо» .robbo-guest-hero).
 */
(function () {
  'use strict';

  var topbar = document.querySelector('.robbo-guest-topbar');
  var hero = document.querySelector('.robbo-guest-hero');
  if (!topbar || !hero) {
    return;
  }

  function setScrolled(pastHero) {
    topbar.classList.toggle('robbo-guest-topbar--scrolled', pastHero);
  }

  if (typeof IntersectionObserver === 'undefined') {
    // Крайний случай: ориентир по нижней границе hero.
    function fallbackUpdate() {
      setScrolled(hero.getBoundingClientRect().bottom <= 0);
    }
    fallbackUpdate();
    window.addEventListener('scroll', fallbackUpdate, { passive: true });
    window.addEventListener('resize', fallbackUpdate);
    return;
  }

  var observer = new IntersectionObserver(
    function (entries) {
      entries.forEach(function (entry) {
        // Пока hero пересекается с viewport — «ещё на первом экране»; иначе — уже ниже hero.
        setScrolled(!entry.isIntersecting);
      });
    },
    {
      root: null,
      threshold: 0,
    }
  );

  observer.observe(hero);
})();
