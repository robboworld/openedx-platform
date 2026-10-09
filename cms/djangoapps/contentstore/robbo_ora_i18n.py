# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# ORA status strings use XBlockI18nService; DarkLang may leave LocaleMiddleware on en.

"""Russian overrides for edx-ora2 strings rendered via XBlockI18nService."""

from django.conf import settings
from django.utils import translation

from xmodule.course_metadata_utils import is_russian_language


def effective_ora_ui_language():
    """
    Language for ORA Studio/LMS UI strings.

    Prefer ``request.LANGUAGE_CODE`` (LocaleMiddleware + Robbo language middleware)
    over ``translation.get_language()`` so Authoring iframe matches the HTTP request.
    """
    try:
        from crum import get_current_request

        request = get_current_request()
        if request is not None:
            lang = getattr(request, 'LANGUAGE_CODE', None)
            if lang:
                return str(lang)
    except Exception:  # pylint: disable=broad-except
        pass
    lang = translation.get_language()
    if lang:
        return str(lang)
    forced = getattr(settings, 'ROBBO_FORCED_LANGUAGE', None)
    if forced:
        return str(forced)
    return str(getattr(settings, 'LANGUAGE_CODE', 'en'))


def robbo_ora_russian_active():
    """True when the active ORA UI language is Russian."""
    return is_russian_language(effective_ora_ui_language())


