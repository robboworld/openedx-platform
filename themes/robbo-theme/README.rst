Robbo theme
===========

Comprehensive theme for Open edX (forked from Indigo), with **white surfaces** and **green** accents.

- LMS primary: ``#15803d``, light panels: ``#f0fdf4``
- Dark mode palette is green-tinted for consistency

Tutor: mount ``themes/robbo-theme`` to ``/openedx/themes/robbo-theme`` and set ``DEFAULT_SITE_THEME = "robbo-theme"`` (see project Tutor settings).

After changing Sass, rebuild theme assets (e.g. ``npm run compile-sass`` / ``watch-sass`` in the theme context).

If the UI still shows **indigo**, clear the site theme in Django admin (**Site configuration**) or ensure no ``SITE_THEME`` overrides the default.
