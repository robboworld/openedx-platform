/**
 * Copyright (C) 2024-2026 Robbo <https://robbo.ru>
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Part of the Robbo Open edX distribution. See NOTICE at edx-platform repository root.
 *
 * Гостевой лендинг: баннер согласия на cookie / метаданные. Один раз на устройство — ключ в localStorage.
 * Тот же ключ, что раньше в Authn MFE, чтобы на одном origin не показывать повторно после принятия там.
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'robbo.authn.cookieConsent.accepted';
  var root = document.getElementById('robbo-cookie-consent-root');
  var btn = document.getElementById('robbo-cookie-consent-accept');

  if (!root) {
    return;
  }

  try {
    if (window.localStorage.getItem(STORAGE_KEY) === 'true') {
      root.setAttribute('hidden', '');
    }
  } catch (e) {
    // storage недоступен — оставляем баннер видимым
  }

  if (!btn) {
    return;
  }

  btn.addEventListener('click', function () {
    try {
      window.localStorage.setItem(STORAGE_KEY, 'true');
    } catch (e) {
      // скрываем только на текущем визите
    }
    root.setAttribute('hidden', '');
  });
}());
