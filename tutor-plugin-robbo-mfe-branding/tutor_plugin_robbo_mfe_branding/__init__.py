# Copyright (C) 2024-2026 Robbo <https://robbo.ru>
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of the Robbo Open edX distribution. See NOTICE at repository root.

"""
Tutor plugin: Robbo MFE branding — MFE_CONFIG, Paragon URLs; trims tutor-indigo image
injects for bind-mounted MFEs (brand, header/footer packages, footer slot, env imports);
installs Robbo ``@edx/brand`` and RobboFooter chrome for Authoring MFE at image build time.
"""
from __future__ import annotations

import json
from importlib import resources

from tutor import hooks
from tutormfe.hooks import PLUGIN_SLOTS

_PKG = "tutor_plugin_robbo_mfe_branding"

# Authoring (Studio home / courses / libraries) is not bind-mounted; tutor-indigo does not
# restyle it either. Bake Robbo Paragon tokens via local brand package in the MFE build context
# (templates/mfe/build/mfe/robbo-brand-openedx → env after `tutor config save`).
_PATCH_AUTHORING_ROBBO_BRAND = """
COPY robbo-brand-openedx /openedx/robbo-brand-openedx
RUN npm install '@edx/brand@file:/openedx/robbo-brand-openedx'
"""

# After full app COPY + env.config.jsx: put chrome under src/ so babel transpiles JSX
# (node_modules is excluded from babel-loader).
_PATCH_AUTHORING_ROBBO_CHROME_SRC = """
COPY robbo-frontend-chrome /openedx/app/src/robbo-frontend-chrome
"""

_PATCH_AUTHORING_ROBBO_FOOTER_IMPORT = """
const { RobboStudioHelpContent } = await import('./src/robbo-frontend-chrome');
"""

# Only replace Studio help buttons (docs + demo course) → Robbo support.
# Keep the default Studio footer chrome/UI unchanged.
_AUTHORING_STUDIO_HELP_CONTENT_SLOT = """
            {
                op: PLUGIN_OPERATIONS.Hide,
                widgetId: 'default_contents',
            },
            {
                op: PLUGIN_OPERATIONS.Insert,
                widget: {
                    id: 'robbo_studio_help_content',
                    type: DIRECT_PLUGIN,
                    priority: 1,
                    RenderWidget: <RobboStudioHelpContent />,
                },
            },
"""

@hooks.Filters.ENV_TEMPLATE_ROOTS.add(priority=hooks.priorities.LOW)
def _prepend_robbo_template_root(roots: list[str]) -> list[str]:
    """Put Robbo templates first so overrides (e.g. MFE Dockerfile) win over tutormfe."""
    robbo_templates = str(resources.files(_PKG) / "templates")
    deduped = [r for r in roots if r != robbo_templates]
    return [robbo_templates] + deduped

_PARAGON_THEME_URLS = """
MFE_CONFIG["PARAGON_THEME_URLS"] = {
    "core": {
        "urls": {
            "default": "https://cdn.jsdelivr.net/npm/@openedx/paragon@$paragonVersion/dist/core.min.css",
            "brandOverride": "http://{{ LMS_HOST }}:8000/static/robbo-theme/css/paragon-brand-robbo.css",
        },
    },
    "defaults": {
        "light": "light",
    },
    "variants": {
        "light": {
            "urls": {
                "default": "https://cdn.jsdelivr.net/npm/@openedx/paragon@$paragonVersion/dist/light.min.css",
                "brandOverride": "http://{{ LMS_HOST }}:8000/static/robbo-theme/css/paragon-brand-robbo.css",
            },
        },
    },
}
"""

# Production / local without :8000 — overrides brandOverride from common (dev) defaults.
_PARAGON_THEME_URLS_PROD = """
MFE_CONFIG["PARAGON_THEME_URLS"] = {
    "core": {
        "urls": {
            "default": "https://cdn.jsdelivr.net/npm/@openedx/paragon@$paragonVersion/dist/core.min.css",
            "brandOverride": "{% if ENABLE_HTTPS %}https{% else %}http{% endif %}://{{ LMS_HOST }}/static/robbo-theme/css/paragon-brand-robbo.css",
        },
    },
    "defaults": {
        "light": "light",
    },
    "variants": {
        "light": {
            "urls": {
                "default": "https://cdn.jsdelivr.net/npm/@openedx/paragon@$paragonVersion/dist/light.min.css",
                "brandOverride": "{% if ENABLE_HTTPS %}https{% else %}http{% endif %}://{{ LMS_HOST }}/static/robbo-theme/css/paragon-brand-robbo.css",
            },
        },
    },
}
"""

_PATCH_MFE_DEV = """
# Studio Authoring + other MFEs: Robbo wordmark badge (not the legacy envelope Vector.svg).
MFE_CONFIG["LOGO_URL"] = "http://{{ LMS_HOST }}:8000/static/robbo-theme/images/logo-robbo.svg"
MFE_CONFIG["LOGO_TRADEMARK_URL"] = "http://{{ LMS_HOST }}:8000/static/robbo-theme/images/logo-robbo.svg"
MFE_CONFIG["LOGO_WHITE_URL"] = "http://{{ LMS_HOST }}:8000/static/robbo-theme/images/logo-robbo-white.svg"
MFE_CONFIG["FAVICON_URL"] = "http://{{ LMS_HOST }}:8000/static/robbo-theme/images/favicon.ico"
MFE_CONFIG["ENABLE_DYNAMIC_REGISTRATION_FIELDS"] = True
MFE_CONFIG["MARKETING_EMAILS_OPT_IN"] = True
MFE_CONFIG["TOS_AND_HONOR_CODE"] = "https://robbo.ru/wp-content/uploads/agree.pdf"
MFE_CONFIG["PRIVACY_POLICY"] = "https://robbo.ru/wp-content/uploads/policy.pdf"
MFE_CONFIG["ENABLE_YANDEX_METRIKA"] = False
MFE_CONFIG["YANDEX_METRIKA_COUNTER_ID"] = None
"""

