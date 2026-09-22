/**
 * Robbo ORA LMS: upload size limit, i18n fixes, and upload UI hints.
 */
(function () {
  'use strict';

  function gettext(msg) {
    if (typeof django !== 'undefined' && django.gettext) {
      return django.gettext(msg);
    }
    return msg;
  }

  function applyUploadLimit() {
    if (!window.OpenAssessment || !window.OpenAssessment.ResponseView) {
      return false;
    }

    var ResponseView = window.OpenAssessment.ResponseView;
    if (window.ROBBO_ORA_MAX_FILE_BYTES) {
      ResponseView.MAX_FILE_SIZE = window.ROBBO_ORA_MAX_FILE_BYTES;
      ResponseView.MAX_FILES_MB = window.ROBBO_ORA_MAX_FILE_MB;
    }

    var proto = ResponseView.prototype;
    if (!proto._robboUploadPatched) {
      var originalUpdateDescriptions = proto.updateFilesDescriptionsFields;
      proto.updateFilesDescriptionsFields = function (files, descriptions, uploadType) {
        originalUpdateDescriptions.call(this, files, descriptions, uploadType);
        $(this.element).find('.files__descriptions .submission__file__description__label').each(function (index) {
          var name = files[index] && files[index].name ? files[index].name : '';
          $(this).text(
            gettext('Describe {filename} (required):').replace('{filename}', name)
          );
        });
      };
      var originalInstallHandlers = proto.installHandlers;
      proto.installHandlers = function () {
        originalInstallHandlers.call(this);
        refreshUploadUi();
      };
      proto._robboUploadPatched = true;
    }

    if (window.OpenAssessment.BaseView && !OpenAssessment.BaseView.prototype._robboUploadErrorPatched) {
      var originalToggleError = OpenAssessment.BaseView.prototype.toggleActionError;
      OpenAssessment.BaseView.prototype.toggleActionError = function (type, message) {
        if (type === 'upload' && (!message || message === 'error')) {
          message = gettext(
            'Upload failed. Check that the file is within the size limit and try again.'
          );
        } else if (message) {
          message = gettext(message);
        }
        return originalToggleError.call(this, type, message);
      };
      OpenAssessment.BaseView.prototype._robboUploadErrorPatched = true;
    }

    return true;
  }

  function bindFilePickerTriggers() {
    document.querySelectorAll('[data-robbo-file-trigger]').forEach(function (button) {
      if (button.dataset.robboTriggerBound) {
        return;
      }
      button.dataset.robboTriggerBound = '1';
      button.addEventListener('click', function () {
        var inputId = button.getAttribute('data-robbo-file-trigger');
        var input = inputId && document.getElementById(inputId);
        if (input) {
          input.click();
        }
      });
    });
  }

  function bindFilePickerStatus(input) {
    if (input.dataset.robboStatusBound) {
      return;
    }
    input.dataset.robboStatusBound = '1';
    input.addEventListener('change', function () {
      var picker = input.closest('.robbo-ora-file-picker');
      var status = picker && picker.querySelector('.robbo-ora-file-picker__status');
      if (!status) {
        return;
      }
      var emptyLabel = status.getAttribute('data-robbo-empty-label')
        || gettext(input.hasAttribute('multiple') ? 'No files chosen' : 'No file chosen');
      if (!input.files || input.files.length === 0) {
        status.textContent = emptyLabel;
        return;
      }
      if (input.files.length === 1) {
        status.textContent = input.files[0].name;
        return;
      }
      status.textContent = gettext('%(count)s files selected').replace(
        '%(count)s',
        String(input.files.length)
      );
    });
  }

  function enhanceNativeFileInputs() {
    document.querySelectorAll('input.submission__answer__upload.file--upload').forEach(function (input) {
      if (input.closest('.robbo-ora-file-picker')) {
        bindFilePickerStatus(input);
        return;
      }
      if (input.dataset.robboFileEnhanced) {
        return;
      }
      input.dataset.robboFileEnhanced = '1';

      var multiple = input.hasAttribute('multiple');
      var chooseLabel = gettext(multiple ? 'Choose files' : 'Choose file');
      var emptyLabel = gettext(multiple ? 'No files chosen' : 'No file chosen');

      var wrap = document.createElement('div');
      wrap.className = 'robbo-ora-file-picker';
      input.parentNode.insertBefore(wrap, input);
      wrap.appendChild(input);
      input.classList.add('robbo-ora-file-picker__input');

      if (!input.id) {
        input.id = 'robbo_ora_file_' + Math.random().toString(36).slice(2, 10);
      }

      var pickerButton = document.createElement('label');
      pickerButton.className = 'robbo-ora-file-picker__button action action--upload';
      pickerButton.htmlFor = input.id;
      pickerButton.setAttribute('for', input.id);
      pickerButton.textContent = chooseLabel;
      wrap.appendChild(pickerButton);

      var status = document.createElement('span');
      status.className = 'robbo-ora-file-picker__status';
      status.textContent = emptyLabel;
      wrap.appendChild(status);

      status.setAttribute('data-robbo-empty-label', emptyLabel);
      bindFilePickerStatus(input);
    });
  }

  function setTranslatedText(node, msgid) {
    var translated = gettext(msgid);
    if (node.textContent !== translated) {
      node.textContent = translated;
    }
  }

  function translateUploadControls() {
    document.querySelectorAll('button.file__upload.action--upload').forEach(function (btn) {
      if (btn.dataset.robboTranslated) {
        return;
      }
      var label = btn.getAttribute('data-robbo-upload-label') || btn.textContent.trim();
      if (label === 'Upload file' || label === 'Upload files' || label === 'Загрузить файл' || label === 'Загрузить файлы') {
        btn.setAttribute('data-robbo-upload-label', label);
        var key = label.indexOf('files') !== -1 || label.indexOf('файлы') !== -1 ? 'Upload files' : 'Upload file';
        setTranslatedText(btn, key);
        btn.dataset.robboTranslated = '1';
      }
    });

    document.querySelectorAll('button.delete__uploaded__file').forEach(function (btn) {
      if (btn.dataset.robboTranslated) {
        return;
      }
      setTranslatedText(btn, 'Delete File');
      btn.dataset.robboTranslated = '1';
    });

    document.querySelectorAll('.step--response .field > div').forEach(function (div) {
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

    document.querySelectorAll('label.sr[for^="submission_answer_upload"]').forEach(function (label) {
      if (label.dataset.robboTranslated) {
        return;
      }
      var original = label.getAttribute('data-robbo-upload-label') || label.textContent.trim();
      label.setAttribute('data-robbo-upload-label', original);
      setTranslatedText(label, original);
      label.dataset.robboTranslated = '1';
    });

    document.querySelectorAll('.submission__answer__part__text__title').forEach(function (title) {
      if (title.dataset.robboTranslated) {
        return;
      }
      var original = title.getAttribute('data-robbo-upload-label') || title.textContent.trim();
      title.setAttribute('data-robbo-upload-label', original);
      setTranslatedText(title, original);
      title.dataset.robboTranslated = '1';
    });
  }

  function injectUploadLimitHint() {
    if (!window.ROBBO_ORA_MAX_FILE_MB) {
      return;
    }
    var hintText = gettext('Maximum file size: %(max_mb)s MB.').replace(
      '%(max_mb)s',
      String(window.ROBBO_ORA_MAX_FILE_MB)
    );
    document.querySelectorAll('.submission__upload__files__title').forEach(function (title) {
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
      if (hint.textContent !== hintText) {
        hint.textContent = hintText;
      }
    });
  }

  var refreshUploadUiQueued = false;
  var refreshUploadUiRunning = false;

  function refreshUploadUi() {
    if (refreshUploadUiRunning) {
      return;
    }
    refreshUploadUiRunning = true;
    try {
      enhanceNativeFileInputs();
      bindFilePickerTriggers();
      injectUploadLimitHint();
      translateUploadControls();
    } finally {
      refreshUploadUiRunning = false;
    }
  }

  function scheduleRefreshUploadUi() {
    if (refreshUploadUiQueued) {
      return;
    }
    refreshUploadUiQueued = true;
    window.requestAnimationFrame(function () {
      refreshUploadUiQueued = false;
      refreshUploadUi();
    });
  }

  function boot() {
    if (!applyUploadLimit()) {
      var tries = 0;
      var timer = window.setInterval(function () {
        if (applyUploadLimit() || ++tries > 50) {
          window.clearInterval(timer);
        }
      }, 100);
    }
    refreshUploadUi();
    if (typeof MutationObserver !== 'undefined') {
      var observer = new MutationObserver(function (mutations) {
        var shouldRefresh = mutations.some(function (mutation) {
          if (mutation.type !== 'childList') {
            return false;
          }
          var nodes = Array.prototype.slice.call(mutation.addedNodes || []);
          return nodes.some(function (node) {
            return node.nodeType === 1 && (
              node.matches && (
                node.matches('.step--response, .submission__upload__files__title, input.submission__answer__upload')
                || (node.querySelector && node.querySelector('.step--response, input.submission__answer__upload'))
              )
            );
          });
        });
        if (shouldRefresh) {
          scheduleRefreshUploadUi();
        }
      });
      var root = document.querySelector('.openassessment__steps');
      if (root) {
        observer.observe(root, { childList: true, subtree: true });
      }
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
}());