ROBBO_ORA_RU_STRINGS = {
    # Response / draft status (server render + XBlock translate)
    "Status of Your Response": "Статус вашего ответа",
    "Response not started.": "Ответ не начат.",
    "Draft saved!": "Черновик сохранён!",
    "Not Started": "Не начато",
    "Not Completed": "Не завершено",
    "Not Available": "Недоступно",
    "Waiting for Assessments": "Ожидание оценок",
    "Incomplete": "Не завершено",
    "In Progress": "Выполняется",
    "Instructions Unavailable": "Инструкции недоступны",
    "Error": "Ошибка",
    "Required": "Обязательно",
    "Optional": "Необязательно",
    "None": "Нет",
    "Peer Assessment Only": "Только взаимная оценка",
    "Maximum File Uploads": "Максимум загружаемых файлов",
    "Specify the maximum number of files a learner can upload. Valid numbers are 1 to 20.": (
        "Укажите максимальное число файлов, которые может загрузить учащийся. Допустимые значения: от 1 до 20."
    ),
    "Maximum size per file: %(max_mb)s MB.": "Максимальный размер одного файла: %(max_mb)s МБ.",
    (
        'By default each file may be up to %(max_mb)s MB. Turn on "Larger file sizes" to set a limit '
        'for each file type (up to %(cap_mb)s MB).'
    ): (
        "По умолчанию размер одного файла — до %(max_mb)s МБ. Включите «Увеличенный размер файлов», "
        "чтобы задать ограничение для каждого типа файлов (до %(cap_mb)s МБ)."
    ),
    "Larger file sizes": "Увеличенный размер файлов",
    "Maximum file size by type": "Максимальный размер файла по типам",
    "File type": "Тип файла",
    "Size, MB": "Вес, МБ",
    "Default is %(default_mb)s MB, maximum is %(cap_mb)s MB per file.": (
        "По умолчанию — %(default_mb)s МБ, максимум — %(cap_mb)s МБ на файл."
    ),
    "Select file types above to set their size limits.": "Выберите типы файлов выше, чтобы задать для них ограничения.",
    "Maximum file size:": "Максимальный размер файла:",
    "%(ext)s — up to %(mb)s MB": "%(ext)s — до %(mb)s МБ",
    "Learners must enter a short description for each file before uploading. This requirement is built into Open Response Assessment and cannot be turned off in these settings.": (
        "Перед загрузкой учащийся должен указать краткое описание каждого файла. Это требование встроено "
        "в задание с развёрнутым ответом и не отключается в этих настройках."
    ),
    "Learners may leave file descriptions empty; a dash is saved when no description is provided.": (
        "Описание файла можно не заполнять — при пустом поле сохранится «-»."
    ),
    "File Uploads Response": "Загрузка файлов в ответе",
    "Specify whether learners are able to upload files as a part of their response.": (
        "Укажите, могут ли учащиеся загружать файлы как часть ответа."
    ),
    "Allow Multiple Files": "Разрешить несколько файлов",
    (
        "Specify whether learners can upload more than one file. This has no effect if File Uploads Response "
        "is set to None. This is automatically set to True for Team Assignments. "
    ): (
        "Укажите, могут ли учащиеся загрузить более одного файла. Не действует, если загрузка файлов отключена. "
        "Для командных заданий всегда включено автоматически. "
    ),
    "File Upload Types": "Типы загружаемых файлов",
    "PDF or Image Files": "PDF или изображения",
    "Image Files": "Изображения",
    "Custom File Types": "Пользовательские типы файлов",
    "File Types": "Типы файлов",
    "False": "Нет",
    "True": "Да",
    "Cancelled": "Отменено",
    "Complete": "Завершено",
    "Completed": "Завершено",
    "Your Response": "Ваш ответ",
    "Your Grade": "Ваша оценка",
    "Status": "Статус",
    # Staff assessment step
    "Staff Grade": "Оценка персоналом",
    "Staff Assessment": "Оценка персоналом",
    "Waiting for a Staff Grade": "Ожидание оценки персоналом",
    "Check back later to see if a course staff member has assessed "
    "your response. You will receive your grade after the assessment "
    "is complete.": (
        "Загляните позже: возможно, сотрудник курса уже оценит ваш ответ. "
        "Оценка появится после завершения проверки."
    ),
    "You Must Complete the Steps Above to View Your Grade": (
        "Завершите шаги выше, чтобы увидеть оценку"
    ),
    "Although a course staff member has assessed your response, "
    "you will receive your grade only after you have completed "
    "all the required steps of this problem.": (
        "Сотрудник курса уже оценил ваш ответ, но оценка появится только после "
        "выполнения всех обязательных шагов задания."
    ),
    # Grade / peer status
    "Waiting for peer reviews": "Ожидание взаимных оценок",
    "The grade for this problem is determined by your Staff Grade.": (
        "Итоговая оценка за это задание определяется оценкой персонала."
    ),
    "The grade for this problem is determined by your Self Assessment.": (
        "Итоговая оценка за это задание определяется вашей самооценкой."
    ),
    "The grade for this problem is determined by the median score of your Peer Assessments.": (
        "Итоговая оценка за это задание определяется медианой ваших взаимных оценок."
    ),
    "You have not yet received all necessary peer reviews to determine your final grade.": (
        "Вы ещё не получили все необходимые взаимные оценки для итоговой оценки."
    ),
    "You have completed your steps in the assignment, but some assessments still need to be done on your response. When the assessments of your response are complete, you will see feedback from everyone who assessed your response, and you will receive your final grade.": (
        "Вы выполнили свои шаги, но по вашему ответу ещё нужны оценки. "
        "Когда проверка завершится, вы увидите отзывы оценивших и получите итоговую оценку."
    ),
    "Staff Comments": "Комментарии персонала",
    "Peer Mean Grade": "Средняя взаимная оценка",
    "Peer Median Grade": "Медианная взаимная оценка",
    "Self Assessment Grade": "Оценка по самооценке",
    "Your Self Assessment": "Ваша самооценка",
    "Your Comments": "Ваши комментарии",
    "Peer Assessment": "Взаимная оценка",
    "Self Assessment": "Самооценка",
    "Learner Training": "Обучение оцениванию",
    "Assess Peers": "Оценить однокурсников",
    "Assess Your Response": "Оценить свой ответ",
    "Learn to Assess Responses": "Научиться оценивать ответы",
    "The submission is waiting for assessments.": "Ответ ожидает оценок.",
    "An unexpected error occurred.": "Произошла непредвиденная ошибка.",
    # File upload UI (server-rendered templates)
    "(Required)": "(обязательно)",
    "(Optional)": "(необязательно)",
    "File Uploads ": "Загрузка файлов ",
    "We could not upload files": "Не удалось загрузить файлы",
    "We could not delete files": "Не удалось удалить файлы",
    "Select one or more files to upload for this submission.": (
        "Выберите один или несколько файлов для этой отправки."
    ),
    "Select a file to upload for this submission.": (
        "Выберите файл для этой отправки."
    ),
    "Supported file types: ": "Поддерживаемые типы файлов: ",
    "Upload files": "Загрузить файлы",
    "Upload file": "Загрузить файл",
    "Choose file": "Выбрать файл",
    "Choose files": "Выбрать файлы",
    "No file chosen": "Файл не выбран",
    "No files chosen": "Файлы не выбраны",
    "%(count)s files selected": "Выбрано файлов: %(count)s",
    "Files that were uploaded by you:": "Файлы, загруженные вами:",
    "Files that were uploaded by your teammates:": "Файлы, загруженные участниками вашей команды:",
    "Delete File": "Удалить файл",
    "Maximum file size: %(max_mb)s MB.": "Максимальный размер файла: %(max_mb)s МБ.",
    "Maximum number of files: %(max_files)s.": "Максимальное количество файлов: %(max_files)s.",
    "View the files associated with this submission:": "Файлы, прикреплённые к этой отправке:",
    (
        "Caution: These files were uploaded by another course learner and have not been verified, "
        "screened, approved, reviewed, or endorsed by the site administrator. If you access the files, "
        "you do so at your own risk.)"
    ): (
        "Внимание: эти файлы загрузил другой учащийся; они не проверялись и не одобрялись администрацией "
        "площадки. Вы открываете их на свой риск.)"
    ),
}