_PATCH_MFE_PROD = """
MFE_CONFIG["LOGO_URL"] = "{% if ENABLE_HTTPS %}https{% else %}http{% endif %}://{{ LMS_HOST }}/static/robbo-theme/images/logo-robbo.svg"
MFE_CONFIG["LOGO_TRADEMARK_URL"] = "{% if ENABLE_HTTPS %}https{% else %}http{% endif %}://{{ LMS_HOST }}/static/robbo-theme/images/logo-robbo.svg"
MFE_CONFIG["LOGO_WHITE_URL"] = "{% if ENABLE_HTTPS %}https{% else %}http{% endif %}://{{ LMS_HOST }}/static/robbo-theme/images/logo-robbo-white.svg"
MFE_CONFIG["FAVICON_URL"] = "{% if ENABLE_HTTPS %}https{% else %}http{% endif %}://{{ LMS_HOST }}/static/robbo-theme/images/favicon.ico"
MFE_CONFIG["ENABLE_DYNAMIC_REGISTRATION_FIELDS"] = True
MFE_CONFIG["MARKETING_EMAILS_OPT_IN"] = True
MFE_CONFIG["TOS_AND_HONOR_CODE"] = "https://robbo.ru/wp-content/uploads/agree.pdf"
MFE_CONFIG["PRIVACY_POLICY"] = "https://robbo.ru/wp-content/uploads/policy.pdf"
{% if ROBBO_YANDEX_METRIKA_COUNTER_ID %}
MFE_CONFIG["ENABLE_YANDEX_METRIKA"] = True
MFE_CONFIG["YANDEX_METRIKA_COUNTER_ID"] = {{ ROBBO_YANDEX_METRIKA_COUNTER_ID }}
{% else %}
MFE_CONFIG["ENABLE_YANDEX_METRIKA"] = False
MFE_CONFIG["YANDEX_METRIKA_COUNTER_ID"] = None
{% endif %}
"""

# Tutor sets FEATURES["ENABLE_COURSE_DISCOVERY"] = True. Stock courseware.views.courses
# then skips get_courses() and leaves courses_list empty while the Robbo theme expects
# server-rendered cards (discovery UI is off in theme). Disable discovery so the catalog
# view fills `courses` from MySQL CourseOverview.
_PATCH_ROBBO_LMS_SERVER_CATALOG = """
FEATURES["ENABLE_COURSE_DISCOVERY"] = False
# Show Robbo ``logout.html`` (Russian) then redirect via inline script; fast path still uses ``?next=/``.
FEATURES["SKIP_INTERMEDIATE_LOGOUT_PAGE"] = False
"""

# LK BFF OIDC: MFE_CONFIG + LMS logout → /auth/oidc/logout/lms (path-only; no nested query).
# Enable by setting ROBBO_LK_API_URL and ROBBO_LK_FRONTEND_URL (see tutor/config.example.yml).
_PATCH_ROBBO_LK_BFF = """
{% if ROBBO_LK_API_URL and ROBBO_LK_FRONTEND_URL %}
from urllib.parse import quote, urlparse

_lk_api = {{ ROBBO_LK_API_URL | tojson }}
_lk_fe = {{ ROBBO_LK_FRONTEND_URL | tojson }}
_lk_home = _lk_fe.rstrip("/") + "/home"
MFE_CONFIG["ROBBO_LK_URL"] = _lk_fe
MFE_CONFIG["ROBBO_LK_SSO_URL"] = (
    _lk_api.rstrip("/") + "/auth/oidc/start"
    + "?return_to=" + quote(_lk_home, safe="")
    + "&prompt=none"
)
MFE_CONFIG["ROBBO_BFF_SSO_START"] = _lk_api.rstrip("/") + "/auth/oidc/start?prompt=none"
ROBBO_BFF_LOGOUT_URL = _lk_api.rstrip("/") + "/auth/oidc/logout/lms"
MFE_CONFIG["ROBBO_BFF_LOGOUT_URL"] = ROBBO_BFF_LOGOUT_URL
MFE_CONFIG["LOGOUT_URL"] = (
    "{% if ENABLE_HTTPS %}https{% else %}http{% endif %}://{{ LMS_HOST }}/logout?redirect_url="
    + quote(ROBBO_BFF_LOGOUT_URL, safe="")
)
FEATURES["SKIP_INTERMEDIATE_LOGOUT_PAGE"] = True
_bff_clear = _lk_api.rstrip("/") + "/auth/oidc/logout/clear"
if _bff_clear not in IDA_LOGOUT_URI_LIST:
    IDA_LOGOUT_URI_LIST.append(_bff_clear)
for _robbo_origin in (_lk_api, _lk_fe{% if ROBBO_RS_URL %}, {{ ROBBO_RS_URL | tojson }}{% endif %}):
    _parsed = urlparse(_robbo_origin)
    if not _parsed.hostname:
        continue
    _hostport = _parsed.hostname + ((":" + str(_parsed.port)) if _parsed.port else "")
    if _hostport and _hostport not in LOGIN_REDIRECT_WHITELIST:
        LOGIN_REDIRECT_WHITELIST.append(_hostport)
{% endif %}
"""

# Robbo support: Authn / activation copy, help links (configuration_helpers in login & emails).
_PATCH_ROBBO_SUPPORT = """
SUPPORT_SITE_LINK = "https://support.robbo.world/"
ACTIVATION_EMAIL_SUPPORT_LINK = "https://support.robbo.world/"
"""

# Keep unconfirmed-email prompts active across LMS/MFE flows.
_PATCH_ROBBO_EMAIL_CONFIRMATION = """
MARKETING_EMAILS_OPT_IN = True
SHOW_ACCOUNT_ACTIVATION_CTA = True
FEATURES["SKIP_EMAIL_VALIDATION"] = False
FEATURES["AUTOMATIC_AUTH_FOR_TESTING"] = False
"""

# Anti-spam: per-IP registration cap and minimum time on the form before submit.
_PATCH_ROBBO_REGISTRATION_ANTI_SPAM = """
REGISTRATION_RATELIMIT = '20/d'
REGISTRATION_MIN_COMPLETION_SECONDS = 5
"""

