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

# Authoring (Studio home / courses / libraries) is not in the bind-mount set; bake Robbo
# Paragon tokens via local brand package in the MFE build context
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

# Runtime green primary for Authoring (and any MFE still using PARAGON_THEME_URLS).
# Bind-mounted MFEs null this out and use bundled Robbo tokens instead.
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
MFE_CONFIG["ROBBO_ANALYTICS_URL"] = "http://{{ LMS_HOST }}:8000/robbo/analytics/"
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
MFE_CONFIG["ROBBO_ANALYTICS_URL"] = "{% if ENABLE_HTTPS %}https{% else %}http{% endif %}://{{ LMS_HOST }}/robbo/analytics/"
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

# Robbo theme translations override stock LMS labels while keeping stock gettext keys.
# tutor-indigo init assigns SiteTheme "indigo" for LMS_HOST; force default comprehensive theme.
_PATCH_ROBBO_DEFAULT_SITE_THEME = """
DEFAULT_SITE_THEME = "robbo-theme"
"""

# Share LMS session between LMS_HOST and apps.* MFE host (e.g. skill.robbo.ru ↔ apps.skill.robbo.ru).
# CSRF_COOKIE_SAMESITE=None is required for cross-site Learning MFE iframe POSTs to LMS chromeless views.
# Do not enable CSRF_USE_SESSIONS here — it breaks the dual-cookie cleanup path on skill.
_PATCH_MFE_CROSS_DOMAIN_SESSION = """
{% if MFE_HOST and MFE_HOST != LMS_HOST %}
SESSION_COOKIE_DOMAIN = ".{{ LMS_HOST }}"
CSRF_COOKIE_DOMAIN = ".{{ LMS_HOST }}"
CSRF_COOKIE_SAMESITE = "None"
{% endif %}
"""

# Seamless cleanup of host-only csrftoken left after CSRF_COOKIE_DOMAIN migration (no mass logout).
_PATCH_EXPIRE_LEGACY_CSRF_COOKIE = """
{% if MFE_HOST and MFE_HOST != LMS_HOST %}
ROBBO_LEGACY_CSRF_COOKIE_DOMAIN = "{{ LMS_HOST }}"
_EXPIRE_LEGACY_CSRF_MW = "openedx.core.djangoapps.cors_csrf.expire_legacy_csrf.ExpireLegacyCsrfCookieMiddleware"
if _EXPIRE_LEGACY_CSRF_MW not in MIDDLEWARE:
    MIDDLEWARE.append(_EXPIRE_LEGACY_CSRF_MW)
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
                '        "ROBBO_ANALYTICS_URL": "{% if ENABLE_HTTPS %}https{% else %}http{% endif %}://{{ LMS_HOST }}/robbo/analytics/",',
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

hooks.Filters.CONFIG_DEFAULTS.add_items(
    [
        ("ROBBO_YANDEX_METRIKA_COUNTER_ID", ""),
    ]
)

hooks.Filters.ENV_PATCHES.add_items(
    [
        ("mfe-dockerfile-base", _PATCH_MFE_DOCKERFILE_NPM_RESILIENCE),
        ("mfe-dockerfile-post-npm-install-authoring", _PATCH_AUTHORING_ROBBO_BRAND),
        ("mfe-dockerfile-pre-npm-build-authoring", _PATCH_AUTHORING_ROBBO_CHROME_SRC),
        ("mfe-env-config-runtime-definitions-authoring", _PATCH_AUTHORING_ROBBO_FOOTER_IMPORT),
        ("mfe-lms-common-settings", _PARAGON_THEME_URLS),
        ("mfe-lms-development-settings", _PATCH_MFE_DEV),
        ("mfe-lms-production-settings", _PATCH_MFE_PROD),
        ("mfe-lms-production-settings", _PARAGON_THEME_URLS_PROD),
        ("openedx-lms-development-settings", _PATCH_ROBBO_LMS_SERVER_CATALOG),
        ("openedx-lms-production-settings", _PATCH_ROBBO_LMS_SERVER_CATALOG),
        ("openedx-lms-development-settings", _PATCH_ROBBO_SUPPORT),
        ("openedx-lms-production-settings", _PATCH_ROBBO_SUPPORT),
        ("openedx-lms-development-settings", _PATCH_ROBBO_EMAIL_CONFIRMATION),
        ("openedx-lms-production-settings", _PATCH_ROBBO_EMAIL_CONFIRMATION),
        ("openedx-lms-development-settings", _PATCH_ROBBO_REGISTRATION_ANTI_SPAM),
        ("openedx-lms-production-settings", _PATCH_ROBBO_REGISTRATION_ANTI_SPAM),
        ("openedx-lms-development-settings", _PATCH_MFE_CROSS_DOMAIN_SESSION),
        ("openedx-lms-production-settings", _PATCH_MFE_CROSS_DOMAIN_SESSION),
        ("openedx-lms-development-settings", _PATCH_EXPIRE_LEGACY_CSRF_COOKIE),
        ("openedx-lms-production-settings", _PATCH_EXPIRE_LEGACY_CSRF_COOKIE),
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
    ]
)