class _RobboOraTranslatorWrapper:
    """Wrap XBlock gettext catalog with Robbo ORA Russian overrides."""

    def __init__(self, inner):
        self._inner = inner

    def _translate(self, msgid):
        if not robbo_ora_russian_active():
            if hasattr(self._inner, 'gettext'):
                return self._inner.gettext(msgid)
            return self._inner.ugettext(msgid)
        translated = get_robbo_ora_runtime_catalog().get(msgid)
        if translated is not None:
            return translated
        if hasattr(self._inner, 'gettext'):
            return self._inner.gettext(msgid)
        return self._inner.ugettext(msgid)

    def gettext(self, msgid):
        return self._translate(msgid)

    def ugettext(self, msgid):
        return self._translate(msgid)

    def __getattr__(self, name):
        return getattr(self._inner, name)


def patch_ora_xblock_i18n():
    """Wrap XBlockI18nService translators with ORA Russian overrides."""
    from xmodule.modulestore.django import XBlockI18nService

    if getattr(XBlockI18nService, '_robbo_ora_i18n_patched', False):
        return

    original_init = XBlockI18nService.__init__

    def patched_init(self, block=None):
        original_init(self, block)
        if not isinstance(self.translator, _RobboOraTranslatorWrapper):
            self.translator = _RobboOraTranslatorWrapper(self.translator)

    XBlockI18nService.__init__ = patched_init
    XBlockI18nService._robbo_ora_i18n_patched = True