# Authn MFE: company field off (see docs/production.md). Overrides stale site config defaults.
_PATCH_ROBBO_REGISTRATION_FIELDS = """
try:
    REGISTRATION_EXTRA_FIELDS = dict(REGISTRATION_EXTRA_FIELDS)
except NameError:
    REGISTRATION_EXTRA_FIELDS = {}
REGISTRATION_EXTRA_FIELDS['company'] = 'hidden'
REGISTRATION_EXTRA_FIELDS['date_of_birth'] = 'hidden'
"""

# Robbo default locale for LMS/CMS (see also tutor config LANGUAGE_CODE).
_PATCH_ROBBO_LMS_LANGUAGE = """
LANGUAGE_CODE = 'ru'
"""

# Force Russian for all LMS requests (overrides stale language cookies).
_PATCH_ROBBO_FORCE_RUSSIAN_LANGUAGE = """
MIDDLEWARE.append(
    'lms.djangoapps.robbo_lang.middleware.RobboForceRussianLanguageMiddleware',
)
"""
# tutor-indigo init assigns SiteTheme "indigo" for LMS_HOST; force default comprehensive theme.
_PATCH_ROBBO_DEFAULT_SITE_THEME = """
DEFAULT_SITE_THEME = "robbo-theme"
"""

# Bake Robbo xblocks from $TUTOR_ROOT/env/build/openedx/requirements/private.txt (Koa parity).
# pip 24 resolves "-e ./pkg" relative to CWD, not private.txt — must cd into requirements/ first.
_PATCH_OPENEDX_ROBBO_XBLOCKS = """
COPY requirements /openedx/requirements
RUN --mount=type=cache,target=/openedx/.cache/pip,sharing=shared \\
    bash -lc 'set -euo pipefail; cd /openedx/requirements; \\
    if [[ ! -f private.txt ]]; then exit 0; fi; \\
    pip install -r private.txt'
"""

# Robbo Scratch (separate containers scratch-srv-new / scratch-gui-new).
# Survives `tutor config save` (manual Caddyfile edits do not).
# ORA uploads go straight to LMS (filesystem backend: PUT /openassessment/fileupload/...). Tutor caps LMS request
# bodies at 4 MB, which blocks the per-extension "Larger file sizes" option (up to 50 MB per file, see
# cms/djangoapps/contentstore/robbo_ora_limits.py ROBBO_ORA_LARGE_FILE_MB_CAP). Raise the cap for that path only;
# `handle` with a longer path wins over Tutor's `handle_path /*`. ORA PUTs the raw file (no multipart), and both
# Caddy and ORA count 1 MB = 1000**2 bytes, so 50MB matches the cap exactly.
_PATCH_CADDYFILE_LMS_ORA_UPLOADS = """
handle /openassessment/fileupload/* {
    request_body {
        max_size 50MB
    }
}
"""

# Files with a content hash in the name never change under the same URL, but uwsgi (LMS/CMS
# /static) and the MFE Caddy sent no Cache-Control, so browsers revalidated them on every visit.
# LMS/CMS: ManifestStaticFilesStorage adds a 12-hex hash; MFE: webpack 20-hex chunk hashes and
# 32-hex asset names. index.html and unhashed files keep the default behaviour.
_PATCH_CADDYFILE_HASHED_STATIC = r"""
@robbo_hashed_static path_regexp ^/static/.+\.[0-9a-f]{12}\.(css|js|png|jpe?g|gif|svg|webp|ico|woff2?|ttf|eot|otf)$
header @robbo_hashed_static Cache-Control "public, max-age=31536000, immutable"
"""

_PATCH_MFE_CADDYFILE_HASHED_ASSETS = r"""
@robbo_hashed_assets path_regexp ^/[^/]+/(.+[.-])?[0-9a-f]{20,32}\.(css|js|png|jpe?g|gif|svg|webp|ico|woff2?|ttf|eot|otf)$
header @robbo_hashed_assets Cache-Control "public, max-age=31536000, immutable"
"""

# «Проверка ответов» (ORA grading MFE) shows files and rich text written by learners, on the LMS
# site locally and next to it in production. Its Content-Security-Policy limits what such content could
# do if a sanitizer ever let something through: scripts only from the MFE itself (its build has no
# inline scripts, see frontend-app-ora-grading webpack.prod.config.js; the pdf.js worker comes with the
# app), requests and media only to the LMS, Paragon theme CSS from jsdelivr, no plugins, no framing by
# other sites. ROBBO_ORA_GRADING_CSP: "enforce" (default), "report-only" (try a change on a server
# first: violations only reported, nothing blocked) or "off"; ROBBO_CSP_REPORT_URI: where browsers
# POST violation reports (empty: no reports).
_PATCH_MFE_CADDYFILE_ORA_GRADING_CSP = """
{% if ROBBO_ORA_GRADING_CSP in ["enforce", "report-only"] %}
{% set robbo_lms = ("https://" if ENABLE_HTTPS else "http://") + LMS_HOST %}
@robbo_ora_grading path /ora-grading /ora-grading/*
header @robbo_ora_grading {
    {% if ROBBO_ORA_GRADING_CSP == "report-only" %}Content-Security-Policy-Report-Only{% else %}Content-Security-Policy{% endif %} "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' {{ robbo_lms }} https://cdn.jsdelivr.net; img-src 'self' data: {{ robbo_lms }}; font-src 'self' data: {{ robbo_lms }} https://cdn.jsdelivr.net; media-src 'self' {{ robbo_lms }}; connect-src 'self' {{ robbo_lms }}; worker-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self' {{ robbo_lms }}; frame-ancestors 'self' {{ robbo_lms }}{% if ENABLE_HTTPS %}; upgrade-insecure-requests{% endif %}{% if ROBBO_CSP_REPORT_URI %}; report-uri {{ ROBBO_CSP_REPORT_URI }}{% endif %}"
    X-Content-Type-Options "nosniff"
    Referrer-Policy "strict-origin-when-cross-origin"
}
{% endif %}
"""

