/**
 * Robbo patch for the ORA Studio editor: max_files_count on save, necessity rules, RU select
 * labels, and per-extension size limits ("Larger file sizes").
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
          // Write only on change: replacing the text node is itself a DOM mutation.
          if (Object.prototype.hasOwnProperty.call(labels, opt.value) && opt.textContent !== labels[opt.value]) {
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

  // --- "Larger file sizes" option: per-extension size limit rows in the editor ---

  var SIZE_UNIT_FALLBACK = {
    MB: 'МБ',
  };

  function tSizeUnit(msg) {
    if (typeof window.gettext === 'function') {
      var translated = window.gettext(msg);
      if (translated && translated !== msg) {
        return translated;
      }
    }
    return SIZE_UNIT_FALLBACK[msg] || msg;
  }

  function readJsonAttr(el, name, fallback) {
    try {
      return JSON.parse(el.getAttribute(name) || '') || fallback;
    } catch (error) {
      return fallback;
    }
  }

  function normalizeExtension(value) {
    return String(value || '').trim().replace(/^\.+/, '').toLowerCase();
  }

  function selectedExtensions(wrapper) {
    var typeSelect = document.getElementById('openassessment_submission_upload_selector');
    var type = typeSelect ? typeSelect.value : '';
    var presets = readJsonAttr(wrapper, 'data-presets', {});
    var list = presets[type];
    if (!list) {
      var custom = document.getElementById('openassessment_submission_white_listed_file_types');
      list = custom ? custom.value.split(',') : [];
    }
    var seen = {};
    return list.map(normalizeExtension).filter(function (ext) {
      if (!ext || seen[ext]) {
        return false;
      }
      seen[ext] = true;
      return true;
    });
  }

  function clampMb(wrapper, value) {
    var cap = parseInt(wrapper.getAttribute('data-cap-mb'), 10) || 50;
    var mb = parseInt(value, 10);
    if (Number.isNaN(mb)) {
      return null;
    }
    return Math.max(1, Math.min(cap, mb));
  }

  function renderSizeRows(wrapper) {
    var list = wrapper.querySelector('.robbo-ora-size-limits__list');
    var empty = wrapper.querySelector('.robbo-ora-size-limits__empty');
    if (!list) {
      return;
    }
    var defaultMb = parseInt(wrapper.getAttribute('data-default-mb'), 10) || 5;
    var limits = wrapper._robboLimits;
    var extensions = selectedExtensions(wrapper);
    list.replaceChildren();
    extensions.forEach(function (ext) {
      var id = 'robbo_ora_size_limit_' + ext.replace(/[^a-z0-9_-]/g, '_');
      var row = document.createElement('li');
      row.className = 'robbo-ora-size-limits__row';
      var label = document.createElement('label');
      label.setAttribute('for', id);
      label.textContent = '.' + ext;
      var input = document.createElement('input');
      input.id = id;
      input.type = 'text';
      input.className = 'input setting-input';
      input.setAttribute('inputmode', 'numeric');
      input.setAttribute('maxlength', '2');
      input.setAttribute('data-extension', ext);
      input.value = String(limits[ext] || defaultMb);
      var unit = document.createElement('span');
      unit.textContent = tSizeUnit('MB');
      row.appendChild(label);
      row.appendChild(input);
      row.appendChild(unit);
      list.appendChild(row);
    });
    if (empty) {
      empty.classList.toggle('is--hidden', extensions.length > 0);
    }
  }

  function syncSizeVisibility(wrapper) {
    var toggle = wrapper.querySelector('#robbo_ora_large_files_toggle');
    var panel = wrapper.querySelector('.robbo-ora-size-limits');
    if (toggle && panel) {
      panel.classList.toggle('is--hidden', !toggle.checked);
      toggle.setAttribute('aria-expanded', toggle.checked ? 'true' : 'false');
    }
  }

  function initLargeFiles() {
    var wrapper = document.getElementById('robbo_ora_large_files_wrapper');
    if (!wrapper || wrapper._robboInit) {
      return;
    }
    wrapper._robboInit = true;
    wrapper._robboLimits = readJsonAttr(wrapper, 'data-limits', {});
    renderSizeRows(wrapper);
    syncSizeVisibility(wrapper);

    wrapper.addEventListener('change', function (event) {
      if (event.target.id === 'robbo_ora_large_files_toggle') {
        syncSizeVisibility(wrapper);
      }
    });
    wrapper.addEventListener('input', function (event) {
      var input = event.target;
      var ext = input.getAttribute && input.getAttribute('data-extension');
      if (!ext) {
        return;
      }
      input.value = input.value.replace(/[^0-9]/g, '');
      var mb = clampMb(wrapper, input.value);
      input.classList.toggle('is--invalid', mb === null || String(mb) !== input.value);
      if (mb !== null) {
        wrapper._robboLimits[ext] = mb;
      }
    });
    wrapper.addEventListener('focusout', function (event) {
      var input = event.target;
      var ext = input.getAttribute && input.getAttribute('data-extension');
      if (!ext) {
        return;
      }
      var mb = clampMb(wrapper, input.value) || parseInt(wrapper.getAttribute('data-default-mb'), 10) || 5;
      input.value = String(mb);
      input.classList.remove('is--invalid');
      wrapper._robboLimits[ext] = mb;
    });
    // Rebuild the rows when the author switches the upload type or edits the custom list.
    ['openassessment_submission_upload_selector', 'openassessment_submission_white_listed_file_types']
      .forEach(function (id) {
        var el = document.getElementById(id);
        if (el) {
          el.addEventListener('change', function () { renderSizeRows(wrapper); });
          el.addEventListener('input', function () { renderSizeRows(wrapper); });
        }
      });
  }

  function readSizeSettings() {
    var wrapper = document.getElementById('robbo_ora_large_files_wrapper');
    if (!wrapper) {
      return null;
    }
    var toggle = wrapper.querySelector('#robbo_ora_large_files_toggle');
    var limits = {};
    wrapper.querySelectorAll('input[data-extension]').forEach(function (input) {
      var mb = clampMb(wrapper, input.value);
      if (mb !== null) {
        limits[input.getAttribute('data-extension')] = mb;
      }
    });
    return { enabled: !!(toggle && toggle.checked), limits: limits };
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
        // edx-ora2 bundles ServerClient inside webpack (no global), so extend the save request itself.
        var sizeSettings = readSizeSettings();
        if (sizeSettings) {
          payload.robbo_large_files = sizeSettings.enabled;
          payload.robbo_file_size_limits = sizeSettings.limits;
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
    if (!editor || editor._robboBooted) {
      return;
    }
    // The editor template is rendered on the server in one piece, so a single pass is enough.
    editor._robboBooted = true;
    syncNecessityOptionLabels();
    installNecessityFieldListeners();
    updateNecessityHintVisibility();
    initLargeFiles();
  }

  installSaveValidationGuard();
  installAjaxHooks();

  // The editor appears later (Edit modal) and comes back as a new element after reopening.
  // The observer only looks it up, at most once per 100 ms; it must never write to the DOM itself:
  // writes from the callback retriggered it endlessly and froze Studio on ORA Edit.
  if (!document._robboOraEditorObserver) {
    var bootTimer = null;
    document._robboOraEditorObserver = new MutationObserver(function () {
      if (bootTimer === null) {
        bootTimer = window.setTimeout(function () {
          bootTimer = null;
          bootEditorPatch();
        }, 100);
      }
    });
    document._robboOraEditorObserver.observe(document.documentElement, {
      childList: true,
      subtree: true,
    });
  }

  bootEditorPatch();
}());
