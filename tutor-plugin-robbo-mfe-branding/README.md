# Tutor plugin: Robbo MFE branding

Patches [tutor-mfe](https://github.com/overhangio/tutor-mfe) so MFEs get Robbo logos and Paragon theme CSS (light only) from the LMS config API, and **Indigo header/footer** are recolored to match LMS `robbo-theme` via `robbo-mfe-shell.css` injected at **`tutor images build mfe`** time.

## Documentation

- **[PRODUCTION.md](docs/PRODUCTION.md)** — блок **«Скопировать в чат Cursor»** для одношаговой настройки; справочник оператора (классы A/B/C, продакшен). Правило Cursor: [.cursor/rules/openedx-tutor-robbo.mdc](../.cursor/rules/openedx-tutor-robbo.mdc).

## Install

From the `openedx-platform` repo root:

```bash
pip install -e ./tutor-plugin-robbo-mfe-branding
tutor plugins enable robbo-mfe-branding
tutor config save
```

Ensure `INDIGO_ENABLE_DARK_TOGGLE: false` is set in `config.yml` if you use tutor-indigo and want the theme toggle hidden on LMS/MFE.

Regenerate env, **rebuild the MFE image** (shell CSS is baked in), restart:

```bash
tutor config save
tutor images build mfe
tutor local launch   # or: tutor dev launch
```

Runtime-only changes (`MFE_CONFIG`, logos URLs) do not need an MFE rebuild; header/footer shell overrides do.

## What it does

- **`mfe-lms-development-settings`**: `LOGO_*`, `FAVICON_URL` pointing at `http://{{ LMS_HOST }}:8000/static/robbo-theme/...`
- **`mfe-lms-production-settings`**: same paths with `http(s)://{{ LMS_HOST }}` (no port)
- **`mfe-lms-common-settings`**: `PARAGON_THEME_URLS` with only `light` (Paragon + `@openedx/brand-openedx` from jsDelivr, `$paragonVersion` / `$brandVersion` wildcards)
