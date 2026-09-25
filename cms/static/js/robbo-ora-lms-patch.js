/**
 * Robbo ORA LMS: upload limit, i18n, optional file descriptions.
 * DOM/event-based — does not rely on OpenAssessment.ResponseView (removed in newer edx-ora2).
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
  };

  function gettext(msg) {
    if (typeof django !== 'undefined' && django.gettext) {
      var translated = django.gettext(msg);
      if (translated && translated !== msg) {
        return translated;
      }
    }
    return FALLBACK_CATALOG[msg] || msg;
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
    return node && node.closest ? node.closest('.step--response, .openassessment') : null;
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
      content.innerHTML = '<p>' + message + '</p>';
    }
    errorBox.classList.add('has--error');
    var focusTarget = errorBox.querySelector('.message');
    if (focusTarget) {
      focusTarget.focus();
    }
  }

  function clearUploadError(stepRoot) {
    if (!stepRoot) {
      return;
    }
    var errorBox = stepRoot.querySelector('.upload__error');
    if (!errorBox) {
      return;
    }
    var content = errorBox.querySelector('.message__content');
    if (content) {
      content.innerHTML = '';
    }
    errorBox.classList.remove('has--error');
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

  function applyUploadButtonPresentation(btn, enabled) {
    btn.classList.add('robbo-ora-upload-btn');
    btn.classList.toggle('robbo-ora-upload-btn--ready', enabled);
    btn.classList.toggle('robbo-ora-upload-btn--disabled', !enabled);

    btn.style.setProperty('display', 'inline-flex', 'important');
    btn.style.setProperty('align-items', 'center', 'important');
    btn.style.setProperty('justify-content', 'center', 'important');
    btn.style.setProperty('box-sizing', 'border-box', 'important');
    btn.style.setProperty('margin-top', '0.9rem', 'important');
    btn.style.setProperty('padding', '1.2rem 2.7rem', 'important');
    btn.style.setProperty('min-height', '3.6rem', 'important');
    btn.style.setProperty('height', 'auto', 'important');
    btn.style.setProperty('min-width', '0', 'important');
    btn.style.setProperty('width', 'auto', 'important');
    btn.style.setProperty('max-width', 'none', 'important');
    btn.style.setProperty('line-height', '1.3', 'important');
    btn.style.setProperty('text-align', 'center', 'important');
    btn.style.setProperty('font-size', '1.35rem', 'important');
    btn.style.setProperty('font-weight', '600', 'important');
    btn.style.setProperty('border-radius', '0', 'important');
    btn.style.setProperty('float', 'right', 'important');
    btn.style.setProperty('clear', 'right', 'important');
    btn.style.setProperty('margin-left', 'auto', 'important');
    btn.style.setProperty('margin-right', '0', 'important');
    btn.style.removeProperty('background');
    btn.style.removeProperty('border');
    btn.style.removeProperty('border-color');
    btn.style.removeProperty('box-shadow');
    btn.style.removeProperty('transform');
  }

  function syncUploadButtonState(stepRoot) {
    var scope = stepRoot || document;

    scope.querySelectorAll('.step--response').forEach(function (stepEl) {
      var input = findFileInput(stepEl);
      var btn = findUploadButton(stepEl);
      if (!btn) {
        return;
      }
      var hasFiles = !!(input && input.files && input.files.length > 0);
      btn.disabled = !hasFiles;
      btn.setAttribute('aria-disabled', hasFiles ? 'false' : 'true');
      btn.classList.toggle('is--disabled', !hasFiles);
      applyUploadButtonPresentation(btn, hasFiles);
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

  function injectUploadLimitHint(root) {
    if (!window.ROBBO_ORA_MAX_FILE_MB) {
      return;
    }
    var scope = root || document;
    var hintText = gettext('Maximum file size: %(max_mb)s MB.').replace(
      '%(max_mb)s',
      String(window.ROBBO_ORA_MAX_FILE_MB)
    );
    scope.querySelectorAll('.submission__upload__files__title').forEach(function (title) {
      var parent = title.parentNode;
      if (!parent) {
        return;
      }
      var hint = parent.querySelector('.robbo-ora-upload-limit');
      if (!hint) {
        hint = document.createElement('p');
        hint.className = 'robbo-ora-upload-limit';
        parent.insertBefore(hint, title.nextSibling);
      }
      hint.style.setProperty('font-size', '1.125rem', 'important');
      hint.style.setProperty('line-height', '1.4', 'important');
      if (hint.textContent !== hintText) {
        hint.textContent = hintText;
      }
    });
  }

  function refreshUploadUi(root) {
    injectUploadLimitHint(root);
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

  function validateSelectedFiles(input) {
    var maxBytes = window.ROBBO_ORA_MAX_FILE_BYTES;
    if (!maxBytes || !input.files || !input.files.length) {
      return true;
    }
    var stepRoot = findStepRoot(input);
    for (var i = 0; i < input.files.length; i++) {
      if (input.files[i].size > maxBytes) {
        var maxMb = window.ROBBO_ORA_MAX_FILE_MB || Math.round(maxBytes / (1000 * 1000));
        showUploadError(
          stepRoot,
          gettext('Individual file size must be {max_files_mb}MB or less.').replace(
            '{max_files_mb}',
            String(maxMb)
          )
        );
        input.value = '';
        return false;
      }
    }
    clearUploadError(stepRoot);
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
    if (!validateSelectedFiles(input)) {
      syncUploadButtonState(findStepRoot(input));
      return;
    }
    var stepRoot = findStepRoot(input);
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
    scope.addEventListener('change', onFileInputChange, true);
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
    if (!input.matches('input.submission__answer__upload, input.file--upload, input[type="file"]')) {
      return;
    }
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
    if (url.indexOf('download_url') !== -1 || url.indexOf('save_files_descriptions') !== -1) {
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
      window.jQuery(document).on(
        'change.robboOraUpload',
        'input.submission__answer__upload, input.file--upload, input[type=file]',
        function () {
          handleFileInputSelected(this);
        }
      );
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
