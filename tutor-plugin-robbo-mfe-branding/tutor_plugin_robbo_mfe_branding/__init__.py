"""
Tutor plugin: Robbo MFE branding — MFE_CONFIG, Paragon URLs, shell CSS for Indigo header/footer.
"""
from __future__ import annotations

from importlib import resources

from tutor import hooks

_PKG = "tutor_plugin_robbo_mfe_branding"

hooks.Filters.ENV_TEMPLATE_ROOTS.add_item(str(resources.files(_PKG) / "templates"))
hooks.Filters.ENV_TEMPLATE_TARGETS.add_item(
    ("robbo-mfe-shell.css", "plugins/mfe/build/mfe")
)

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
"""

_PATCH_MFE_PROD = """
MFE_CONFIG["LOGO_URL"] = "{% if ENABLE_HTTPS %}https{% else %}http{% endif %}://{{ LMS_HOST }}/static/robbo-theme/images/Vector.svg"
MFE_CONFIG["LOGO_TRADEMARK_URL"] = "{% if ENABLE_HTTPS %}https{% else %}http{% endif %}://{{ LMS_HOST }}/static/robbo-theme/images/Vector.svg"
MFE_CONFIG["LOGO_WHITE_URL"] = "{% if ENABLE_HTTPS %}https{% else %}http{% endif %}://{{ LMS_HOST }}/static/robbo-theme/images/logo-mfe-white.svg"
MFE_CONFIG["FAVICON_URL"] = "{% if ENABLE_HTTPS %}https{% else %}http{% endif %}://{{ LMS_HOST }}/favicon.ico"
"""

hooks.Filters.ENV_PATCHES.add_items(
    [
        ("mfe-lms-common-settings", _PARAGON_THEME_URLS),
        ("mfe-lms-development-settings", _PATCH_MFE_DEV),
        ("mfe-lms-production-settings", _PATCH_MFE_PROD),
    ]
)

# Indigo header/footer ship fixed colors; override via CSS bundled at MFE image build.
# Context path is plugins/mfe/build/mfe (same dir as Dockerfile).
_ROBBO_MFE_ENTRY_SCSS = {
    "authn": "src/index.scss",
    "learner-dashboard": "src/App.scss",
    "learning": "src/index.scss",
    "profile": "src/index.scss",
    "account": "src/index.scss",
    "discussions": "src/index.scss",
}


def _pre_npm_build_patch(entry_scss: str) -> str:
    return f"""
COPY robbo-mfe-shell.css /openedx/app/src/robbo-mfe-shell.css
RUN grep -qF 'robbo-mfe-shell.css' /openedx/app/{entry_scss} 2>/dev/null || printf '%s\\n' '@import "./robbo-mfe-shell.css";' >> /openedx/app/{entry_scss}
"""


for _name, _entry in _ROBBO_MFE_ENTRY_SCSS.items():
    hooks.Filters.ENV_PATCHES.add_item(
        (f"mfe-dockerfile-pre-npm-build-{_name}", _pre_npm_build_patch(_entry)),
        priority=hooks.priorities.LOW,
    )
