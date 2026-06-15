from setuptools import setup

setup(
    name="robbo-mfe-branding",
    version="0.1.0",
    packages=["tutor_plugin_robbo_mfe_branding"],
    entry_points={
        "tutor.plugin.v1": [
            "robbo-mfe-branding = tutor_plugin_robbo_mfe_branding"
        ]
    },
    install_requires=["tutor>=16.0", "tutor-mfe"],
    include_package_data=True,
)
