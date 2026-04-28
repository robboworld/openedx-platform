"""
Tutor plugin: Robbo MFE branding — MFE_CONFIG, Paragon URLs; trims tutor-indigo image
injects for bind-mounted MFEs (brand, header/footer packages, footer slot, env imports).
"""
from __future__ import annotations

from importlib import resources

from tutor import hooks
from tutormfe.hooks import PLUGIN_SLOTS

_PKG = "tutor_plugin_robbo_mfe_branding"

hooks.Filters.ENV_TEMPLATE_ROOTS.add_item(str(resources.files(_PKG) / "templates"))

_PARAGON_THEME_URLS = """
MFE_CONFIG["PARAGON_THEME_URLS"] = {
    "core": {
        "urls": {
            "default": "https://cdn.jsdelivr.net/npm/@openedx/paragon@$paragonVersion/dist/core.min.css",
            "brandOverride": "https://cdn.jsdelivr.net/npm/@openedx/brand-openedx@$brandVersion/dist/core.min.css",
        },
    },
    "defaults": {
        "light": "light",
    },
    "variants": {
        "light": {
            "urls": {
                "default": "https://cdn.jsdelivr.net/npm/@openedx/paragon@$paragonVersion/dist/light.min.css",
                "brandOverride": "https://cdn.jsdelivr.net/npm/@openedx/brand-openedx@$brandVersion/dist/light.min.css",
            },
        },
    },
}
"""

_PATCH_MFE_DEV = """
MFE_CONFIG["LOGO_URL"] = "http://{{ LMS_HOST }}:8000/static/robbo-theme/images/Vector.svg"
MFE_CONFIG["LOGO_TRADEMARK_URL"] = "http://{{ LMS_HOST }}:8000/static/robbo-theme/images/Vector.svg"
MFE_CONFIG["LOGO_WHITE_URL"] = "http://{{ LMS_HOST }}:8000/static/robbo-theme/images/logo-mfe-white.svg"
MFE_CONFIG["FAVICON_URL"] = "http://{{ LMS_HOST }}:8000/favicon.ico"
MFE_CONFIG["ENABLE_DYNAMIC_REGISTRATION_FIELDS"] = True
MFE_CONFIG["MARKETING_EMAILS_OPT_IN"] = True
MFE_CONFIG["TOS_AND_HONOR_CODE"] = "https://robbo.ru/wp-content/uploads/agree.pdf"
MFE_CONFIG["PRIVACY_POLICY"] = "https://robbo.ru/wp-content/uploads/policy.pdf"
"""

_PATCH_MFE_PROD = """
MFE_CONFIG["LOGO_URL"] = "{% if ENABLE_HTTPS %}https{% else %}http{% endif %}://{{ LMS_HOST }}/static/robbo-theme/images/Vector.svg"
MFE_CONFIG["LOGO_TRADEMARK_URL"] = "{% if ENABLE_HTTPS %}https{% else %}http{% endif %}://{{ LMS_HOST }}/static/robbo-theme/images/Vector.svg"
MFE_CONFIG["LOGO_WHITE_URL"] = "{% if ENABLE_HTTPS %}https{% else %}http{% endif %}://{{ LMS_HOST }}/static/robbo-theme/images/logo-mfe-white.svg"
MFE_CONFIG["FAVICON_URL"] = "{% if ENABLE_HTTPS %}https{% else %}http{% endif %}://{{ LMS_HOST }}/favicon.ico"
MFE_CONFIG["ENABLE_DYNAMIC_REGISTRATION_FIELDS"] = True
MFE_CONFIG["MARKETING_EMAILS_OPT_IN"] = True
MFE_CONFIG["TOS_AND_HONOR_CODE"] = "https://robbo.ru/wp-content/uploads/agree.pdf"
MFE_CONFIG["PRIVACY_POLICY"] = "https://robbo.ru/wp-content/uploads/policy.pdf"
"""

# Tutor sets FEATURES["ENABLE_COURSE_DISCOVERY"] = True. Stock courseware.views.courses
# then skips get_courses() and leaves courses_list empty while the Robbo theme expects
# server-rendered cards (discovery UI is off in theme). Disable discovery so the catalog
# view fills `courses` from MySQL CourseOverview.
_PATCH_ROBBO_LMS_SERVER_CATALOG = """
FEATURES["ENABLE_COURSE_DISCOVERY"] = False
# Immediate redirect to ``next``/home; avoids broken iframe/JS logout interstitial on Robbo stacks.
FEATURES["SKIP_INTERMEDIATE_LOGOUT_PAGE"] = True
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

# Robbo theme translations override stock LMS labels while keeping stock gettext keys.
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


hooks.Filters.ENV_PATCHES.add_items(
    [
        ("mfe-lms-common-settings", _PARAGON_THEME_URLS),
        ("mfe-lms-development-settings", _PATCH_MFE_DEV),
        ("mfe-lms-production-settings", _PATCH_MFE_PROD),
        ("openedx-lms-development-settings", _PATCH_ROBBO_LMS_SERVER_CATALOG),
        ("openedx-lms-production-settings", _PATCH_ROBBO_LMS_SERVER_CATALOG),
        ("openedx-lms-development-settings", _PATCH_ROBBO_SUPPORT),
        ("openedx-lms-production-settings", _PATCH_ROBBO_SUPPORT),
        ("openedx-lms-development-settings", _PATCH_ROBBO_EMAIL_CONFIRMATION),
        ("openedx-lms-production-settings", _PATCH_ROBBO_EMAIL_CONFIRMATION),
        ("openedx-lms-development-settings", _PATCH_ROBBO_THEME_LOCALES),
        ("openedx-lms-production-settings", _PATCH_ROBBO_THEME_LOCALES),
        ("openedx-lms-development-settings", _PATCH_ROBBO_BINDMOUNT_MFES_SKIP_RUNTIME_PARAGON),
        ("openedx-lms-production-settings", _PATCH_ROBBO_BINDMOUNT_MFES_SKIP_RUNTIME_PARAGON),
    ]
)