# Human-readable errors (docs/human-errors.md in the meta repo). Every request gets a number: Caddy's
# request UUID goes to LMS/Studio as X-Request-ID (templates/apps/caddy/Caddyfile, `proxy` snippet) and
# back in every answer; the error journal (lms.djangoapps.robbo_errors) and the user's screen show it.
_PATCH_CADDYFILE_PROXY_REQUEST_ID = """
header X-Request-ID {http.request.uuid}
"""

# Texts of the answers Caddy gives by itself: a copy of the platform's error catalog, written by
# scripts/robbo-errors-sync.py in the meta repo (the plugin is installed without the platform).
hooks.Filters.ENV_TEMPLATE_VARIABLES.add_item(
    ("ROBBO_ERRORS", json.loads((resources.files(_PKG) / "robbo_errors.json").read_text(encoding="utf-8")))
)

# Upload limits of the Caddyfile: templates/apps/caddy/Caddyfile (profile images 1MB, LMS 5MB,
# Studio 250MB) and _PATCH_CADDYFILE_LMS_ORA_UPLOADS (50MB). Keep in step: the page names the limit.
_ROBBO_LMS_UPLOAD_MB = 5
_ROBBO_LMS_PATH_UPLOAD_MB = [["/api/profile_images/*", 1], ["/openassessment/fileupload/*", 50]]
_ROBBO_CMS_UPLOAD_MB = 250

# `handle_errors` of an LMS or Studio site block. Errors Caddy answers by itself (502 while LMS
# restarts, 413 over the upload limit) get the code, text and number of the error catalog: JSON for
# AJAX calls, a page for the browser. CORS headers let the MFEs (on MFE_HOST, or on LMS_HOST locally)
# read the real status; without them the browser hides it and MFEs say "Axios Error (Request)".
#
# Jinja fills in the texts (site language from LANGUAGE_CODE); {vars.*}, {re.*}, {err.*} and
# {http.request.uuid} are Caddy placeholders, \{ \} literal braces for Caddy. Only our texts and the
# request UUID get into the page, never anything from the request: Caddy does not escape placeholders.
# @UPLOAD_MB@ and @PATH_UPLOAD_MB@ are replaced per site block below.
_ROBBO_CADDY_ERRORS = r"""
{%- set robbo_lang = "en" if LANGUAGE_CODE.startswith("en") else "ru" %}
{%- set robbo_codes = ROBBO_ERRORS["codes"] %}
{%- set robbo_ui = ROBBO_ERRORS["ui"] %}
{%- set robbo_help_before, robbo_help_rest = robbo_ui["help_learner"][robbo_lang].split("[") %}
{%- set robbo_help_link, robbo_help_after = robbo_help_rest.split("]") %}
handle_errors {
    route {
        header X-Request-ID {http.request.uuid}
        @robbo_err_cors header_regexp Origin ^https?://({{ MFE_HOST|replace(".", "\\.") }}|{{ LMS_HOST|replace(".", "\\.") }})(:[0-9]+)?$
        header @robbo_err_cors {
            Access-Control-Allow-Origin {http.request.header.Origin}
            Access-Control-Allow-Credentials true
            Access-Control-Expose-Headers X-Request-ID
            Vary Origin
        }
        # SRV-ERROR unless a more exact code below matches (a route keeps this order).
        vars {
            robbo_code SRV-ERROR
            robbo_title "{{ robbo_codes["SRV-ERROR"]["title"][robbo_lang] }}"
            robbo_message "{{ robbo_codes["SRV-ERROR"]["message"][robbo_lang] }}"
            robbo_action "location.reload()"
            robbo_action_label "{{ robbo_ui["reload"][robbo_lang] }}"
            robbo_hex ""
            robbo_short ""
        }
        @robbo_err_restart expression `{err.status_code} in [502, 503, 504]`
        vars @robbo_err_restart {
            robbo_code SRV-RESTART
            robbo_title "{{ robbo_codes["SRV-RESTART"]["title"][robbo_lang] }}"
            robbo_message "{{ robbo_codes["SRV-RESTART"]["message"][robbo_lang] }}"
        }
        @robbo_err_upload expression `{err.status_code} == 413`
        vars @robbo_err_upload {
            robbo_code UPLOAD-SIZE
            robbo_title "{{ robbo_codes["UPLOAD-SIZE"]["title"][robbo_lang] }}"
            robbo_message "{{ robbo_codes["UPLOAD-SIZE"]["message"][robbo_lang]|replace("{limit}", "@UPLOAD_MB@") }}"
            robbo_action "history.back()"
            robbo_action_label "{{ robbo_ui["back"][robbo_lang] }}"
        }
        {%- for robbo_path, robbo_mb in @PATH_UPLOAD_MB@ %}
        @robbo_err_upload_{{ loop.index }} {
            expression `{err.status_code} == 413`
            path {{ robbo_path }}
        }
        vars @robbo_err_upload_{{ loop.index }} robbo_message "{{ robbo_codes["UPLOAD-SIZE"]["message"][robbo_lang]|replace("{limit}", robbo_mb|string) }}"
        {%- endfor %}
        # The number shown to the user: first 8 hex of the UUID; the JSON gets all 32 without dashes.
        @robbo_err_id vars_regexp robbo_id {http.request.uuid} ^([0-9a-f]{4})([0-9a-f]{4})-([0-9a-f]{4})-([0-9a-f]{4})-([0-9a-f]{4})-([0-9a-f]{12})$
        vars @robbo_err_id {
            robbo_hex "{re.robbo_id.1}{re.robbo_id.2}{re.robbo_id.3}{re.robbo_id.4}{re.robbo_id.5}{re.robbo_id.6}"
            robbo_short "{re.robbo_id.1}-{re.robbo_id.2}"
        }
        @robbo_err_html header Accept *text/html*
        header @robbo_err_html Content-Type "text/html; charset=utf-8"
        respond @robbo_err_html <<HTML
            <!doctype html>
            <html lang="{{ robbo_lang }}">
            <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <meta name="robots" content="noindex">
            <title>{vars.robbo_title}</title>
            <style>
            :root \{ --robbo-green: #00af41; --robbo-coal: #383838; --robbo-grey: #989898; --robbo-white: #ffffff; --robbo-gap: 1rem; \}
            *, *::before, *::after \{ box-sizing: border-box; \}
            body \{ margin: 0; min-height: 100vh; display: grid; place-items: center; padding: var(--robbo-gap); background: var(--robbo-white); color: var(--robbo-coal); font: 1rem/1.5 "Proxima Nova", Helvetica, Arial, sans-serif; \}
            .robbo-error \{ width: 100%; max-width: 34rem; padding: calc(var(--robbo-gap) * 2); border: 1px solid var(--robbo-grey); border-radius: 0.75rem; \}
            .robbo-error h1 \{ margin: 0 0 0.5rem; font-size: 1.5rem; line-height: 1.25; overflow-wrap: anywhere; \}
            .robbo-error p \{ margin: 0 0 var(--robbo-gap); overflow-wrap: anywhere; \}
            .robbo-error > :last-child \{ margin-bottom: 0; \}
            .robbo-error a \{ color: var(--robbo-coal); \}
            .robbo-error a:hover \{ color: var(--robbo-green); \}
            .robbo-error :focus-visible \{ outline: 2px solid var(--robbo-green); outline-offset: 2px; \}
            .robbo-error__actions \{ display: flex; flex-wrap: wrap; align-items: center; gap: var(--robbo-gap); margin: calc(var(--robbo-gap) * 1.5) 0; \}
            .robbo-error__button \{ min-height: 2.75rem; padding: 0.5rem 1.25rem; border: 0; border-radius: 0.5rem; background: var(--robbo-green); color: var(--robbo-white); font: inherit; cursor: pointer; \}
            .robbo-error__button:hover \{ filter: brightness(0.92); \}
            .robbo-error__code \{ display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem; font-size: 0.875rem; \}
            .robbo-error__number \{ font-family: ui-monospace, Menlo, Consolas, monospace; text-transform: uppercase; \}
            .robbo-error__copy \{ min-height: 2.75rem; padding: 0 0.75rem; border: 1px solid var(--robbo-grey); border-radius: 0.5rem; background: transparent; color: var(--robbo-coal); font: inherit; cursor: pointer; \}
            .robbo-error__help \{ font-size: 0.875rem; \}
            </style>
            </head>
            <body>
            <main class="robbo-error">
            <h1>{vars.robbo_title}</h1>
            <p>{vars.robbo_message}</p>
            <div class="robbo-error__actions">
            <button class="robbo-error__button" type="button" onclick="{vars.robbo_action}">{vars.robbo_action_label}</button>
            <a href="/">{{ robbo_ui["home"][robbo_lang]|e }}</a>
            </div>
            <p class="robbo-error__code">{{ robbo_ui["code"][robbo_lang]|e }}: <span class="robbo-error__number" id="robbo-error-code">{vars.robbo_code} · {vars.robbo_short}</span>
            <button class="robbo-error__copy" type="button" id="robbo-error-copy" hidden>{{ robbo_ui["copy"][robbo_lang]|e }}</button></p>
            <p class="robbo-error__help">{{ robbo_help_before|e }}<a href="{{ robbo_ui["support_url"]|e }}">{{ robbo_help_link|e }}</a>{{ robbo_help_after|e }}</p>
            </main>
            <script>
            (function () \{
              var copy = document.getElementById("robbo-error-copy");
              var code = document.getElementById("robbo-error-code");
              if (!navigator.clipboard) return;
              copy.hidden = false;
              copy.addEventListener("click", function () \{
                navigator.clipboard.writeText(code.textContent.toUpperCase()).then(function () \{
                  copy.textContent = "{{ robbo_ui["copied"][robbo_lang]|e }}";
                \});
              \});
            \})();
            </script>
            </body>
            </html>
            HTML {err.status_code}
        header Content-Type application/json
        respond <<JSON
            \{"error_code":"{vars.robbo_code}","user_title":"{vars.robbo_title}","user_message":"{vars.robbo_message}","incident_id":"{vars.robbo_hex}","developer_message":"caddy {err.status_code}","error":"{vars.robbo_message}"\}
            JSON {err.status_code}
    }
}
"""

