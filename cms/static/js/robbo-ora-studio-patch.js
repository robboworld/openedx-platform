/**
 * Robbo patch: include max_files_count in ORA Studio editor save requests.
 */
(function () {
  'use strict';

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

  function patchServerClient() {
    if (!window.ServerClient || !window.ServerClient.prototype) {
      return false;
    }
    var proto = window.ServerClient.prototype;
    if (proto._robboMaxFilesPatched) {
      return true;
    }
    var original = proto.updateEditorContext;
    proto.updateEditorContext = function (options) {
      var maxFiles = readMaxFilesCount();
      var self = this;
      var url = this.url('update_editor_context');
      var payload = {
        prompts: options.prompts,
        prompts_type: options.prompts_type,
        feedback_prompt: options.feedbackPrompt,
        feedback_default_text: options.feedback_default_text,
        title: options.title,
        submission_start: options.submissionStart,
        submission_due: options.submissionDue,
        date_config_type: options.dateConfigType,
        criteria: options.criteria,
        assessments: options.assessments,
        editor_assessments_order: options.editorAssessmentsOrder,
        text_response: options.textResponse,
        text_response_editor: options.textResponseEditor,
        file_upload_response: options.fileUploadResponse,
        file_upload_type: options.fileUploadType,
        white_listed_file_types: options.fileTypeWhiteList,
        allow_multiple_files: options.multipleFilesEnabled,
        allow_latex: options.latexEnabled,
        leaderboard_show: options.leaderboardNum,
        teams_enabled: options.teamsEnabled,
        selected_teamset_id: options.selectedTeamsetId,
        show_rubric_during_response: options.showRubricDuringResponse,
        allow_learner_resubmissions: options.allowLearnerResubmissions,
        resubmissions_grace_period: options.resubmissionsGracePeriod,
      };
      if (maxFiles !== null) {
        payload.max_files_count = maxFiles;
      }
      return $.Deferred(function (defer) {
        $.ajax({
          type: 'POST',
          url: url,
          data: JSON.stringify(payload),
          contentType: 'application/json; charset=UTF-8',
        }).done(function (data) {
          if (data.success) {
            defer.resolve();
          } else {
            defer.reject(data.msg);
          }
        }).fail(function () {
          defer.reject(
            (window.gettext && gettext('This problem could not be saved.'))
            || 'This problem could not be saved.'
          );
        });
      }).promise();
    };
    proto._robboMaxFilesPatched = true;
    return true;
  }

  var LABEL_MAP = {
    None: 'Нет',
    Required: 'Обязательно',
    Optional: 'Необязательно',
  };

  function localizeSelectLabels(root) {
    var container = root || document.getElementById('openassessment-editor');
    if (!container) {
      return;
    }
    container.querySelectorAll('select option').forEach(function (option) {
      var text = option.textContent.trim();
      if (LABEL_MAP[text]) {
        option.textContent = LABEL_MAP[text];
      }
    });
  }

  function watchEditorLabels() {
    var editor = document.getElementById('openassessment-editor');
    if (!editor || editor._robboLabelObserver) {
      return;
    }
    localizeSelectLabels(editor);
    var observer = new MutationObserver(function () {
      localizeSelectLabels(editor);
    });
    observer.observe(editor, { childList: true, subtree: true });
    editor._robboLabelObserver = observer;
  }

  var attempts = 0;
  var timer = setInterval(function () {
    attempts += 1;
    patchServerClient();
    watchEditorLabels();
    if (attempts > 50) {
      clearInterval(timer);
    }
  }, 100);
}());
