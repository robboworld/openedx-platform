/**
 * Robbo ORA (LMS + Studio preview): upload limits, Russian file picker, i18n, optional file descriptions.
 * DOM/event-based — does not rely on OpenAssessment.ResponseView (removed in newer edx-ora2).
 * Presentation lives in ROBBO_ORA_RESPONSE_STEP_CSS (robbo_ora_i18n.py); this script only toggles
 * classes, text and disabled state.
 */
(function () {
  'use strict';

  if (window.RobboOraUploadPatch && window.RobboOraUploadPatch.installed) {
    if (typeof window.RobboOraUploadPatch.refresh === 'function') {
      window.RobboOraUploadPatch.refresh();
    }
    return;
  }

  var DEFAULT_FILE_DESCRIPTION = '-';

  var FALLBACK_CATALOG = {
    'Upload file': 'Загрузить файл',
    'Upload files': 'Загрузить файлы',
    'Delete File': 'Удалить файл',
    'Supported file types: ': 'Поддерживаемые типы файлов: ',
    'Maximum file size: %(max_mb)s MB.': 'Максимальный размер файла: %(max_mb)s МБ.',
    'Describe {filename} (optional):': 'Описание «{filename}» (необязательно):',
    'Individual file size must be {max_files_mb}MB or less.': (
      'Размер каждого файла не должен превышать {max_files_mb} МБ.'
    ),
    'Upload failed. Check that the file is within the size limit and try again.': (
      'Не удалось загрузить файл. Проверьте размер файла и попробуйте снова.'
    ),
    'Please provide a description for each file you are uploading.': (
      'Укажите описание для каждого загружаемого файла.'
    ),
    '%(count)s files selected': 'Выбрано файлов: %(count)s',
    'Too many files: the limit is {max}. Already uploaded: {saved}, selected: {selected}. Choose no more than {left}.': (
      'Слишком много файлов: можно прикрепить не более {max}. Уже загружено: {saved}, выбрано: {selected}. '
      + 'Выберите не больше {left}.'
    ),
    'You have already uploaded the maximum number of files ({max}). To add another one, delete an uploaded file.': (
      'Уже загружено максимальное количество файлов ({max}). Чтобы добавить новый, удалите один из загруженных.'
    ),
    'The file "{name}" is larger than {mb} MB, the limit for .{ext} files.': (
      'Файл «{name}» больше {mb} МБ — это ограничение для файлов .{ext}.'
    ),
    'File limit reached ({max}). To add another file, delete an uploaded one.': (
      'Достигнут лимит файлов ({max}). Чтобы добавить новый, удалите один из загруженных.'
    ),
  };

  function isRussianUi() {
    var lang = (document.documentElement && document.documentElement.lang) || '';
    if (lang.toLowerCase().indexOf('ru') === 0) {
      return true;
    }
    if (typeof django !== 'undefined' && django.getLanguage) {
      return String(django.getLanguage() || '').toLowerCase().indexOf('ru') === 0;
    }
    return false;
  }

  function format(template, values) {
    return Object.keys(values).reduce(function (text, key) {
      return text.split('{' + key + '}').join(String(values[key]));
    }, template);
  }

  function gettext(msg) {
    if (typeof django !== 'undefined' && django.gettext) {
      var translated = django.gettext(msg);
      if (translated && translated !== msg) {
        return translated;
      }
    }
    if (isRussianUi() && FALLBACK_CATALOG[msg]) {
      return FALLBACK_CATALOG[msg];
    }
    return msg;
  }

  function trim(value) {
    return (value || '').replace(/^\s+|\s+$/g, '');
  }

  function setTranslatedText(node, msgid) {
    var translated = gettext(msgid);
    if (node.textContent !== translated) {
      node.textContent = translated;
    }
  }

  function findStepRoot(node) {
    return node && node.closest ? node.closest('.step--response') || node.closest('.openassessment') : null;
  }

  function showUploadError(stepRoot, message) {
    if (!stepRoot) {
      return;
    }
    var errorBox = stepRoot.querySelector('.upload__error');
    if (!errorBox) {
      return;
    }
    var content = errorBox.querySelector('.message__content');
    if (content) {
      var paragraph = document.createElement('p');
      paragraph.textContent = message;
      content.replaceChildren(paragraph);
    }
    errorBox.classList.add('has--error');
    var focusTarget = errorBox.querySelector('.message');
    if (focusTarget) {
      focusTarget.focus();
    }
  }

  function applyDefaultFileDescriptions(stepRoot) {
    if (!stepRoot) {
      return;
    }
    stepRoot.querySelectorAll('.file__description').forEach(function (textarea) {
      if (!trim(textarea.value)) {
        textarea.value = DEFAULT_FILE_DESCRIPTION;
      }
    });
  }

  function normalizeUploadedFileDisplay(stepRoot) {
    var scope = stepRoot || document;

    scope.querySelectorAll('a.submission__answer__file.submission--file').forEach(function (link) {
      var text = trim(link.textContent);
      var placeholderMatch = text.match(/^-\s+\((.+)\)$/);
      if (placeholderMatch) {
        link.textContent = placeholderMatch[1];
        return;
      }
      if (text === '-') {
        var href = link.getAttribute('href') || '';
        var hrefName = href.split('/').pop();
        if (hrefName) {
          link.textContent = hrefName;
        }
      }
    });

    scope.querySelectorAll('.submission__file__description__label').forEach(function (label) {
      var text = trim(label.textContent);
      if (text === '-' || text === '-:' || text === '—' || text === '—:') {
        label.style.display = 'none';
      }
    });
  }

  function findUploadButton(stepEl) {
    return stepEl.querySelector('button.file__upload, button.action--upload');
  }

  function findFileInput(stepEl) {
    return stepEl.querySelector(
      'input.submission__answer__upload, input.file--upload, input[type="file"].submission__answer__upload'
    );
  }

  function getMaxFiles(stepEl) {
    var input = findFileInput(stepEl);
    var max = input ? parseInt(input.getAttribute('data-robbo-max-files'), 10) : NaN;
    return max > 0 ? max : null;
  }

  function getSavedFileCount(stepEl) {
    // Same rule as edx-ora2 getSavedFileCount(false): deleted files leave an empty block.
    return Array.prototype.filter.call(
      stepEl.querySelectorAll('.submission__answer__file__block'),
      function (block) { return block.children.length > 0 || trim(block.textContent) !== ''; }
    ).length;
  }

  function isLimitReached(stepEl) {
    var max = getMaxFiles(stepEl);
    return max !== null && getSavedFileCount(stepEl) >= max;
  }

  function updatePickerStatus(stepEl) {
    var input = findFileInput(stepEl);
    var status = stepEl.querySelector('.robbo-ora-file-picker__status');
    if (!input || !status) {
      return;
    }
    var limitReached = isLimitReached(stepEl);
    var text;
    if (limitReached) {
      text = format(gettext('File limit reached ({max}). To add another file, delete an uploaded one.'), {
        max: getMaxFiles(stepEl),
      });
    } else if (input.files && input.files.length === 1) {
      text = input.files[0].name;
    } else if (input.files && input.files.length > 1) {
      text = gettext('%(count)s files selected').replace('%(count)s', String(input.files.length));
    } else {
      text = status.getAttribute('data-robbo-empty-label') || trim(status.textContent);
    }
    status.classList.toggle('is--limit-reached', limitReached);
    status.title = text;
    if (status.textContent !== text) {
      status.textContent = text;
    }
  }

  function syncUploadButtonState(stepRoot) {
    var scope = stepRoot || document;
    var steps = scope.matches && scope.matches('.step--response')
      ? [scope] : scope.querySelectorAll('.step--response');

    Array.prototype.forEach.call(steps, function (stepEl) {
      var input = findFileInput(stepEl);
      var btn = findUploadButton(stepEl);
      var limitReached = isLimitReached(stepEl);
      if (input) {
        if (limitReached && input.files && input.files.length) {
          input.value = '';
        }
        input.disabled = limitReached;
      }
      updatePickerStatus(stepEl);
      if (!btn) {
        return;
      }
      var hasFiles = !!(input && input.files && input.files.length > 0);
      var enabled = hasFiles && !limitReached;
      btn.disabled = !enabled;
      btn.setAttribute('aria-disabled', enabled ? 'false' : 'true');
      btn.classList.toggle('is--disabled', !enabled);
    });
  }

  function translateDescriptionLabels(stepRoot) {
    var scope = stepRoot || document;

    scope.querySelectorAll('.submission__file__description__label').forEach(function (label) {
      var text = trim(label.textContent);
      if (
        text.indexOf('(optional)') !== -1
        || text.indexOf('(необязательно)') !== -1
      ) {
        return;
      }

      var match = text.match(/^(?:Describe|Описание)\s+(.+?)\s+\((?:required|обязательно)\):?$/i);
      if (!match) {
        return;
      }

      var optionalLabel = gettext('Describe {filename} (optional):').replace(
        '{filename}',
        match[1]
      );
      if (label.textContent !== optionalLabel) {
        label.textContent = optionalLabel;
      }
    });
  }

  function translateUploadControls(root) {
    var scope = root || document;

    scope.querySelectorAll('button.file__upload, button.action--upload').forEach(function (btn) {
      if (!btn.classList.contains('file__upload') && !btn.classList.contains('action--upload')) {
        return;
      }
      if (btn.dataset.robboTranslated) {
        return;
      }
      var label = btn.getAttribute('data-robbo-upload-label') || trim(btn.textContent);
      if (
        label === 'Upload file' || label === 'Upload files'
        || label === 'Загрузить файл' || label === 'Загрузить файлы'
      ) {
        btn.setAttribute('data-robbo-upload-label', label);
        var key = label.indexOf('files') !== -1 || label.indexOf('файлы') !== -1
          ? 'Upload files' : 'Upload file';
        setTranslatedText(btn, key);
      }
      btn.dataset.robboTranslated = '1';
    });

    scope.querySelectorAll('button.delete__uploaded__file').forEach(function (btn) {
      var label = trim(btn.textContent);
      if (label === 'Delete File' || label === 'Удалить файл') {
        setTranslatedText(btn, 'Delete File');
      }
    });

    scope.querySelectorAll('.step--response .field > div').forEach(function (div) {
      if (div.dataset.robboTranslated) {
        return;
      }
      var text = div.textContent || '';
      if (text.indexOf('Supported file types:') === 0) {
        var translated = gettext('Supported file types: ') + text.slice('Supported file types:'.length);
        if (div.textContent !== translated) {
          div.textContent = translated;
        }
        div.dataset.robboTranslated = '1';
      }
    });

    translateDescriptionLabels(scope);
  }

  function refreshUploadUi(root) {
    translateUploadControls(root);
    syncUploadButtonState(root);
  }

  var refreshUploadUiQueued = false;

  function scheduleRefreshUploadUi(root) {
    if (refreshUploadUiQueued) {
      return;
    }
    refreshUploadUiQueued = true;
    window.requestAnimationFrame(function () {
      refreshUploadUiQueued = false;
      refreshUploadUi(root);
    });
  }

  function rejectSelection(input, stepRoot, message) {
    showUploadError(stepRoot, message);
    input.value = '';
    var descriptions = stepRoot && stepRoot.querySelector('.files__descriptions');
    if (descriptions) {
      descriptions.replaceChildren();
    }
    return false;
  }

  function validateSelectedFiles(input) {
    var stepRoot = findStepRoot(input);
    if (!input.files || !input.files.length) {
      return true;
    }
    // Per-extension limits ("Larger file sizes" in Studio) win over the global 5 MB default.
    var sizeLimits = null;
    try {
      sizeLimits = JSON.parse(input.getAttribute('data-robbo-size-limits') || 'null');
    } catch (error) {
      sizeLimits = null;
    }
    var maxBytes = window.ROBBO_ORA_MAX_FILE_BYTES;
    for (var i = 0; i < input.files.length; i++) {
      var file = input.files[i];
      var ext = (file.name.split('.').pop() || '').toLowerCase();
      if (sizeLimits && sizeLimits[ext]) {
        if (file.size > sizeLimits[ext] * 1000 * 1000) {
          return rejectSelection(input, stepRoot, format(gettext(
            'The file "{name}" is larger than {mb} MB, the limit for .{ext} files.'
          ), { name: file.name, mb: sizeLimits[ext], ext: ext }));
        }
      } else if (maxBytes && file.size > maxBytes) {
        var maxMb = window.ROBBO_ORA_MAX_FILE_MB || Math.round(maxBytes / (1000 * 1000));
        return rejectSelection(input, stepRoot, gettext(
          'Individual file size must be {max_files_mb}MB or less.'
        ).replace('{max_files_mb}', String(maxMb)));
      }
    }
    var max = stepRoot ? getMaxFiles(stepRoot) : null;
    if (max !== null) {
      var saved = getSavedFileCount(stepRoot);
      var selected = input.files.length;
      if (saved >= max) {
        return rejectSelection(input, stepRoot, format(gettext(
          'You have already uploaded the maximum number of files ({max}). To add another one, delete an uploaded file.'
        ), { max: max }));
      }
      if (saved + selected > max) {
        return rejectSelection(input, stepRoot, format(gettext(
          'Too many files: the limit is {max}. Already uploaded: {saved}, selected: {selected}. Choose no more than {left}.'
        ), { max: max, saved: saved, selected: selected, left: max - saved }));
      }
    }
    // edx-ora2 may still have reported a problem of its own (e.g. unsupported type) — keep it.
    return true;
  }

  function onUploadButtonClick(event) {
    var btn = event.target.closest('button.file__upload, button.action--upload');
    if (!btn) {
      return;
    }
    if (btn.disabled || btn.classList.contains('is--disabled')) {
      event.preventDefault();
      event.stopImmediatePropagation();
      return;
    }
    var stepRoot = findStepRoot(btn);
    applyDefaultFileDescriptions(stepRoot);
  }

  function handleFileInputSelected(input) {
    if (!input) {
      return;
    }
    var stepRoot = findStepRoot(input);
    if (!validateSelectedFiles(input)) {
      syncUploadButtonState(stepRoot);
      return;
    }
    syncUploadButtonState(stepRoot);
    window.setTimeout(function () {
      translateDescriptionLabels(stepRoot);
      syncUploadButtonState(stepRoot);
    }, 0);
  }

  function bindFileInputHandlers(root) {
    var scope = root || document;
    if (scope.robboOraFileInputBound) {
      return;
    }
    scope.robboOraFileInputBound = true;
    // Bubble phase: edx-ora2 binds its change handler on the input itself, so it runs first and
    // our validation has the last word on the error box and the upload button.
    scope.addEventListener('change', onFileInputChange, false);
  }

  function wrapOpenAssessmentBlock() {
    var original = window.OpenAssessmentBlock;
    if (!original || original._robboOraWrapped) {
      return !!original;
    }
    window.OpenAssessmentBlock = function (runtime, element, data) {
      original(runtime, element, data);
      bindFileInputHandlers(element);
      window.setTimeout(function () {
        scheduleRefreshUploadUi(element);
      }, 0);
      window.setTimeout(function () {
        scheduleRefreshUploadUi(element);
      }, 500);
    };
    window.OpenAssessmentBlock._robboOraWrapped = true;
    return true;
  }

  function onFileInputChange(event) {
    var input = event.target;
    if (event.robboOraHandled || !input.matches('input.submission__answer__upload, input.file--upload')) {
      return;
    }
    event.robboOraHandled = true;
    handleFileInputSelected(input);
  }

  function patchSaveFilesDescriptionsPayload(options) {
    var url = options && options.url ? String(options.url) : '';
    if (url.indexOf('save_files_descriptions') === -1 || !options.data) {
      return;
    }
    try {
      var payload = JSON.parse(options.data);
      if (!payload.fileMetadata || !payload.fileMetadata.length) {
        return;
      }
      payload.fileMetadata.forEach(function (entry) {
        if (!trim(entry.description)) {
          entry.description = DEFAULT_FILE_DESCRIPTION;
        }
      });
      options.data = JSON.stringify(payload);
    } catch (error) {
      // Keep the original request if the payload is not JSON.
    }
  }

  function onAjaxSuccess(event, xhr, settings) {
    var url = settings && settings.url ? String(settings.url) : '';
    if (
      url.indexOf('download_url') !== -1
      || url.indexOf('save_files_descriptions') !== -1
      || url.indexOf('remove_uploaded_file') !== -1
    ) {
      scheduleRefreshUploadUi();
    }
    if (url.indexOf('download_url') !== -1) {
      normalizeUploadedFileDisplay();
    }
  }

  function shouldRefreshForNode(node) {
    if (!node || node.nodeType !== 1) {
      return false;
    }
    // Studio: the ORA editor has no learner upload UI; skip its large subtree.
    if (node.closest('#openassessment-editor') || node.id === 'openassessment-editor') {
      return false;
    }
    if (node.matches(
      '.openassessment, .openassessment__steps, .step--response, .submission__upload__files__title, '
      + 'input.submission__answer__upload, input.file--upload, button.file__upload, button.action--upload, '
      + 'button.delete__uploaded__file, .submission__answer__file__block, .submission__answer__files, '
      + '.files__descriptions, .submission__file__description__label'
    )) {
      return true;
    }
    return !!(node.querySelector && node.querySelector(
      '.step--response, button.file__upload, button.action--upload, button.delete__uploaded__file, '
      + '.file__description, .submission__file__description__label, input.submission__answer__upload, '
      + 'input.file--upload'
    ));
  }

  var booted = false;
  var domObserver = null;

  function boot() {
    if (booted) {
      refreshUploadUi();
      return;
    }
    booted = true;

    document.addEventListener('click', onUploadButtonClick, true);
    bindFileInputHandlers(document);

    if (typeof window.jQuery !== 'undefined') {
      window.jQuery.ajaxPrefilter(patchSaveFilesDescriptionsPayload);
      window.jQuery(document).ajaxSuccess(onAjaxSuccess);
      // Failed uploads reset the input via jQuery .val(null) without a change event.
      // Only XBlock handler calls matter; Studio fires plenty of unrelated requests.
      window.jQuery(document).ajaxComplete(function (_event, _xhr, settings) {
        if (settings && settings.url && String(settings.url).indexOf('handler') !== -1) {
          scheduleRefreshUploadUi();
        }
      });
    }

    wrapOpenAssessmentBlock();
    var wrapAttempts = 0;
    var wrapTimer = window.setInterval(function () {
      if (wrapOpenAssessmentBlock() || ++wrapAttempts > 80) {
        window.clearInterval(wrapTimer);
      }
    }, 250);

    refreshUploadUi();

    if (typeof MutationObserver !== 'undefined' && !domObserver) {
      domObserver = new MutationObserver(function (mutations) {
        var shouldRefresh = mutations.some(function (mutation) {
          if (mutation.type !== 'childList' || !mutation.addedNodes.length) {
            return false;
          }
          return Array.prototype.some.call(mutation.addedNodes, shouldRefreshForNode);
        });
        if (shouldRefresh) {
          scheduleRefreshUploadUi();
          mutations.forEach(function (mutation) {
            Array.prototype.forEach.call(mutation.addedNodes, function (node) {
              if (shouldRefreshForNode(node)) {
                syncUploadButtonState(node.nodeType === 1 ? node : document);
              }
            });
          });
        }
      });
      domObserver.observe(document.documentElement, { childList: true, subtree: true });
    }

    var pollAttempts = 0;
    var pollTimer = window.setInterval(function () {
      refreshUploadUi();
      pollAttempts += 1;
      if (pollAttempts > 40 || document.querySelector('button.file__upload, button.action--upload')) {
        window.clearInterval(pollTimer);
      }
    }, 250);
  }

  window.RobboOraUploadPatch = {
    installed: true,
    refresh: refreshUploadUi,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
}());