_PATCH_CADDYFILE_LMS_ERRORS = _ROBBO_CADDY_ERRORS.replace("@UPLOAD_MB@", str(_ROBBO_LMS_UPLOAD_MB)).replace(
    "@PATH_UPLOAD_MB@", json.dumps(_ROBBO_LMS_PATH_UPLOAD_MB)
)
_PATCH_CADDYFILE_CMS_ERRORS = _ROBBO_CADDY_ERRORS.replace("@UPLOAD_MB@", str(_ROBBO_CMS_UPLOAD_MB)).replace(
    "@PATH_UPLOAD_MB@", "[]"
)

_PATCH_CADDYFILE_SCRATCH = """
scratch-srv.robbo.world{$default_site_port} {
    import proxy "scratch-srv-new:5000"
}

scratch-gui.robbo.world{$default_site_port} {
    import proxy "scratch-gui-new:5001"
}
"""

# Local Tutor (ENABLE_HTTPS=false): MFE URLs on LMS_HOST, not apps.* — avoids browser
# HTTPS-Only upgrading http://apps.local… to https://… (connection refused on :443).
_PATCH_LOCAL_MFE_ON_LMS_HOST = """
{% if not ENABLE_HTTPS %}
_robbo_mfe_origin = "http://{{ LMS_HOST }}"
LEARNING_MICROFRONTEND_URL = _robbo_mfe_origin + "/learning"
MFE_CONFIG["LEARNING_BASE_URL"] = LEARNING_MICROFRONTEND_URL
LEARNER_HOME_MICROFRONTEND_URL = _robbo_mfe_origin + "/learner-dashboard/"
AUTHN_MICROFRONTEND_URL = _robbo_mfe_origin + "/authn"
AUTHN_MICROFRONTEND_DOMAIN = "{{ LMS_HOST }}/authn"
ACCOUNT_MICROFRONTEND_URL = _robbo_mfe_origin + "/account/"
MFE_CONFIG["ACCOUNT_SETTINGS_URL"] = ACCOUNT_MICROFRONTEND_URL
MFE_CONFIG["COURSE_AUTHORING_MICROFRONTEND_URL"] = _robbo_mfe_origin + "/authoring"
DISCUSSIONS_MICROFRONTEND_URL = _robbo_mfe_origin + "/discussions"
MFE_CONFIG["DISCUSSIONS_MFE_BASE_URL"] = DISCUSSIONS_MICROFRONTEND_URL
WRITABLE_GRADEBOOK_URL = _robbo_mfe_origin + "/gradebook"
ORA_GRADING_MICROFRONTEND_URL = _robbo_mfe_origin + "/ora-grading"
PROFILE_MICROFRONTEND_URL = _robbo_mfe_origin + "/profile/u/"
MFE_CONFIG["ACCOUNT_PROFILE_URL"] = _robbo_mfe_origin + "/profile"
COMMUNICATIONS_MICROFRONTEND_URL = _robbo_mfe_origin + "/communications"
MFE_CONFIG["BASE_URL"] = _robbo_mfe_origin
{% endif %}
"""

