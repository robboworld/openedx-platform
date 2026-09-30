# MathJax 2.7.5 (self-hosted, trimmed)

Source: `https://registry.npmjs.org/mathjax/-/mathjax-2.7.5.tgz`
(integrity `sha512-OzsJNitEHAJB3y4IIlPCAvS0yoXwYjlo2Y4kmm9K…`, Apache-2.0, see `LICENSE`).

Replaces the jsdelivr CDN in `mathjax_include.html`, `xblock_v2/xblock_iframe.html`,
`cms/js/require-config.js`, `pipeline_js/js/xmodule.js` and `discussion/mathjax_include.js`
(render-blocking and slow/unreachable for learners).

Kept only what `config=TeX-MML-AM_SVG` needs: `MathJax.js`, `config/TeX-MML-AM_SVG.js` (+ `config/local`),
`extensions/`, `jax/input/{TeX,MathML,AsciiMath}`, `jax/element`, `jax/output/SVG` (TeX fonts only),
`jax/output/{NativeMML,PreviewHTML}`, `localization/ru`. Dropped: `unpacked/`, `test/`, `fonts/`,
HTML-CSS/CommonHTML outputs (so the MathJax context menu cannot switch to those renderers).

Must be referenced by the unhashed URL (`STATIC_URL + js/vendor/mathjax-2.7.5/MathJax.js?config=…`):
MathJax locates its root by the `MathJax.js` file name.
