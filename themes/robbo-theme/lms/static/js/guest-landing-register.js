/**
 * Гостевой лендинг: валидация как в Authn MFE (isFormValid + validators), POST create_account, разбор JSON.
 * Тексты — в духе frontend-app-authn src/i18n/ru.json.
 */
(function () {
  'use strict';

  // Сообщения (по смыслу совпадают с MFE ru.json)
  var M = {
    emptyName: 'Введите ФИО',
    nameInvalid: 'Введите корректное ФИО',
    emptyEmail: 'Введите email',
    emailFormat: 'Введите корректный email',
    usernameLen: 'Логин: от 2 до 30 символов',
    usernameFormat: 'Допустимы буквы (A–Z, a–z), цифры (0–9), подчёркивание (_) и дефис (-). Пробелы недопустимы.',
    password: 'Пароль не соответствует требованиям',
    company: 'Укажите название компании',
    /** Согласие с рассылками; формулировка в духе registration.opt.in / MFE */
    marketing: 'Необходимо согласие на получение новостей и рекламных рассылок',
    honor: 'Необходимо согласие на обработку персональных данных',
  };

  // Как в frontend-app-authn src/data/constants.js
  var LETTER_REGEX = /[a-zA-Z]/;
  var NUMBER_REGEX = /\d/;
  var VALID_EMAIL_REGEX = '(^[-!#$%&\'*+/=?^_`{}|~0-9A-Z]+(\\.[-!#$%&\'*+/=?^_`{}|~0-9A-Z]+)*'
    + '|^"([\\001-\\010\\013\\014\\016-\\037!#-\\[\\]-\\177]|\\\\[\\001-\\011\\013\\014\\016-\\177])*"'
    + ')@((?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\\.)+)(?:[A-Z0-9-]{2,63})'
    + '|\\[(25[0-5]|2[0-4]\\d|[0-1]?\\d?\\d)(\\.(25[0-5]|2[0-4]\\d|[0-1]?\\d?\\d)){3}\\]$';
  var emailRegex = new RegExp(VALID_EMAIL_REGEX, 'i');

  // NameField/validator.js (без флага g у URL_REGEX — стабильный .test)
  var URL_REGEX = /[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_+.~#?&//=]*)?/i;
  var HTML_REGEX = /<|>/;
  var INVALID_NAME_REGEX = /https?:\/\/(?:[-\w.]|(?:%[\da-fA-F]{2}))*/g;

  // UsernameField/validator.js
  var VALID_USERNAME_REGEX = /^[a-zA-Z0-9_-]+$/i;

  var form = document.getElementById('robbo-guest-register-form');
  if (!form) {
    return;
  }

  var passwordReqEls = {
    letter: document.getElementById('robbo-reg-password-req-letter'),
    number: document.getElementById('robbo-reg-password-req-number'),
    len: document.getElementById('robbo-reg-password-req-len'),
  };

  function updatePasswordRequirementHints() {
    var el = getInput('password');
    if (!el) {
      return;
    }
    var v = el.value;
    if (passwordReqEls.letter) {
      passwordReqEls.letter.classList.toggle('robbo-guest-register__password-req--ok', LETTER_REGEX.test(v));
    }
    if (passwordReqEls.number) {
      passwordReqEls.number.classList.toggle('robbo-guest-register__password-req--ok', NUMBER_REGEX.test(v));
    }
    if (passwordReqEls.len) {
      passwordReqEls.len.classList.toggle('robbo-guest-register__password-req--ok', v.length >= 8);
    }
  }

  var formLoadTimeMs = Date.now();
  var submitBtn = form.querySelector('[type="submit"]');
  var formError = document.getElementById('robbo-guest-register-form-error');

  var fieldIds = {
    name: 'robbo-reg-name',
    email: 'robbo-reg-email',
    company: 'robbo-reg-company',
    username: 'robbo-reg-username',
    password: 'robbo-reg-password',
  };

  function getInput(key) {
    return document.getElementById(fieldIds[key]);
  }

  function showFieldError(key, message) {
    var input = getInput(key);
    var msgEl = document.getElementById(fieldIds[key] + '-err');
    if (input) {
      input.setAttribute('aria-invalid', 'true');
    }
    if (msgEl) {
      msgEl.textContent = message;
      msgEl.hidden = false;
    }
  }

  function clearFieldErrors() {
    Object.keys(fieldIds).forEach(function (key) {
      var el = getInput(key);
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

  function validateNameValue(value) {
    if (!value || !String(value).trim()) {
      return M.emptyName;
    }
    var v = String(value);
    if (URL_REGEX.test(v) || HTML_REGEX.test(v)) {
      return M.nameInvalid;
    }
    INVALID_NAME_REGEX.lastIndex = 0;
    if (INVALID_NAME_REGEX.test(v)) {
      return M.nameInvalid;
    }
    return '';
  }

  /**
   * Корректность email: как в MFE (regex + длина), плюс структурные проверки.
   * Ведущие/конечные пробелы снимаются при проверке; внутренние пробелы — ошибка.
   */
  function validateEmailValue(value) {
    if (value == null || value === undefined) {
      return M.emptyEmail;
    }
    var s = String(value).trim();
    if (!s) {
      return M.emptyEmail;
    }
    if (/\s/.test(s)) {
      return M.emailFormat;
    }
    if (s.length <= 2) {
      return M.emailFormat;
    }
    var parts = s.split('@');
    if (parts.length !== 2) {
      return M.emailFormat;
    }
    var local = parts[0];
    var domain = parts[1];
    if (!local || !domain) {
      return M.emailFormat;
    }
    if (local.length > 64 || domain.length > 253) {
      return M.emailFormat;
    }
    if (local.indexOf('..') !== -1 || domain.indexOf('..') !== -1) {
      return M.emailFormat;
    }
    if (local[0] === '.' || local[local.length - 1] === '.') {
      return M.emailFormat;
    }
    if (domain.indexOf('.') === -1) {
      return M.emailFormat;
    }
    var domainLabels = domain.split('.');
    for (var i = 0; i < domainLabels.length; i++) {
      if (!domainLabels[i].length || domainLabels[i].length > 63) {
        return M.emailFormat;
      }
    }
    var tld = domainLabels[domainLabels.length - 1];
    if (tld.length < 2) {
      return M.emailFormat;
    }
    if (!emailRegex.test(s)) {
      return M.emailFormat;
    }
    return '';
  }

  function validateUsernameValue(value) {
    if (!value || value.length <= 1 || value.length > 30) {
      return M.usernameLen;
    }
    if (!VALID_USERNAME_REGEX.test(value)) {
      return M.usernameFormat;
    }
    return '';
  }

  function validatePasswordValue(value) {
    if (!value || !LETTER_REGEX.test(value) || !NUMBER_REGEX.test(value) || value.length < 8) {
      return M.password;
    }
    return '';
  }

  function validateCompanyValue(value) {
    if (!value || !String(value).trim()) {
      return M.company;
    }
    return '';
  }

  /**
   * @returns {boolean} true если есть ошибки клиентской валидации
   */
  function runClientValidation() {
    var name = (getInput('name') && getInput('name').value) || '';
    var email = (getInput('email') && getInput('email').value) || '';
    var company = (getInput('company') && getInput('company').value) || '';
    var username = (getInput('username') && getInput('username').value) || '';
    var password = (getInput('password') && getInput('password').value) || '';

    var err;
    var hasError = false;

    err = validateNameValue(name);
    if (err) {
      showFieldError('name', err);
      hasError = true;
    }
    err = validateEmailValue(email);
    if (err) {
      showFieldError('email', err);
      hasError = true;
    }
    err = validateCompanyValue(company);
    if (err) {
      showFieldError('company', err);
      hasError = true;
    }
    err = validateUsernameValue(username);
    if (err) {
      showFieldError('username', err);
      hasError = true;
    }
    err = validatePasswordValue(password);
    if (err) {
      showFieldError('password', err);
      hasError = true;
    }

    var marketing = form.querySelector('input[name="marketing_emails_opt_in"]');
    var honor = form.querySelector('input[name="honor_code"]');
    if (!marketing || !marketing.checked) {
      setFormError(M.marketing);
      hasError = true;
    } else if (!honor || !honor.checked) {
      setFormError(M.honor);
      hasError = true;
    }

    return hasError;
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
      showFieldError(key, row[0].user_message);
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

    if (runClientValidation()) {
      return;
    }

    var emailEl = getInput('email');
    if (emailEl) {
      emailEl.value = String(emailEl.value).trim();
    }

    var action = form.getAttribute('action');
    if (!action) {
      setFormError('Не задан адрес отправки формы.');
      return;
    }

    var body = new URLSearchParams(new FormData(form));
    var elapsedSec = (Date.now() - formLoadTimeMs) / 1000;
    body.set('total_registration_time', String(Math.round(elapsedSec * 1000) / 1000));
    if (!body.get('next')) {
      body.set('next', '/courses');
    }

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
        var data = result.data;
        var success = data && (data.success !== false);
        if (result.ok && data && data.redirect_url && success) {
          window.location.href = data.redirect_url;
          return;
        }
        if (data) {
          showFieldErrors(data);
          if (!formError || formError.hidden) {
            if (data.error_code === 'duplicate-email') {
              setFormError('Указанный email уже занят.');
            } else if (data.error_code && String(data.error_code).indexOf('duplicate') === 0) {
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

  var passwordInput = getInput('password');
  if (passwordInput) {
    passwordInput.addEventListener('input', updatePasswordRequirementHints);
    passwordInput.addEventListener('change', updatePasswordRequirementHints);
    updatePasswordRequirementHints();
  }
}());