# CMS /home/ redirects to COURSE_AUTHORING_MICROFRONTEND_URL — must match LMS_HOST locally.
_PATCH_LOCAL_AUTHORING_MFE_ON_LMS_HOST_CMS = """
{% if not ENABLE_HTTPS %}
_robbo_mfe_origin = "http://{{ LMS_HOST }}"
COURSE_AUTHORING_MICROFRONTEND_URL = _robbo_mfe_origin + "/authoring"
LOGIN_REDIRECT_WHITELIST.append("{{ LMS_HOST }}")
CORS_ORIGIN_WHITELIST.append(_robbo_mfe_origin)
CSRF_TRUSTED_ORIGINS.append(_robbo_mfe_origin)
{% endif %}
"""

_PATCH_ROBBO_THEME_LOCALES = """
from pathlib import Path as _RobboPath

for _robbo_locale_path in reversed((
    _RobboPath("/openedx/edx-platform/themes/conf/locale"),
    _RobboPath("/mnt/openedx-platform/themes/conf/locale"),
    REPO_ROOT / "themes/conf/locale",
)):
    if _robbo_locale_path.exists() and _robbo_locale_path not in LOCALE_PATHS:
        LOCALE_PATHS.insert(0, _robbo_locale_path)
"""

# Never send Yandex Metrika from Tutor dev (`openedx-lms-development-settings`).
_PATCH_YANDEX_METRIKA_DEV_LMS = """
ENABLE_YANDEX_METRIKA = False
YANDEX_METRIKA_COUNTER_ID = None
"""

# Production: enable only when ``ROBBO_YANDEX_METRIKA_COUNTER_ID`` is set in Tutor ``config.yml``.
_PATCH_YANDEX_METRIKA_PROD_LMS = """
{% if ROBBO_YANDEX_METRIKA_COUNTER_ID %}
ENABLE_YANDEX_METRIKA = True
YANDEX_METRIKA_COUNTER_ID = {{ ROBBO_YANDEX_METRIKA_COUNTER_ID }}
{% endif %}
"""

# App IDs that Robbo overrides via Tutor bind-mounts under repos/mfe-overrides/.
# tutor-indigo adds post-`npm clean-install` RUNs: indigo brand, header, footer — which
# override package.json from the mount. Drop those Dockerfile patches for these apps so
# the image matches `tutor dev`. Runtime Paragon CDN is also disabled (see below).
_ROBBO_BINDMOUNT_MFE_APP_IDS: frozenset[str] = frozenset(
    ("authn", "account", "profile", "learning", "learner-dashboard", "discussions")
)

_POST_NPM_INSTALL_PREFIX = "mfe-dockerfile-post-npm-install-"
_RUNTIME_DEF_PREFIX = "mfe-env-config-runtime-definitions-"


def _mfe_post_npm_install_app_id(patch_name: str) -> str | None:
    if not patch_name.startswith(_POST_NPM_INSTALL_PREFIX):
        return None
    return patch_name[len(_POST_NPM_INSTALL_PREFIX) :]


def _mfe_runtime_definitions_app_id(patch_name: str) -> str | None:
    if not patch_name.startswith(_RUNTIME_DEF_PREFIX):
        return None
    return patch_name[len(_RUNTIME_DEF_PREFIX) :]


def _is_indigo_mfe_dockerfile_post_npm_patch(name: str, content: str) -> bool:
    """
    tutor-indigo registers `mfe-dockerfile-post-npm-install-<app>` with brand and/or
    Indigo header/footer npm installs.
    """
    app_id = _mfe_post_npm_install_app_id(name)
    if app_id is None or app_id not in _ROBBO_BINDMOUNT_MFE_APP_IDS:
        return False
    c = content
    return (
        "indigo-brand-openedx" in c
        or "indigo-frontend-component-footer" in c
        or "indigo-frontend-component-header" in c
    )


def _is_indigo_mfe_env_runtime_definitions_patch(name: str, content: str) -> bool:
    """tutor-indigo adds `const { default: IndigoFooter } = await import(...)` per MFE."""
    app_id = _mfe_runtime_definitions_app_id(name)
    if app_id is None or app_id not in _ROBBO_BINDMOUNT_MFE_APP_IDS:
        return False
    c = content
    return "indigo-frontend-component-footer" in c or "IndigoFooter" in c


def _should_drop_indigo_env_patch(name: str, content: str) -> bool:
    return _is_indigo_mfe_dockerfile_post_npm_patch(
        name, content
    ) or _is_indigo_mfe_env_runtime_definitions_patch(name, content)


def _patch_mfe_overrides_paragon_null() -> str:
    """Disable runtime PARAGON_THEME_URLS (CDN) for bind-mounted MFEs; bundle-only theming."""
    parts = [
        "MFE_CONFIG_OVERRIDES = {",
        "    **MFE_CONFIG_OVERRIDES,",
    ]
    for app in sorted(_ROBBO_BINDMOUNT_MFE_APP_IDS):
        parts.extend(
            [
                f'    "{app}": {{',
                f'        **MFE_CONFIG_OVERRIDES.get("{app}", {{}}),',
                '        "PARAGON_THEME_URLS": None,',
                "    },",
            ]
        )
    parts.append("}")
    return "\n".join(parts) + "\n"


