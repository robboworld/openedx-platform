/**
 * /courses stub interest buttons.
 */
(function () {
  'use strict';

  var root = document.querySelector('.robbo-courses-catalog');
  if (!root) {
    return;
  }

  function getCookie(name) {
    var cookieValue = null;
    var cookies;
    var i;
    var cookie;

    if (document.cookie && document.cookie !== '') {
      cookies = document.cookie.split(';');
      for (i = 0; i < cookies.length; i += 1) {
        cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === (name + '=')) {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  function getQueryParam(name) {
    var query = window.location.search.substring(1).split('&');
    var i;
    var pair;

    for (i = 0; i < query.length; i += 1) {
      pair = query[i].split('=');
      if (decodeURIComponent(pair[0] || '') === name) {
        return decodeURIComponent(pair.slice(1).join('=') || '');
      }
    }
    return '';
  }

  function getCard(btn) {
    return btn.closest && btn.closest('.robbo-courses-catalog__stub');
  }

  function getStatus(btn) {
    var card = getCard(btn);
    return card && card.querySelector('.robbo-courses-catalog__stub-status');
  }

  function setButtonState(btn, state, label, message) {
    var status = getStatus(btn);
    var labelNode = btn.querySelector('.robbo-courses-catalog__stub-notify-label');
    var card = getCard(btn);
    var defaultLabel = btn.getAttribute('data-default-label') || 'Сообщить об открытии';

    btn.classList.remove('is-loading', 'is-success', 'is-error');
    if (card) {
      card.classList.remove('is-interest-loading', 'is-interest-success', 'is-interest-error');
    }

    if (state) {
      btn.classList.add('is-' + state);
      if (card) {
        card.classList.add('is-interest-' + state);
      }
    }

    btn.setAttribute('data-state', state || 'idle');
    btn.disabled = state === 'loading' || state === 'success';
    if (labelNode) {
      labelNode.textContent = label || defaultLabel;
    }
    if (status) {
      status.textContent = message || '';
    }
  }

  function redirectGuest(stubId) {
    var registerUrl = root.getAttribute('data-register-url') || '/register';
    var nextUrl = '/courses?notify_stub=' + encodeURIComponent(stubId);
    var separator = registerUrl.indexOf('?') === -1 ? '?' : '&';

    window.location.href = registerUrl + separator + 'next=' + encodeURIComponent(nextUrl);
  }

  function clearNotifyQuery() {
    if (window.history && window.history.replaceState) {
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }

  function submitInterest(btn, shouldClearQuery) {
    var stubId = btn.getAttribute('data-stub-id');
    var endpoint = root.getAttribute('data-course-interest-url');
    var state = btn.getAttribute('data-state');

    if (!stubId || !endpoint || state === 'loading' || state === 'success') {
      return;
    }

    if (root.getAttribute('data-authenticated') !== 'true') {
      redirectGuest(stubId);
      return;
    }

    setButtonState(btn, 'loading', 'Отправляем...', 'Отправляем заявку.');

    fetch(endpoint, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken') || ''
      },
      body: JSON.stringify({
        stub_id: stubId
      })
    }).then(function (response) {
      return response.json().catch(function () {
        return {};
      }).then(function (data) {
        if (!response.ok || !data.ok) {
          throw new Error(data.message || 'Не удалось отправить заявку. Попробуйте ещё раз.');
        }
        return data;
      });
    }).then(function (data) {
      setButtonState(
        btn,
        'success',
        'Вы подписаны',
        data.message || 'Мы сообщим на вашу почту, когда курс откроется.'
      );
      if (shouldClearQuery) {
        clearNotifyQuery();
      }
    }).catch(function (err) {
      setButtonState(
        btn,
        'error',
        null,
        err.message || 'Не удалось отправить заявку. Попробуйте ещё раз.'
      );
    });
  }

  function findButtonByStubId(stubId) {
    var buttons = root.querySelectorAll('button.robbo-courses-catalog__stub-notify');
    var i;

    for (i = 0; i < buttons.length; i += 1) {
      if (buttons[i].getAttribute('data-stub-id') === stubId) {
        return buttons[i];
      }
    }
    return null;
  }

  document.addEventListener('click', function (e) {
    var btn = e.target && e.target.closest && e.target.closest('button.robbo-courses-catalog__stub-notify');
    if (btn) {
      submitInterest(btn, false);
    }
  });

  var pendingStubId = getQueryParam('notify_stub');
  if (pendingStubId && root.getAttribute('data-authenticated') === 'true') {
    var pendingBtn = findButtonByStubId(pendingStubId);
    if (pendingBtn) {
      pendingBtn.focus();
      submitInterest(pendingBtn, true);
    }
  }
}());