# JS gettext() in ORA iframe (djangojs.js may be en or missing entries).
ROBBO_ORA_JS_CATALOG = {
    "This component has validation issues.": "В этом компоненте есть ошибки.",
    "This unit has validation issues.": "В этом блоке есть ошибки.",
    "Saving draft": "Сохранение черновика",
    "Saving draft...": "Сохранение черновика...",
    "Draft saved!": "Черновик сохранён!",
    "Error": "Ошибка",
    "Response not started.": "Ответ не начат.",
    "In Progress": "Выполняется",
    "Not Started": "Не начато",
    "Not Completed": "Не завершено",
    "Please check your internet connection.": "Проверьте подключение к интернету.",
    "Please provide a response.": "Введите ответ.",
    "Please upload a file.": "Загрузите файл.",
    "No files selected for upload.": "Файлы для загрузки не выбраны.",
    "Choose file": "Выбрать файл",
    "Choose files": "Выбрать файлы",
    "No file chosen": "Файл не выбран",
    "No files chosen": "Файлы не выбраны",
    "%(count)s files selected": "Выбрано файлов: %(count)s",
    "Upload files": "Загрузить файлы",
    "Upload file": "Загрузить файл",
    "Supported file types: ": "Поддерживаемые типы файлов: ",
    "Confirm Submit Response": "Подтвердите отправку ответа",
    (
        "You're about to submit your response for this assignment. After you submit this response, "
        "you may have a limited time to resubmit before your submission is graded."
    ): (
        "Вы собираетесь отправить ответ на это задание. После отправки у вас может остаться "
        "ограниченное время на повторную отправку до начала оценивания."
    ),
    (
        "You're about to submit your response for this assignment. After you submit this response, "
        "you can't change it or submit a new response."
    ): (
        "Вы собираетесь отправить ответ на это задание. После отправки вы не сможете изменить его "
        "или отправить новый ответ."
    ),
    "There is still file upload in progress. Please wait until it is finished.": (
        "Файл ещё загружается. Дождитесь завершения загрузки."
    ),
    "Cannot submit empty response even everything is optional.": (
        "Нельзя отправить пустой ответ, даже если все поля необязательны."
    ),
    "Please provide a description for each file you are uploading.": (
        "Укажите описание для каждого загружаемого файла."
    ),
    "Confirm Delete Uploaded File": "Подтвердите удаление загруженного файла",
    "Refresh": "Обновить",
    "Save Unsuccessful": "Не удалось сохранить",
    "Please wait": "Подождите",
    "Submit your assessment and review another response": (
        "Отправить оценку и проверить следующий ответ"
    ),
    "Submit your assessment and move to next step": (
        "Отправить оценку и перейти к следующему шагу"
    ),
    "Staff": "Персонал",
    "Peer": "Однокурсник",
    "Self": "Самооценка",
    "Training": "Обучение",
    "Waiting": "Ожидание",
    "Assessment": "Оценка",
    "Assessments": "Оценки",
    "Final Grade Received": "Итоговая оценка получена",
    "Staff assessment": "Оценка персоналом",
    "Grade Status": "Статус оценки",
    "Staff Grader": "Оценивание персоналом",
    "View and grade responses": "Просмотр и оценка ответов",
    "If you leave this page without saving or submitting your response, you will lose any work you have done on the response.": (
        "Если вы покинете страницу без сохранения или отправки ответа, введённый текст будет потерян."
    ),
    # File upload UI (client-side). ORA builds labels from gettext('Describe ')+name+gettext('(required):');
    # we remap "(required):" to optional because file descriptions are not required for Robbo.
    "Describe {filename} (required):": "Описание «{filename}» (необязательно):",
    "Describe {filename} (optional):": "Описание «{filename}» (необязательно):",
    "Describe ": "Описание ",
    "(required):": "(необязательно):",
    "(optional):": "(необязательно):",
    "Thumbnail view of ": "Миниатюра ",
    "Individual file size must be {max_files_mb}MB or less.": (
        "Размер каждого файла не должен превышать {max_files_mb} МБ."
    ),
    (
        "File upload failed: unsupported file type. "
        "Only the supported file types can be uploaded. "
        "If you have questions, please reach out to the course team."
    ): (
        "Не удалось загрузить файл: неподдерживаемый тип. Можно загружать только разрешённые типы файлов. "
        "По вопросам обратитесь к команде курса."
    ),
    "The maximum number files that can be saved is ": "Максимальное число сохраняемых файлов: ",
    "Delete File": "Удалить файл",
    "Maximum file size: %(max_mb)s MB.": "Максимальный размер файла: %(max_mb)s МБ.",
    "Upload failed. Check that the file is within the size limit and try again.": (
        "Не удалось загрузить файл. Проверьте размер файла и попробуйте снова."
    ),
    "Are you sure you want to delete the following file? It cannot be restored.\nFile: ": (
        "Удалить этот файл? Восстановить его будет нельзя.\nФайл: "
    ),
    "Your file has been deleted or path has been changed: ": "Файл удалён или путь изменён: ",
    "Too many files: the limit is {max}. Already uploaded: {saved}, selected: {selected}. Choose no more than {left}.": (
        "Слишком много файлов: можно прикрепить не более {max}. Уже загружено: {saved}, выбрано: {selected}. "
        "Выберите не больше {left}."
    ),
    "You have already uploaded the maximum number of files ({max}). To add another one, delete an uploaded file.": (
        "Уже загружено максимальное количество файлов ({max}). Чтобы добавить новый, удалите один из загруженных."
    ),
    'The file "{name}" is larger than {mb} MB, the limit for .{ext} files.': (
        "Файл «{name}» больше {mb} МБ — это ограничение для файлов .{ext}."
    ),
    "File limit reached ({max}). To add another file, delete an uploaded one.": (
        "Достигнут лимит файлов ({max}). Чтобы добавить новый, удалите один из загруженных."
    ),
}


