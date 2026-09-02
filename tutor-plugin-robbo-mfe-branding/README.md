# Плагин Tutor: брендинг MFE Robbo

Патчит [tutor-mfe](https://github.com/overhangio/tutor-mfe), чтобы MFE получали
логотипы Robbo и CSS темы Paragon (только light) из LMS config API, а
**header/footer Indigo** перекрашивались под LMS `robbo-theme` через
`robbo-mfe-shell.css`, внедряемый при **`tutor images build mfe`**.

**Authoring (Studio):** при сборке образа Authoring MFE ставит локальный brand-пакет
`robbo-brand-openedx` как `@edx/brand` (`$primary: #00af41`). После правок brand SCSS
пересоберите `mfe`.

## Документация

- **[PRODUCTION.md](docs/PRODUCTION.md)** — блок **«Скопировать в чат Cursor»**
  для одношаговой настройки; справочник оператора (классы A/B/C, продакшен).
  Правило Cursor:
  [.cursor/rules/openedx-tutor-robbo.mdc](../.cursor/rules/openedx-tutor-robbo.mdc).

## Установка

Из корня репозитория `openedx-platform`:

```bash
pip install -e ./tutor-plugin-robbo-mfe-branding
tutor plugins enable robbo-mfe-branding
tutor config save
```

Если используете tutor-indigo и хотите скрыть переключатель темы на LMS/MFE,
в `config.yml` задайте `INDIGO_ENABLE_DARK_TOGGLE: false`.

Перегенерируйте env, **пересоберите образ MFE** (brand Authoring + shell CSS
запекаются), перезапустите:

```bash
tutor config save
tutor images build mfe
tutor local launch   # или: tutor dev restart mfe
```

Изменения только runtime (`MFE_CONFIG`, URL логотипов) не требуют пересборки MFE;
цвет primary Authoring и overrides shell header/footer — требуют.

## Что делает

- **`mfe-dockerfile-post-npm-install-authoring`**: `COPY` +
  `npm install @edx/brand@file:…/robbo-brand-openedx` (зелёные токены Paragon для Studio)
- **`mfe-lms-development-settings`**: `LOGO_*`, `FAVICON_URL` на
  `http://{{ LMS_HOST }}:8000/static/robbo-theme/...`
- **`mfe-lms-production-settings`**: те же пути с `http(s)://{{ LMS_HOST }}`
  (без порта)
- **`mfe-lms-common-settings`**: `PARAGON_THEME_URLS` только с `light`
  (Paragon + `@openedx/brand-openedx` с jsDelivr, wildcard `$paragonVersion` /
  `$brandVersion`)
