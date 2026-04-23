# Changelog

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/),
и записи по теме **robbo-theme** ведутся здесь отдельно от апстримового `CHANGELOG.rst`.

## [0.1.0] - 23.04.2026

### Добавлено

- **[LMS] Шапка по референсу:** зелёная полоса (`#00b140`), белый текст навигации; логотип заменён на **словесный знак «РОББО®»** (`navbar-logo-header.html`, стили в `extra/_header.scss`); переключатель темы в шапке скрыт.
- **[Правила Cursor]** В `.cursor/rules/openedx-tutor-scope.mdc` добавлено исключение: после правок **`.scss`** в этом репозитории агент запускает сборку Sass командой `tutor dev exec lms bash -lc 'cd /openedx/edx-platform && npm run compile-sass-dev'`.

### Изменено

- **[LMS+Studio] Футер:** разметка на три зоны — бренд (логотип + копирайт), центральные юридические ссылки, контакты; единые шаблоны `lms/templates/footer.html` и `cms/templates/widgets/footer.html`.
- **[LMS+Studio] Внешний вид футера:** зелёный блок логотипа (`#00b050`), сетка **до 1162px**, три колонки с выравниванием (`justify-self` для краёв и центра), **узкая левая колонка** (`max-width: 241px`), **`row-gap: 0`** у внутренней сетки; адаптивные отступы и типографика через `clamp()`; на узком экране — одна колонка.
- **[LMS] Навигация:** пункт «Discover» переименован в **«Course catalog»** в шаблонах `navbar-authenticated.html` и `navbar-not-authenticated.html`.
- **[LMS] Вёрстка страницы:** `.window-wrap` — колонка **`min-height: 100vh`**, основной блок `#content.content-wrapper` с **`flex: 1`**, чтобы футер **оставался внизу окна** при коротком контенте; у `.wrapper-footer` задано **`flex: 0 0 auto`**, чтобы футер **не растягивался** за счёт flex.
- **[LMS] Отступы футера:** вертикальный padding обёртки **20px**; у `.window-wrap` вместо `overflow: hidden` используется **`overflow-x: hidden`**, **`overflow-y: visible`**.
- **[LMS] Контент:** убран устаревший **`min-height: calc(100vh − …)`** у `#content.content-wrapper` (раньше завязан на фиктивную высоту футера).

### Исправлено

- **[LMS+Studio] Футер:** убраны ошибочные стили у списка ссылок (`position: absolute`, фиксированная высота и т.п.), из‑за которых блок уезжал с макета.

Где изменено: `themes/robbo-theme` (`lms/static/sass/extra/_footer.scss`, `lms/static/sass/extra/_header.scss`, `lms/static/sass/partials/lms/theme/_extras.scss`, `lms/templates/footer.html`, `lms/templates/header/*.html`), `themes/robbo-theme/cms/static/sass/partials/cms/theme/_footer.scss`, `themes/robbo-theme/cms/templates/widgets/footer.html`, `.cursor/rules/openedx-tutor-scope.mdc`, `CHANGELOG.md`.
