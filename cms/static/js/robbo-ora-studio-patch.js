/**
 * Robbo patch: max_files_count on save, necessity rules, RU select labels.
 */
(function () {
  'use strict';

  var OPTIONAL_TEXT_BLOCKED_MSG_EN = (
    'When File Upload Response is disabled, Text Response must be Required. '
    + 'Enable file uploads below first, or keep the text response required.'
  );
  var OPTIONAL_TEXT_BLOCKED_MSG_RU = (
    'Пока загрузка файлов отключена, текстовый ответ может быть только обязательным. '
    + 'Сначала включите «Ответ с загрузкой файлов» ниже (обязательно или необязательно).'
  );

  function readMaxFilesCount() {
    var el = document.getElementById('openassessment_max_files_editor');
    if (!el) {
      return null;
    }
    var value = parseInt(el.value, 10);
    if (Number.isNaN(value)) {
      return null;
    }
    return Math.max(1, Math.min(20, value));
  }

  function isRussianStudioUi() {
    // Session locale (Authoring language) overrides <html lang="..."> from LANGUAGE_CODE.
    if (typeof django !== 'undefined' && django.getLanguage) {
      var sessionLang = String(django.getLanguage() || '').toLowerCase();
      if (sessionLang) {
        return sessionLang.indexOf('ru') === 0;
      }
    }
    var docLang = (document.documentElement && document.documentElement.lang) || '';
    return docLang.toLowerCase().indexOf('ru') === 0;
  }

  function t(en, ru) {
    return isRussianStudioUi() ? ru : en;
  }

  function optionalTextBlockedMessage() {
    return t(OPTIONAL_TEXT_BLOCKED_MSG_EN, OPTIONAL_TEXT_BLOCKED_MSG_RU);
  }

  function setOptionDisabled(selectEl, value, disabled) {
    var option = selectEl.querySelector('option[value="' + value + '"]');
    if (option) {
      option.disabled = disabled;
    }
  }

  function getNecessityFields() {
    return {
      textSel: document.getElementById('openassessment_submission_text_response'),
      fileSel: document.getElementById('openassessment_submission_file_upload_response'),
    };
  }

  /**
   * Mirror edx-ora2 server rules in studio_mixin.update_editor_context.
   */
  function getNecessityValidationError() {
    var fields = getNecessityFields();
    if (!fields.textSel || !fields.fileSel) {
      return null;
    }
    var text = fields.textSel.value;
    var file = fields.fileSel.value;
    if (!text && !file) {
      return t(
        'Text Response and File Upload Response cannot both be disabled.',
        'Текстовый ответ и загрузка файлов не могут быть отключены одновременно.'
      );
    }
    if (!text && file === 'optional') {
      return t(
        'When Text Response is disabled, File Upload Response must be Required.',
        'Если текстовый ответ отключён, загрузка файлов должна быть обязательной.'
      );
    }
    if (!file && text === 'optional') {
      return optionalTextBlockedMessage();
    }
    return null;
  }

  function ensureInlineNecessityHint() {
    var wrapper = document.getElementById('openassessment_submission_text_response_wrapper');
    if (!wrapper) {
      return null;
    }
    var hint = document.getElementById('robbo_ora_text_response_necessity_hint');
    if (hint) {
      return hint;
    }
    hint = document.createElement('p');
    hint.id = 'robbo_ora_text_response_necessity_hint';
    hint.className = 'setting-help robbo-ora-necessity-hint';
    hint.textContent = t(
      'To make the text response optional, enable file uploads below (required or optional).',
      'Чтобы сделать текстовый ответ необязательным, сначала включите загрузку файлов ниже.'
    );
    wrapper.appendChild(hint);
    return hint;
  }

  var NECESSITY_LABELS_EN = { required: 'Required', optional: 'Optional', '': 'None' };
  var NECESSITY_LABELS_RU = {
    required: 'Обязательно',
    optional: 'Необязательно',
    '': 'Нет',
  };

  function syncNecessityOptionLabels() {
    ['openassessment_submission_text_response', 'openassessment_submission_file_upload_response'].forEach(
      function (selectId) {
        var sel = document.getElementById(selectId);
        if (!sel) {
          return;
        }
        var lang = (sel.getAttribute('data-robbo-ora-ui-lang') || '').toLowerCase();
        var labels = lang.indexOf('ru') === 0 ? NECESSITY_LABELS_RU : NECESSITY_LABELS_EN;
        Array.prototype.forEach.call(sel.options, function (opt) {
          if (Object.prototype.hasOwnProperty.call(labels, opt.value)) {
            opt.textContent = labels[opt.value];
          }
        });
      },
    );
  }

  function updateNecessityHintVisibility() {
    var fields = getNecessityFields();
    var hint = document.getElementById('robbo_ora_text_response_necessity_hint')
      || ensureInlineNecessityHint();
    if (!hint || !fields.fileSel) {
      return;
    }
    var show = !fields.fileSel.value;
    hint.classList.toggle('is--visible', show);
    hint.classList.toggle('is--hidden', !show);
  }

  function showStudioValidationAlert(message) {
    var title = t('Save Unsuccessful', 'Не удалось сохранить');
    var shown = false;

    if (window.jQuery) {
      var $ = window.jQuery;
      var $alert = $('#openassessment_validation_alert');
      if ($alert.length) {
        $alert.find('.openassessment_alert_title').text(title);
        $alert.find('.openassessment_alert_message').text(message);
        $alert.removeClass('covered');
        var editorElement = $alert.parent();
        var alertHeight = $alert.outerHeight() || 0;
        var headerHeight = $('#openassessment_editor_header', editorElement).outerHeight() || 0;
        $('.oa_editor_content_wrapper', editorElement).css({
          height: 'calc(100% - ' + (alertHeight + headerHeight) + 'px)',
          'border-top-right-radius': '0px',
          'border-top-left-radius': '0px',
        });
        shown = true;
      }
    }

    var hint = ensureInlineNecessityHint();
    if (hint) {
      hint.textContent = message;
      hint.classList.add('is--visible');
      hint.classList.remove('is--hidden');
      hint.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      shown = true;
    }

    if (!shown) {
      window.alert(title + '\n\n' + message);
    }
  }

  function syncNecessitySelectOptions() {
    var fields = getNecessityFields();
    if (!fields.textSel || !fields.fileSel) {
      return;
    }

    [fields.textSel, fields.fileSel].forEach(function (sel) {
      Array.prototype.forEach.call(sel.options, function (opt) {
        opt.disabled = false;
      });
    });

    if (!fields.fileSel.value) {
      setOptionDisabled(fields.textSel, '', true);
      setOptionDisabled(fields.textSel, 'optional', true);
    }
    if (!fields.textSel.value) {
      setOptionDisabled(fields.fileSel, '', true);
      setOptionDisabled(fields.fileSel, 'optional', true);
    }
  }

  function onTextResponseChange() {
    var fields = getNecessityFields();
    if (!fields.textSel || !fields.fileSel) {
      return;
    }
    if (fields.textSel.value === 'optional' && !fields.fileSel.value) {
      fields.textSel.value = 'required';
      showStudioValidationAlert(optionalTextBlockedMessage());
    }
    syncNecessitySelectOptions();
    updateNecessityHintVisibility();
  }

  function onFileResponseChange() {
    syncNecessitySelectOptions();
    updateNecessityHintVisibility();
  }

  function installNecessityFieldListeners() {
    var editor = document.getElementById('openassessment-editor');
    if (!editor || editor._robboNecessityListeners) {
      return;
    }
    var fields = getNecessityFields();
    if (!fields.textSel || !fields.fileSel) {
      return;
    }
    fields.textSel.addEventListener('change', onTextResponseChange);
    fields.fileSel.addEventListener('change', onFileResponseChange);
    editor._robboNecessityListeners = true;
    syncNecessitySelectOptions();
    updateNecessityHintVisibility();
  }

  function installSaveValidationGuard() {
    if (document._robboOraSaveGuard) {
      return;
    }
    document._robboOraSaveGuard = true;
    document.addEventListener('click', function (event) {
      var target = event.target;
      if (!target.closest || !target.closest('.openassessment_save_button')) {
        return;
      }
      var msg = getNecessityValidationError();
      if (!msg) {
        return;
      }
      event.preventDefault();
      event.stopImmediatePropagation();
      showStudioValidationAlert(msg);
    }, true);
  }

  function translateServerMessage(msg) {
    if (!msg || !isRussianStudioUi()) {
      return msg;
    }
    if (msg.indexOf('When File Upload Response is disabled') !== -1) {
      return optionalTextBlockedMessage();
    }
    if (msg.indexOf('When Text Response is disabled') !== -1) {
      return 'Если текстовый ответ отключён, загрузка файлов должна быть обязательной.';
    }
    if (msg.indexOf('cannot both be disabled') !== -1) {
      return 'Текстовый ответ и загрузка файлов не могут быть отключены одновременно.';
    }
    return msg;
  }

  function installAjaxHooks() {
    if (!window.jQuery || window.jQuery._robboOraAjaxHooks) {
      return;
    }
    var $ = window.jQuery;
    $.ajaxPrefilter(function (options) {
      if (!options.url || options.url.indexOf('update_editor_context') === -1) {
        return;
      }
      if (options.type !== 'POST' || typeof options.data !== 'string') {
        return;
      }
      try {
        var payload = JSON.parse(options.data);
        var maxFiles = readMaxFilesCount();
        if (maxFiles !== null) {
          payload.max_files_count = maxFiles;
        }
        options.data = JSON.stringify(payload);
      } catch (e) {
        // leave request unchanged
      }
    });
    $(document).ajaxComplete(function (_event, xhr, settings) {
      if (!settings.url || settings.url.indexOf('update_editor_context') === -1) {
        return;
      }
      try {
        var data = JSON.parse(xhr.responseText);
        if (data && data.success === false && data.msg) {
          showStudioValidationAlert(translateServerMessage(data.msg));
        }
      } catch (e) {
        // ignore non-JSON responses
      }
    });
    window.jQuery._robboOraAjaxHooks = true;
  }

  function bootEditorPatch() {
    var editor = document.getElementById('openassessment-editor');
    if (!editor) {
      return false;
    }
    if (!editor._robboBooted) {
      editor._robboBooted = true;
      if (!editor._robboLabelObserver) {
        var observer = new MutationObserver(function () {
          syncNecessityOptionLabels();
          installNecessityFieldListeners();
          updateNecessityHintVisibility();
        });
        observer.observe(editor, { childList: true, subtree: true });
        editor._robboLabelObserver = observer;
      }
    }
    syncNecessityOptionLabels();
    installNecessityFieldListeners();
    updateNecessityHintVisibility();
    return true;
  }

  installSaveValidationGuard();
  installAjaxHooks();

  if (!document._robboOraEditorObserver) {
    document._robboOraEditorObserver = new MutationObserver(function () {
      bootEditorPatch();
    });
    document._robboOraEditorObserver.observe(document.documentElement, {
      childList: true,
      subtree: true,
    });
  }

  bootEditorPatch();
}());