_PATCH_ROBBO_BINDMOUNT_MFES_SKIP_RUNTIME_PARAGON = _patch_mfe_overrides_paragon_null()

# Harden npm against flaky registry.npmjs.org (ECONNRESET / EIDLETIMEOUT on weak links).
# Applied once in the MFE `base` stage; inherited by every *-common / Indigo npm install.
_PATCH_MFE_DOCKERFILE_NPM_RESILIENCE = """
# Robbo: durable npm fetches (weak networks / intermittent registry resets).
RUN npm config set fetch-retries 5 \\
 && npm config set fetch-retry-mintimeout 20000 \\
 && npm config set fetch-retry-maxtimeout 120000 \\
 && npm config set fetch-timeout 300000 \\
 && npm config set maxsockets 3
"""


def _wrap_dockerfile_npm_install_runs(content: str) -> str:
    """
    Wrap bare `RUN npm install …` in POSIX retries (no bash/`$((…))`).

    Debian slim uses dash as `/bin/sh`; Dockerfile `$$` + arithmetic was parsed as
    PID + `((…))` and failed with: Syntax error: "(" unexpected.
    """
    lines_out: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        already_wrapped = "sleep 20" in stripped or "npm install retry" in stripped
        if (
            stripped.startswith("RUN ")
            and "npm install" in stripped
            and not already_wrapped
        ):
            raw = stripped[len("RUN ") :].strip()
            if not raw.startswith("npm install"):
                lines_out.append(line)
                continue
            pkg = raw[len("npm install") :].strip().strip("'\"")
            # Double quotes: safe inside `{ …; }` and for `@scope@^ver`.
            cmd = f'npm install "{pkg}"'
            lines_out.extend(
                [
                    f"RUN {cmd} \\",
                    f' || {{ echo "npm install retry 1/4"; sleep 20; {cmd}; }} \\',
                    f' || {{ echo "npm install retry 2/4"; sleep 40; {cmd}; }} \\',
                    f' || {{ echo "npm install retry 3/4"; sleep 60; {cmd}; }} \\',
                    f' || {{ echo "npm install retry 4/4"; sleep 80; {cmd}; }}',
                ]
            )
        else:
            lines_out.append(line)
    text = "\n".join(lines_out)
    if content.endswith("\n") and not text.endswith("\n"):
        text += "\n"
    return text