def get_robbo_ora_runtime_catalog():
    """Merged ORA catalog for XBlock translate, Django {% trans %}, and JS gettext."""
    if not robbo_ora_russian_active():
        return {}
    return {**ROBBO_ORA_RU_STRINGS, **ROBBO_ORA_JS_CATALOG}


def robbo_ora_catalog_message(msgid, **kwargs):
    """
    Studio/LMS string: Russian override when active, else Django gettext (EN msgid).

    Applies printf-style ``kwargs`` when provided (e.g. max_mb=5).
    """
    from django.utils.translation import gettext as _

    text = get_robbo_ora_runtime_catalog().get(msgid, _(msgid))
    if kwargs:
        return text % kwargs
    return text


def patch_robbo_ora_django_catalog():
    """Merge Robbo ORA strings into Django's Russian gettext catalog."""
    if not is_russian_language():
        return

    from django.utils.translation import trans_real

    merged = {**ROBBO_ORA_RU_STRINGS, **ROBBO_ORA_JS_CATALOG}
    try:
        catalog = trans_real.translation('ru')
        # TranslationCatalog.update(dict) raises on Django 4.x; assign entries directly.
        for msgid, msgstr in merged.items():
            catalog._catalog[msgid] = msgstr
    except Exception:  # pylint: disable=broad-except
        pass


# Inline CSS for ORA in chromeless iframes (Learning MFE + Studio Authoring).
# Tokens: docs/design/robbo-brand-guidelines.md
ROBBO_ORA_INLINE_CSS = """
.openassessment {
  color: #383838;
  font-family: 'ProximaNova', 'Proxima Nova', Helvetica, Arial, sans-serif;
}
.openassessment .openassessment__steps__step {
  border-color: #d9e8df;
  background: #fff;
}
.openassessment .openassessment__steps__step.is--in-progress {
  border-color: #00af41 !important;
}
.openassessment .openassessment__steps__step.is--in-progress .step__status__value {
  background: #00af41 !important;
  color: #fff !important;
}
.openassessment .openassessment__steps__step.is--in-progress .step__status__value .copy,
.openassessment .openassessment__steps__step.is--in-progress .step__status__value .icon {
  color: #fff !important;
}
.openassessment .step--response .response__submission {
  background: #e8f8ef !important;
}
.openassessment .submission__answer__part__prompt {
  background: #f7fbf8 !important;
  border-color: #00af41 !important;
}
.openassessment .submission__answer__part__text__value,
.openassessment .submission__answer__part__text textarea {
  color: #383838;
  border-color: #00af41 !important;
}
.openassessment .list--actions .action--submit,
.openassessment .openassessment_student_info_form .action--submit-username {
  background: #00af41 !important;
  border-color: #00af41 !important;
  color: #fff !important;
}
.openassessment .list--actions .action--submit:hover,
.openassessment .openassessment_student_info_form .action--submit-username:hover {
  background: #007a2e !important;
  border-color: #007a2e !important;
}
.openassessment .response__submission__label {
  color: #383838 !important;
}
.openassessment .response__submission__label .save__submission__label {
  color: #383838 !important;
  text-transform: none !important;
}
.openassessment .response__submission__label .save__submission__icon.fa-check-circle-o {
  color: #00af41 !important;
}
.openassessment .response__submission__label .save__submission__icon.fa-refresh {
  color: #00af41 !important;
  display: inline-block;
  animation: robbo-ora-draft-save-spin 1s linear infinite;
}
@keyframes robbo-ora-draft-save-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
.openassessment .response__submission__label .save__submission__icon.fa-exclamation-circle {
  color: #c23c2a !important;
}
.openassessment .step__message.message--waiting {
  background: #e8f8ef;
}
.openassessment .message--complete,
.openassessment .step--student-training .message--correct {
  background: #e8f8ef;
  border-color: #00af41;
}
.openassessment .submission__answer__part__prompt__copy a,
.openassessment .message .message__content a {
  color: #00af41;
}
.openassessment .submission__answer__part__prompt__copy a:hover,
.openassessment .message .message__content a:hover {
  color: #007a2e;
}
.open-response-assessment-block .ora-summary-title {
  color: #00af41 !important;
}
"""

