# Robbo MFE branding: продакшен и настройка через Cursor

Документ для операторов и для **вставки в чат Cursor**, чтобы ассистент выполнил настройку Tutor + плагина `robbo-mfe-branding`.

**Правило репозитория (агент):** [.cursor/rules/openedx-tutor-robbo.mdc](../../.cursor/rules/openedx-tutor-robbo.mdc).

---

## Скопировать в чат Cursor (одним сообщением)

Скопируй всё между линиями **BEGIN** и **END** (включительно можно без заголовков «BEGIN/END» — главное тело поручения). Подставь пути, если у тебя другие.

**Вариант без копирования:** в чат приложи файл `tutor-plugin-robbo-mfe-branding/docs/PRODUCTION.md` и напиши: «Выполни настройку по разделу „Скопировать в чат Cursor“».

```
BEGIN CURSOR PROMPT — Robbo MFE branding + Tutor

Контекст: репозиторий openedx-platform уже открыт в workspace. Нужно настроить Tutor так, чтобы работали плагин robbo-mfe-branding (логотипы MFE, Paragon light, shell CSS для шапки/футера Indigo).

Сделай по шагам (исполняй команды сам, если есть доступ к shell и tutor):

1) Узнай корень Tutor: `tutor config printroot`. Дальше `config.yml` = `<корень>/config.yml`, при необходимости сгенерируй env: `tutor config save`.

2) Установи плагин из этого репозитория (путь к openedx-platform возьми из workspace):
   pip install -e "<ABS_PATH_OPENEDX>/tutor-plugin-robbo-mfe-branding"

3) Включи плагины (если ещё не включены): `tutor plugins enable indigo mfe robbo-mfe-branding`
   Порядок в config.yml: indigo, mfe, robbo-mfe-branding — не переставляй без причины.

4) В config.yml выставь (сохрани существующие секреты/ключи):
   - INDIGO_ENABLE_DARK_TOGGLE: false   # скрыть переключатель темы в UI, логику dark не вырезать
   - В MOUNTS укажи актуальный путь к клону openedx-platform и теме robbo-theme, например:
     MOUNTS:
       - "<ABS_PATH_OPENEDX>"
       - lms:"<ABS_PATH_OPENEDX>/themes/robbo-theme:/openedx/themes/robbo-theme"
       - cms:"<ABS_PATH_OPENEDX>/themes/robbo-theme:/openedx/themes/robbo-theme"
     (если у команды уже есть свои маунты sass/css — не удаляй без согласования.)

5) Выполни: `tutor config save`

6) Пересобери образ MFE (в shell CSS и Dockerfile-патчи плагина входят в сборку):
   tutor images build mfe

7) Перезапусти стек так, как принято в этом окружении (например `tutor local launch` или `tutor dev launch`). Если образы не пересобирались на шаге 6 — всё равно перезапусти сервисы после config save.

8) Проверь: LMS открывается, MFE authn и learner-dashboard — зелёная шапка как на LMS, логотипы Robbo, футер в светлом стиле. При сбоях смотри README плагина и раздел «Справочник оператора» в этом же файле PRODUCTION.md.

Правило агента: openedx-tutor-robbo.mdc. Не правь посторонние файлы вне задачи.

END CURSOR PROMPT
```

---

## Справочник оператора

Ниже — классы изменений и выкладка **без** привязки к Cursor.

### Предварительные условия

- На сервере (или в CI) установлены **тот же** `tutor`, версии плагинов **`mfe`**, **`indigo`**, **`robbo-mfe-branding`**, что и при разработке (или совместимые мажорные версии).
- В `config.yml` включён плагин `robbo-mfe-branding`, при необходимости заданы `INDIGO_ENABLE_DARK_TOGGLE`, `LMS_HOST`, `ENABLE_HTTPS`, маунты темы `robbo-theme` и т.д.
- Статика логотипов (`Vector.svg`, `logo-mfe-white.svg`) доступна с браузера по URL вида `https://<LMS_HOST>/static/robbo-theme/...` (HTTPS в проде обычно обязателен).

### A. Только рантайм-конфиг MFE (без пересборки образа `mfe`)

Правки патчей **`mfe-lms-common-settings`**, **`mfe-lms-production-settings`**, которые задают только **`MFE_CONFIG`** (логотипы, `PARAGON_THEME_URLS` и т.д., отдаётся через `/api/mfe_config/v1`).

**Действия:** обновить код плагина → `pip install -e ./tutor-plugin-robbo-mfe-branding` → `tutor config save` → перезапуск LMS (и при необходимости прокси). Образ **`mfe` пересобирать не обязательно**.

### B. Изменения, вшиваемые в сборку MFE (нужна пересборка образа)

Правки **`robbo-mfe-shell.css`**, патчей **`mfe-dockerfile-pre-npm-build-*`** или других **`mfe-dockerfile-*`**.

**Действия:** п. A по коду → `tutor config save` → **`tutor images build mfe`** → выкладка образа (Docker Compose / registry / Kubernetes по процессу команды) → перезапуск.

### C. Изменения только в comprehensive theme (`themes/robbo-theme` на LMS)

Логотипы по URL `/static/robbo-theme/...` зависят от образа **openedx** и `collectstatic`.

**Действия:** обычно `tutor images build openedx` и выкладка LMS/CMS. Образ **`mfe`** — только если меняли п. B.

### Чеклист релиза плагина

1. Git + при необходимости [`CHANGELOG.md`](../../CHANGELOG.md).
2. Staging: `pip install -e ...`, `tutor config save`, при необходимости `tutor images build mfe`, smoke authn + learner-dashboard + LMS.
3. Production: те же шаги с тем же коммитом/образами.
4. Проверка `https://<LMS_HOST>/api/mfe_config/v1` (если API включён).
5. Визуальная проверка MFE после жёсткого обновления страницы.

### Indigo и порядок плагинов

**`robbo-mfe-branding`** включён вместе с **`mfe`** и **`indigo`**. Патчи Dockerfile рассчитаны на установку Indigo header/footer **до** слоя Robbo CSS.

### Частые ошибки

- Правка `robbo-mfe-shell.css` без **`tutor images build mfe`** — старый UI.
- Логотипы 404 — тема не в образе/маунтах или неверный `LMS_HOST`/HTTPS в `MFE_CONFIG`.
- Кэш браузера — инкогнито или сброс кэша.

### Ссылки

- [README плагина](../README.md)
- [Tutor: Plugins](https://docs.tutor.edly.io/plugins/index.html)
- [tutor-mfe](https://github.com/overhangio/tutor-mfe)
- [frontend-platform: theming](https://github.com/openedx/frontend-platform/blob/master/docs/how_tos/theming.md)
