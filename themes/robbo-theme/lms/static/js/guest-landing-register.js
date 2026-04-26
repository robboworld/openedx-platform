/**
 * Гостевой лендинг: отправка регистрации на RegistrationView (POST create_account), разбор JSON.
 */
(function () {
  'use strict';

  var form = document.getElementById('robbo-guest-register-form');
  if (!form) {
    return;
  }

  var submitBtn = form.querySelector('[type="submit"]');
  var formError = document.getElementById('robbo-guest-register-form-error');

  var fieldIds = {
    name: 'robbo-reg-name',
    email: 'robbo-reg-email',
    company: 'robbo-reg-company',
    username: 'robbo-reg-username',
    password: 'robbo-reg-password',
  };

  function clearFieldErrors() {
    Object.keys(fieldIds).forEach(function (key) {
      var el = document.getElementById(fieldIds[key]);
      if (!el) {
        return;
      }
      el.removeAttribute('aria-invalid');
      var msg = document.getElementById(fieldIds[key] + '-err');
      if (msg) {
        msg.textContent = '';
        msg.hidden = true;
      }
    });
  }

  function setFormError(message) {
    if (!formError) {
      return;
    }
    if (message) {
      formError.textContent = message;
      formError.hidden = false;
    } else {
      formError.textContent = '';
      formError.hidden = true;
    }
  }

  function showFieldErrors(payload) {
    if (!payload || typeof payload !== 'object') {
      return;
    }
    Object.keys(fieldIds).forEach(function (key) {
      var row = payload[key];
      if (!row || !row.length || !row[0].user_message) {
        return;
      }
      var input = document.getElementById(fieldIds[key]);
      var msgEl = document.getElementById(fieldIds[key] + '-err');
      if (input) {
        input.setAttribute('aria-invalid', 'true');
      }
      if (msgEl) {
        msgEl.textContent = row[0].user_message;
        msgEl.hidden = false;
      }
    });
    if (payload.error_message && payload.error_message.length) {
      var first = payload.error_message[0];
      if (first && first.user_message) {
        setFormError(first.user_message);
      }
    }
  }

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    clearFieldErrors();
    setFormError('');

    var action = form.getAttribute('action');
    if (!action) {
      setFormError('Не задан адрес отправки формы.');
      return;
    }

    var body = new URLSearchParams(new FormData(form));
    if (submitBtn) {
      submitBtn.disabled = true;
    }

    fetch(action, {
      method: 'POST',
      body: body,
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
      },
      credentials: 'same-origin',
    })
      .then(function (response) {
        var ct = response.headers.get('content-type') || '';
        if (ct.indexOf('application/json') === -1) {
          if (response.status === 403) {
            throw new Error('Регистрация с логином и паролем на этой площадке отключена. Используйте стандартную страницу входа.');
          }
          throw new Error('Не удалось обработать ответ сервера. Попробуйте позже.');
        }
        return response.json().then(function (data) {
          return { ok: response.ok, status: response.status, data: data };
        });
      })
      .then(function (result) {
        if (result.ok && result.data && result.data.success && result.data.redirect_url) {
          window.location.href = result.data.redirect_url;
          return;
        }
        if (result.data) {
          showFieldErrors(result.data);
          if (!formError || formError.hidden) {
            if (result.data.error_code === 'duplicate-email') {
              setFormError('Указанный email уже занят.');
            } else if (result.data.error_code && String(result.data.error_code).indexOf('duplicate') === 0) {
              setFormError('Пользователь с таким email или логином уже существует.');
            } else if (result.status === 400) {
              setFormError('Проверьте поля формы.');
            }
          }
        }
      })
      .catch(function (err) {
        setFormError(err.message || 'Ошибка сети. Попробуйте позже.');
      })
      .then(function () {
        if (submitBtn) {
          submitBtn.disabled = false;
        }
      });
  });
}());
