"""
Tests for the modulestore.django module
"""

from pathlib import Path
from unittest.mock import Mock, patch

import django.utils.translation

from xmodule.modulestore.django import XBlockI18nService


def test_get_python_locale_with_atlas_oep58_translations(mock_modern_xblock):
    """
    Test that the XBlockI18nService.get_python_locale() method finds the atlas locale if it exists.

    More on OEP-58 and atlas pull: https://docs.openedx.org/en/latest/developers/concepts/oep58.html.
    """
    i18n_service = XBlockI18nService()
    block = mock_modern_xblock['modern_xblock']
    domain, locale_path = i18n_service.get_python_locale(block)

    assert locale_path.endswith('conf/plugins-locale/xblock.v1/my_modern_xblock'), 'Uses atlas locale if found.'
    assert domain == 'django', 'Uses django domain when atlas locale is found.'


@patch('importlib.resources.files', return_value=Path('/lib/my_legacy_xblock'))
def test_get_python_locale_with_bundled_translations(mock_modern_xblock):
    """
    Ensure that get_python_locale() falls back to XBlock internal translations if atlas translations weren't pulled.

    Pre-OEP-58 translations were stored in the `translations` directory of the XBlock which is
    accessible via the `importlib.resources.files` function.
    """
    i18n_service = XBlockI18nService()
    block = mock_modern_xblock['legacy_xblock']
    domain, path = i18n_service.get_python_locale(block)

    assert path == '/lib/my_legacy_xblock/translations', 'Backward compatible with pre-OEP-58.'
    assert domain == 'text', 'Use the legacy `text` domain for backward compatibility with old XBlocks.'


def test_i18n_service_translator_with_modern_xblock(mock_modern_xblock):
    """
    Ensure the XBlockI18nService uses the atlas translations if found.
    """
    block = mock_modern_xblock['modern_xblock']

    with django.utils.translation.override('fr'):
        i18n_service = XBlockI18nService(block)
        assert i18n_service.translator is django.utils.translation, 'French is not pulled by `mock_modern_xblock`.'

    with django.utils.translation.override('tr'):
        i18n_service = XBlockI18nService(block)
        assert i18n_service.translator is not django.utils.translation, 'Turkish is pulled by `mock_modern_xblock`.'


def test_i18n_service_missing_string_falls_back_to_django(mock_modern_xblock):
    """
    Robbo: a string missing from the Atlas catalog comes from the platform and theme catalogs, not in English.
    """
    block = mock_modern_xblock['modern_xblock']

    with django.utils.translation.override('tr'):
        i18n_service = XBlockI18nService(block)
        with patch.object(django.utils.translation, 'ngettext', return_value='from django') as mock_ngettext:
            assert i18n_service.ngettext('{n} missing item', '{n} missing items', 2) == 'from django'

    mock_ngettext.assert_called_once_with('{n} missing item', '{n} missing items', 2)
@patch('xmodule.modulestore.django.get_xblock_root_module_name', return_value='drag_and_drop_v2')
def test_js_catalog_prefers_bundled_robbo_locale(_mock_module_name, tmp_path):
    """
    Robbo: drag_and_drop_v2 in Russian uses the package catalog, because the Atlas one has no plural strings.
    """
    bundled_catalog = 'public/js/translations/ru/text.js'
    (tmp_path / 'public/js/translations/ru').mkdir(parents=True)
    (tmp_path / bundled_catalog).touch()
    block = Mock()

    with patch('xmodule.modulestore.django.resources.files', return_value=tmp_path):
        with django.utils.translation.override('ru'):
            url = XBlockI18nService().get_javascript_i18n_catalog_url(block)

    block.runtime.local_resource_url.assert_called_once_with(block, bundled_catalog)
    assert url == block.runtime.local_resource_url.return_value


@patch('xmodule.modulestore.django.get_javascript_i18n_file_path')
@patch('xmodule.modulestore.django.get_xblock_root_module_name', return_value='drag_and_drop_v2')
def test_js_catalog_without_bundled_file_stays_on_atlas(_mock_module_name, mock_file_path, tmp_path):
    """
    Robbo: a package without the bundled catalog keeps the upstream Atlas lookup.
    """
    mock_file_path.return_value.exists.return_value = False
    block = Mock()

    with patch('xmodule.modulestore.django.resources.files', return_value=tmp_path):
        with django.utils.translation.override('ru'):
            assert XBlockI18nService().get_javascript_i18n_catalog_url(block) is None

    block.runtime.local_resource_url.assert_not_called()


@patch('xmodule.modulestore.django.get_javascript_i18n_file_path')
@patch('xmodule.modulestore.django.get_xblock_root_module_name', return_value='drag_and_drop_v2')
def test_js_catalog_other_locale_stays_on_atlas(_mock_module_name, mock_file_path):
    """
    Robbo: English stays without the catalog, so the block keeps the global gettext and correct English plurals.
    """
    mock_file_path.return_value.exists.return_value = False
    block = Mock()

    with django.utils.translation.override('en'):
        assert XBlockI18nService().get_javascript_i18n_catalog_url(block) is None

    block.runtime.local_resource_url.assert_not_called()