@hooks.Filters.ENV_PATCHES.add(priority=hooks.priorities.LOW)
def _drop_indigo_mfe_dockerfile_extras_for_robbo_bindmounts(
    patches: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """
    Remove tutor-indigo Dockerfile post-install RUNs (brand, header, footer npm) and the
    matching `env.config.jsx` IndigoFooter import — otherwise the build would still
    reference packages we no longer install.
    """
    return [p for p in patches if not _should_drop_indigo_env_patch(p[0], p[1])]


@hooks.Filters.ENV_PATCHES.add(priority=hooks.priorities.LOW)
def _harden_remaining_indigo_npm_install_runs(
    patches: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    """
    For MFEs that still get Indigo post-npm RUNs (discussions, communications, …),
    wrap each `npm install` in retries so a single ECONNRESET does not fail the image.
    """
    out: list[tuple[str, str]] = []
    for name, content in patches:
        app_id = _mfe_post_npm_install_app_id(name)
        if (
            app_id is not None
            and app_id not in _ROBBO_BINDMOUNT_MFE_APP_IDS
            and (
                "indigo-brand-openedx" in content
                or "indigo-frontend-component-footer" in content
                or "indigo-frontend-component-header" in content
            )
        ):
            out.append((name, _wrap_dockerfile_npm_install_runs(content)))
        else:
            out.append((name, content))
    return out


@PLUGIN_SLOTS.add(priority=hooks.priorities.LOW)
def _drop_indigo_footer_slots_for_robbo_bindmounts(
    slots: list[tuple[str, str, str]],
) -> list[tuple[str, str, str]]:
    """Remove Indigo footer_slot widget definitions for Robbo bind-mounted MFEs."""
    return [
        slot
        for slot in slots
        if not (
            slot[0] in _ROBBO_BINDMOUNT_MFE_APP_IDS
            and slot[1] == "footer_slot"
            and "IndigoFooter" in slot[2]
        )
    ]


PLUGIN_SLOTS.add_item(
    (
        "authoring",
        "org.openedx.frontend.layout.studio_footer_help-content.v1",
        _AUTHORING_STUDIO_HELP_CONTENT_SLOT,
    )
)

# Catalog and learner dashboard cards load course images; thumbnails are off upstream, so cards
# pulled the originals (up to 1.6 MB). Idempotent; see the management command docstring.
hooks.Filters.CLI_DO_INIT_TASKS.add_item(
    ("lms", "./manage.py lms robbo_enable_course_thumbnails"),
    priority=hooks.priorities.LOW,
)
# Course images had no Cache-Control and were revalidated on every catalog/dashboard visit.
hooks.Filters.CLI_DO_INIT_TASKS.add_item(
    ("lms", "./manage.py lms robbo_enable_course_asset_cache"),
    priority=hooks.priorities.LOW,
)

hooks.Filters.CONFIG_DEFAULTS.add_items(
    [
        ("ROBBO_YANDEX_METRIKA_COUNTER_ID", ""),
        ("ROBBO_LK_API_URL", ""),
        ("ROBBO_LK_FRONTEND_URL", "http://localhost:3030"),
        ("ROBBO_RS_URL", ""),
        ("ROBBO_ORA_GRADING_CSP", "enforce"),
        ("ROBBO_CSP_REPORT_URI", ""),
    ]
)

# Translations only for Russian: Robbo sites are Russian (online, skill) and English (courses), and
# English is the source language, built into the code. Without the filter every MFE bundled ~30
# languages of Open edX messages: 78-86% of app.js (learning: 2.3 MB of 2.7 MB) parsed on every
# page. ATLAS_OPTIONS goes to `atlas pull` of the MFE builds and of the openedx image (platform,
# plugin and XBlock translations). A value set in config.yml still wins over this one.
hooks.Filters.CONFIG_OVERRIDES.add_items(
    [
        ("ATLAS_OPTIONS", "--filter=ru"),
    ]
)

hooks.Filters.ENV_PATCHES.add_items(
    [
        ("mfe-dockerfile-base", _PATCH_MFE_DOCKERFILE_NPM_RESILIENCE),
        ("mfe-dockerfile-post-npm-install-authoring", _PATCH_AUTHORING_ROBBO_BRAND),
        # Discussions: Indigo brand is dropped (bind-mount list) — bake Robbo Paragon tokens instead.
        ("mfe-dockerfile-post-npm-install-discussions", _PATCH_AUTHORING_ROBBO_BRAND),
        ("mfe-dockerfile-pre-npm-build-authoring", _PATCH_AUTHORING_ROBBO_CHROME_SRC),
        ("mfe-env-config-runtime-definitions-authoring", _PATCH_AUTHORING_ROBBO_FOOTER_IMPORT),
        ("mfe-lms-common-settings", _PARAGON_THEME_URLS),
        ("mfe-lms-development-settings", _PATCH_MFE_DEV),
        ("mfe-lms-production-settings", _PATCH_MFE_PROD),
        ("mfe-lms-production-settings", _PARAGON_THEME_URLS_PROD),
        ("openedx-lms-development-settings", _PATCH_ROBBO_LMS_SERVER_CATALOG),
        ("openedx-lms-production-settings", _PATCH_ROBBO_LMS_SERVER_CATALOG),
        ("openedx-lms-development-settings", _PATCH_ROBBO_LMS_LANGUAGE),
        ("openedx-lms-production-settings", _PATCH_ROBBO_LMS_LANGUAGE),
        ("openedx-cms-development-settings", _PATCH_ROBBO_LMS_LANGUAGE),
        ("openedx-cms-production-settings", _PATCH_ROBBO_LMS_LANGUAGE),
        ("openedx-lms-development-settings", _PATCH_ROBBO_FORCE_RUSSIAN_LANGUAGE),
        ("openedx-lms-production-settings", _PATCH_ROBBO_FORCE_RUSSIAN_LANGUAGE),
        ("openedx-cms-development-settings", _PATCH_ROBBO_FORCE_RUSSIAN_LANGUAGE),
        ("openedx-cms-production-settings", _PATCH_ROBBO_FORCE_RUSSIAN_LANGUAGE),
        ("openedx-lms-development-settings", _PATCH_ROBBO_SUPPORT),
        ("openedx-lms-production-settings", _PATCH_ROBBO_SUPPORT),
        ("openedx-lms-development-settings", _PATCH_ROBBO_EMAIL_CONFIRMATION),
        ("openedx-lms-production-settings", _PATCH_ROBBO_EMAIL_CONFIRMATION),
        ("openedx-lms-development-settings", _PATCH_ROBBO_REGISTRATION_ANTI_SPAM),
        ("openedx-lms-production-settings", _PATCH_ROBBO_REGISTRATION_ANTI_SPAM),
        ("openedx-lms-development-settings", _PATCH_ROBBO_REGISTRATION_FIELDS),
        ("openedx-lms-production-settings", _PATCH_ROBBO_REGISTRATION_FIELDS),
        ("openedx-lms-development-settings", _PATCH_ROBBO_DEFAULT_SITE_THEME),
        ("openedx-lms-production-settings", _PATCH_ROBBO_DEFAULT_SITE_THEME),
        ("openedx-cms-development-settings", _PATCH_ROBBO_DEFAULT_SITE_THEME),
        ("openedx-cms-production-settings", _PATCH_ROBBO_DEFAULT_SITE_THEME),
        ("openedx-lms-development-settings", _PATCH_ROBBO_THEME_LOCALES),
        ("openedx-lms-production-settings", _PATCH_ROBBO_THEME_LOCALES),
        ("openedx-cms-development-settings", _PATCH_ROBBO_THEME_LOCALES),
        ("openedx-cms-production-settings", _PATCH_ROBBO_THEME_LOCALES),
        ("openedx-lms-development-settings", _PATCH_ROBBO_BINDMOUNT_MFES_SKIP_RUNTIME_PARAGON),
        ("openedx-lms-production-settings", _PATCH_ROBBO_BINDMOUNT_MFES_SKIP_RUNTIME_PARAGON),
        ("openedx-lms-development-settings", _PATCH_YANDEX_METRIKA_DEV_LMS),
        ("openedx-lms-production-settings", _PATCH_YANDEX_METRIKA_PROD_LMS),
        ("openedx-lms-development-settings", _PATCH_ROBBO_LK_BFF),
        ("openedx-lms-production-settings", _PATCH_ROBBO_LK_BFF),
        ("openedx-dockerfile-post-python-requirements", _PATCH_OPENEDX_ROBBO_XBLOCKS),
        ("caddyfile", _PATCH_CADDYFILE_SCRATCH),
        ("caddyfile-proxy", _PATCH_CADDYFILE_PROXY_REQUEST_ID),
        ("caddyfile-lms", _PATCH_CADDYFILE_LMS_ERRORS),
        ("caddyfile-cms", _PATCH_CADDYFILE_CMS_ERRORS),
        ("caddyfile-lms", _PATCH_CADDYFILE_LMS_ORA_UPLOADS),
        ("caddyfile-lms", _PATCH_CADDYFILE_HASHED_STATIC),
        ("caddyfile-cms", _PATCH_CADDYFILE_HASHED_STATIC),
        ("mfe-caddyfile", _PATCH_MFE_CADDYFILE_HASHED_ASSETS),
        ("mfe-caddyfile", _PATCH_MFE_CADDYFILE_ORA_GRADING_CSP),
        ("mfe-lms-production-settings", _PATCH_LOCAL_MFE_ON_LMS_HOST),
        ("openedx-cms-production-settings", _PATCH_LOCAL_AUTHORING_MFE_ON_LMS_HOST_CMS),
        ("openedx-cms-development-settings", _PATCH_LOCAL_AUTHORING_MFE_ON_LMS_HOST_CMS),
    ]
)
