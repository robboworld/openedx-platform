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
"""

# Robbo default locale for LMS/CMS (see also tutor config LANGUAGE_CODE).
_PATCH_ROBBO_LMS_LANGUAGE = """
LANGUAGE_CODE = 'ru'
"""

# Force Russian for all LMS requests (overrides stale language cookies).
_PATCH_ROBBO_FORCE_RUSSIAN_LANGUAGE = """
MIDDLEWARE.insert(
    0,
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
_PATCH_CADDYFILE_SCRATCH = """
scratch-srv.robbo.world{$default_site_port} {
    import proxy "scratch-srv-new:5000"
}

scratch-gui.robbo.world{$default_site_port} {
    import proxy "scratch-gui-new:5001"
}
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
    ("authn", "account", "profile", "learning", "learner-dashboard")
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

hooks.Filters.CONFIG_DEFAULTS.add_items(
    [
        ("ROBBO_YANDEX_METRIKA_COUNTER_ID", ""),
    ]
)

hooks.Filters.ENV_PATCHES.add_items(
    [
        ("mfe-dockerfile-post-npm-install-authoring", _PATCH_AUTHORING_ROBBO_BRAND),
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
        ("openedx-lms-development-settings", _PATCH_ROBBO_FORCE_RUSSIAN_LANGUAGE),
        ("openedx-lms-production-settings", _PATCH_ROBBO_FORCE_RUSSIAN_LANGUAGE),
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
        ("openedx-dockerfile-post-python-requirements", _PATCH_OPENEDX_ROBBO_XBLOCKS),
        ("caddyfile", _PATCH_CADDYFILE_SCRATCH),
    ]
)
