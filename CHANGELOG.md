# Changelog

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/),
и записи по теме **robbo-theme** ведутся здесь отдельно от апстримового `CHANGELOG.rst`.

## [0.1.0] - 23.04.2026

### Добавлено

- **[LMS] Шапка по референсу:** зелёная полоса (`#00b140`), белый текст навигации; логотип заменён на **словесный знак «РОББО®»** (`navbar-logo-header.html`, стили в `extra/_header.scss`); переключатель темы в шапке скрыт.
- **[Правила Cursor]** В `.cursor/rules/openedx-tutor-scope.mdc` добавлено исключение: после правок **`.scss`** в этом репозитории агент запускает сборку Sass командой `tutor dev exec lms bash -lc 'cd /openedx/edx-platform && npm run compile-sass-dev'`.
- **[Правила Cursor]** `.cursor/rules/changelog-and-commits.mdc`: при запросе **закоммитить** — обновлять `CHANGELOG.md` под текущей версией; при фразе **«обнови changelog под текущей версией»** — править только описание существующего верхнего раздела версии, без нового номера.

### Изменено

- **[LMS+Studio] Футер:** разметка на три зоны — бренд (логотип + копирайт), центральные юридические ссылки, контакты; единые шаблоны `lms/templates/footer.html` и `cms/templates/widgets/footer.html`.
- **[LMS+Studio] Внешний вид футера:** зелёный блок логотипа (`#00b050`), сетка **до 1162px**, три колонки с выравниванием (`justify-self` для краёв и центра), **узкая левая колонка** (`max-width: 241px`), **`row-gap: 0`** у внутренней сетки; адаптивные отступы и типографика через `clamp()`; на узком экране — одна колонка; уточнены `clamp()` для padding и размера шрифта в зелёном блоке логотипа (`extra/_footer.scss`, CMS-аналог).
- **[LMS] Навигация:** пункт «Discover» переименован в **«Course catalog»** в шаблонах `navbar-authenticated.html` и `navbar-not-authenticated.html`; для авторизованных пользователей **«Мои курсы»** и **«Каталог»** выводятся стабильно (в т.ч. на `/courses`); в контекст каталога добавлен `show_dashboard_tabs` в `lms/djangoapps/courseware/views/views.py`.
- **[LMS] Шапка (макет и стиль):** навигационные ссылки — **жирный текст и нижнее подчёркивание** при hover/active (не «пилюли»); на широком экране блок **«Мои курсы» + «Каталог»** **центрируется** по ширине полосы хедера; профиль остаётся справа (`extra/_header.scss`, `$header-height` в `_extras.scss`).
- **[LMS] Форк шапки в платформе:** `lms/static/sass/_brand-header-overrides.scss` — **сплошной** зелёный фон `#00b140` вместо полупрозрачного Indigo; убрано скрытие ссылок каталога (`discover-new-link` / `/courses`), иначе стили темы перебивались порядком импорта; финальные правки overflow/отступов и текста ссылок; выпадающее меню пользователя — **тёмный текст на белом** для светлой темы (`body:not(.indigo-dark-theme)`), без наследования `color: #fff` от правила `.nav-item a`.
- **[LMS] Вёрстка страницы:** `.window-wrap` — колонка **`min-height: 100vh`**, основной блок `#content.content-wrapper` с **`flex: 1`**, чтобы футер **оставался внизу окна** при коротком контенте; у `.wrapper-footer` задано **`flex: 0 0 auto`**, чтобы футер **не растягивался** за счёт flex.
- **[LMS] Отступы футера:** вертикальный padding обёртки **20px**; у `.window-wrap` вместо `overflow: hidden` используется **`overflow-x: hidden`**, **`overflow-y: visible`**.
- **[LMS] Контент:** убран устаревший **`min-height: calc(100vh − …)`** у `#content.content-wrapper` (раньше завязан на фиктивную высоту футера).
- **[LMS] Каталог курсов:** в `themes/robbo-theme/lms/templates/courseware/courses.html` исправлена опечатка в разметке (`filter-bar`).

### Исправлено

- **[LMS+Studio] Футер:** убраны ошибочные стили у списка ссылок (`position: absolute`, фиксированная высота и т.п.), из‑за которых блок уезжал с макета.
- **[LMS+Studio] Футер:** из списка документов удалён пункт **«Согласие на получение рекламы»** (`lms/templates/footer.html`, `cms/templates/widgets/footer.html`).
- **[LMS] Шапка:** у ссылок «Мои курсы» / «Каталог» убран **белый квадрат при клике** (outline/`tap-highlight`; для клавиатуры оставлен лёгкий `:focus-visible`).

Где изменено: `themes/robbo-theme` (`lms/static/sass/extra/_footer.scss`, `lms/static/sass/extra/_header.scss`, `lms/static/sass/partials/lms/theme/_extras.scss`, `lms/templates/footer.html`, `lms/templates/courseware/courses.html`, `lms/templates/header/*.html`), `themes/robbo-theme/cms/static/sass/partials/cms/theme/_footer.scss`, `themes/robbo-theme/cms/templates/widgets/footer.html`, `lms/static/sass/_brand-header-overrides.scss`, `lms/djangoapps/courseware/views/views.py`, `.cursor/rules/openedx-tutor-scope.mdc`, `.cursor/rules/changelog-and-commits.mdc`, `CHANGELOG.md`.