# Upload block of the response step (Studio preview + LMS). Injected together with the step HTML
# by render_assessment / student_view, so this is the single source of these rules.
# Sizes are in px on purpose: the Studio iframe has html { font-size: 62.5% } (10px) and LMS 16px,
# so rem renders differently in the two contexts; edx-ora2 itself uses px (14px labels/buttons).
ROBBO_ORA_RESPONSE_STEP_CSS = """
.step--response {
  --robbo-ora-green: #00af41;
  --robbo-ora-green-dark: #007a2e;
  --robbo-ora-green-darker: #006625;
  --robbo-ora-green-tint: #e8f8ef;
  --robbo-ora-text: #383838;
  --robbo-ora-text-muted: #5c5c5c;
  --robbo-ora-disabled-bg: #edf1ee;
  --robbo-ora-disabled-fg: #7d8b83;
  --robbo-ora-font-size: 14px;
  --robbo-ora-control-height: 40px;
  --robbo-ora-radius: 4px;
  --robbo-ora-font: 'ProximaNova', 'Proxima Nova', Helvetica, Arial, sans-serif;
}
/* One brand font for the whole upload block: Studio falls back to Open Sans, LMS mixes both. */
.step--response .submission__upload__files__title,
.step--response .robbo-ora-upload-rules,
.step--response .robbo-ora-file-picker,
.step--response .robbo-ora-upload-actions,
.step--response .upload__error,
.step--response .upload__error .message__title,
.step--response .delete__error .message__title {
  font-family: var(--robbo-ora-font);
}
.step--response .robbo-ora-upload-rules {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin: 4px 0 16px;
  color: var(--robbo-ora-text-muted);
  font-size: var(--robbo-ora-font-size);
  line-height: 1.5;
}
.step--response .robbo-ora-upload-rules .robbo-ora-size-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 2px;
  padding-left: 16px;
}
.step--response .robbo-ora-file-picker {
  position: relative;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  margin: 0 0 12px;
  min-width: 0;
}
.step--response .robbo-ora-file-picker__input {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  padding: 0;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
/* edx-ora2 visually hides every label in .response__submission__content (0,3,1) — out-rank it. */
.step--response .response__submission__content .robbo-ora-file-picker label.robbo-ora-file-picker__button {
  position: static;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  width: auto;
  height: auto;
  min-height: var(--robbo-ora-control-height);
  overflow: visible;
  clip: auto;
  margin: 0;
  padding: 8px 20px;
  border: 1px solid var(--robbo-ora-green);
  border-radius: var(--robbo-ora-radius);
  background: #fff;
  color: var(--robbo-ora-green-dark);
  font-family: var(--robbo-ora-font);
  font-size: var(--robbo-ora-font-size);
  font-weight: 600;
  line-height: 1.5;
  cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}
.step--response .response__submission__content .robbo-ora-file-picker label.robbo-ora-file-picker__button:hover {
  background: var(--robbo-ora-green-tint);
  border-color: var(--robbo-ora-green-dark);
}
.step--response .response__submission__content .robbo-ora-file-picker .robbo-ora-file-picker__input:focus-visible + label.robbo-ora-file-picker__button {
  outline: 2px solid var(--robbo-ora-green-dark);
  outline-offset: 2px;
}
.step--response .response__submission__content .robbo-ora-file-picker .robbo-ora-file-picker__input:disabled + label.robbo-ora-file-picker__button {
  border-color: var(--robbo-ora-disabled-bg);
  background: var(--robbo-ora-disabled-bg);
  color: var(--robbo-ora-disabled-fg);
  cursor: not-allowed;
}
.step--response .robbo-ora-file-picker__status {
  flex: 1 1 200px;
  min-width: 0;
  overflow: hidden;
  color: var(--robbo-ora-text);
  font-size: var(--robbo-ora-font-size);
  line-height: 1.5;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.step--response .robbo-ora-file-picker__status.is--limit-reached {
  color: var(--robbo-ora-text-muted);
  white-space: normal;
}
.step--response .submission__answer__file__block {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  font-family: var(--robbo-ora-font);
  font-size: var(--robbo-ora-font-size);
}
.step--response .submission__answer__file__block .delete__uploaded__file {
  display: inline-flex;
  align-items: center;
  float: none;
  min-height: 32px;
  margin: 0;
  padding: 4px 12px;
  border: 1px solid #c9d6ce;
  border-radius: var(--robbo-ora-radius);
  background: #fff;
  color: var(--robbo-ora-text);
  font-family: var(--robbo-ora-font);
  font-size: var(--robbo-ora-font-size);
  font-weight: 600;
  line-height: 1.5;
  cursor: pointer;
}
.step--response .submission__answer__file__block .delete__uploaded__file:hover {
  border-color: #c23c2a;
  background: #fff;
  color: #c23c2a;
}
.step--response .submission__answer__file__block .delete__uploaded__file:focus-visible {
  outline: 2px solid var(--robbo-ora-green-dark);
  outline-offset: 2px;
}
.step--response .robbo-ora-upload-actions {
  display: flex;
  justify-content: flex-end;
  margin: 12px 0 0;
}
.step--response .robbo-ora-upload-actions .action--upload {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  box-sizing: border-box;
  float: none;
  width: auto;
  min-width: 0;
  height: auto;
  min-height: var(--robbo-ora-control-height);
  margin: 0;
  padding: 8px 24px;
  border: 1px solid var(--robbo-ora-green);
  border-radius: var(--robbo-ora-radius);
  background: var(--robbo-ora-green);
  color: #fff;
  font-family: var(--robbo-ora-font);
  font-size: var(--robbo-ora-font-size);
  font-weight: 600;
  line-height: 1.5;
  text-align: center;
  cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease;
}
.step--response .robbo-ora-upload-actions .action--upload:hover {
  background: var(--robbo-ora-green-dark);
  border-color: var(--robbo-ora-green-dark);
  color: #fff;
}
.step--response .robbo-ora-upload-actions .action--upload:active {
  background: var(--robbo-ora-green-darker);
  border-color: var(--robbo-ora-green-darker);
}
.step--response .robbo-ora-upload-actions .action--upload:focus-visible {
  outline: 2px solid var(--robbo-ora-green-dark);
  outline-offset: 2px;
}
.step--response .robbo-ora-upload-actions .action--upload:disabled,
.step--response .robbo-ora-upload-actions .action--upload.is--disabled {
  border-color: var(--robbo-ora-disabled-bg);
  background: var(--robbo-ora-disabled-bg);
  color: var(--robbo-ora-disabled-fg);
  opacity: 1;
  cursor: not-allowed;
}
"""

ROBBO_ORA_INLINE_CSS = ROBBO_ORA_INLINE_CSS + ROBBO_ORA_RESPONSE_STEP_CSS
