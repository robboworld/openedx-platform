"""
Tutor plugin: Robbo MFE branding — MFE_CONFIG, Paragon URLs, shell CSS for Indigo header/footer.
"""
from __future__ import annotations

from importlib import resources

from tutor import hooks

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
"""

# Robbo support: Authn / activation copy, help links (configuration_helpers in login & emails).
_PATCH_ROBBO_SUPPORT = """
SUPPORT_SITE_LINK = "https://support.robbo.world/"
ACTIVATION_EMAIL_SUPPORT_LINK = "https://support.robbo.world/"
"""

hooks.Filters.ENV_PATCHES.add_items(
    [
        ("mfe-lms-common-settings", _PARAGON_THEME_URLS),
        ("mfe-lms-development-settings", _PATCH_MFE_DEV),
        ("mfe-lms-production-settings", _PATCH_MFE_PROD),
        ("openedx-lms-development-settings", _PATCH_ROBBO_LMS_SERVER_CATALOG),
        ("openedx-lms-production-settings", _PATCH_ROBBO_LMS_SERVER_CATALOG),
        ("openedx-lms-development-settings", _PATCH_ROBBO_SUPPORT),
        ("openedx-lms-production-settings", _PATCH_ROBBO_SUPPORT),
    ]
)
