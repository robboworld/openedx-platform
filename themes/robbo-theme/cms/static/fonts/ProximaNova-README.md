# Proxima Nova (ROBBO brand)

WOFF files in this directory are used by `robbo-theme` (`_robbo-proxima-fonts.scss`) and served as LMS static:

`/static/robbo-theme/fonts/ProximaNova-Regular.woff`  
`/static/robbo-theme/fonts/ProximaNova-Extrabold.woff`

## Files

| File | Weight | Graphic guidelines |
|------|--------|-------------------|
| `ProximaNova-Regular.woff` | 400 | Proxima Nova Regular |
| `ProximaNova-Extrabold.woff` | 700 / 800 | Proxima Nova Extrabold |

## License

Proxima Nova is a **commercial** typeface (Mark Simonson Studio). ROBBO holds the brand license; do not redistribute these files outside authorized deployments. For upstream/Open edX forks, replace with a licensed copy or fall back to Helvetica per brand guidelines.

## MFE copies

Brand-aligned MFE overrides keep copies under `src/assets/fonts/` (authn, profile, …). After updating files here, sync:

```bash
THEME_FONTS=themes/robbo-theme/lms/static/fonts
for app in authn profile account learning learner-dashboard; do
  cp "$THEME_FONTS"/ProximaNova-*.woff \
    "../../mfe-overrides/frontend-app-$app/src/assets/fonts/"
done
```

(Path `THEME_FONTS` relative to `repos/openedx-platform`.)
