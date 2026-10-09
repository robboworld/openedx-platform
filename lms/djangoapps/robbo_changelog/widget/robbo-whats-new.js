/**
 * Copyright (C) 2026 Robbo <https://robbo.ru>
 * SPDX-License-Identifier: AGPL-3.0-only
 *
 * Part of the Robbo Open edX distribution (site changelog). See NOTICE at repository root.
 *
 * «Что нового» header button: news icon, unread counter, panel with the latest changes.
 * One implementation for every header: the LMS serves this file at
 * /api/robbo/v1/whats-new/widget.js to LMS pages and all MFEs; data comes from the
 * robbo_changelog API on the LMS session (guests get 401, accounts not activated yet 403: no button). Studio's Mako
 * pages load the same file from Studio, which serves a copy of the API (no cross-origin calls).
 *
 *   RobboWhatsNew.mount(container, {lmsUrl, lang, variant})
 *       lmsUrl — host of the API (default: this page's origin); links in the panel come from the API.
 *   <span data-robbo-whats-new data-lms-url data-lang data-variant> mounts itself (LMS and Studio pages).
 *
 * variant: "on-dark" — white icon for the green Robbo header (default); "on-light" — white headers.
 */
(function () {
  'use strict';

  if (window.RobboWhatsNew) {
    return;
  }

  var API = '/api/robbo/v1/whats-new/';
  var STYLE_ID = 'robbo-wn-style';
  var NARROW_QUERY = '(max-width: 575.98px)';
  var REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)';
  var CLOSE_DELAY = 160;
  var counter = 0;

  function svg(paths, size) {
    return '<svg viewBox="0 0 24 24" width="' + size + '" height="' + size + '" aria-hidden="true" focusable="false" '
      + 'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
      + paths + '</svg>';
  }

  var ICON_NEWS = svg('<path d="M5 5h11a1 1 0 011 1v12a2 2 0 002 2H6a2 2 0 01-2-2V6a1 1 0 011-1z"/>'
    + '<path d="M17 9h2a1 1 0 011 1v8a2 2 0 01-2 2"/><path d="M7.5 9h6M7.5 12.5h6M7.5 16h3.5"/>', 20);
  var ICON_CLOSE = svg('<path d="M6 6l12 12M18 6L6 18"/>', 18);
  var ICON_ARROW = svg('<path d="M5 12h14M13 6l6 6-6 6"/>', 16);
  var ICON_DONE = svg('<path d="M20 6L9 17l-5-5"/>', 28);
  var KIND_ICONS = {
    important: svg('<path d="M10.3 4.2L2.9 17a2 2 0 001.7 3h14.8a2 2 0 001.7-3L13.7 4.2a2 2 0 00-3.4 0z"/>'
      + '<path d="M12 9.5v4"/><path d="M12 17h.01"/>', 16),
    'new': svg('<path d="M12 3.5l1.8 4.9 4.9 1.8-4.9 1.8L12 16.9l-1.8-4.9-4.9-1.8 4.9-1.8z"/>'
      + '<path d="M18.5 15.5l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7z"/>', 16),
    improved: svg('<path d="M4 16l5-5 4 4 7-7"/><path d="M14 8h6v6"/>', 16),
    fixed: svg('<path d="M14.7 6.3a4 4 0 00-5.4 5.4L4 17v3h3l5.3-5.3a4 4 0 005.4-5.4l-2.5 2.5-2.3-.6-.6-2.3z"/>', 16),
  };

  // Plain CSS (no build step). The panel lives in <body>, so every rule names its own class and
  // sets margins, fonts and colours explicitly against host styles (LMS legacy, Paragon, Studio).
  // Sizes are px, not rem: legacy Studio pages set `html { font-size: 62.5% }`.
  // Palette — ROBBO brand: green #00af41, coal #383838, grey #989898, white. Kind and audience colours
  // are an owner-approved exception, only inside «Что нового» (.cursor/rules/site-changelog.mdc).
  var CSS = [
    '.robbo-wn{--robbo-wn-green:#00af41;--robbo-wn-green-dark:#007e2f;',
    'display:inline-flex;align-items:center;flex:0 0 auto;position:relative;vertical-align:middle}',
    '.robbo-wn[hidden]{display:none}',
    '.robbo-wn.robbo-wn .robbo-wn__button{appearance:none;-webkit-appearance:none;background:transparent;',
    'background-image:none;border:1px solid currentColor;border-radius:999px;box-shadow:none;box-sizing:border-box;',
    'color:#fff;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;',
    'height:calc(21.6px + 14px);width:calc(21.6px + 14px);margin:0;min-width:0;padding:0;position:relative;line-height:1;text-decoration:none;',
    'transition:background-color .15s ease,color .15s ease,transform .15s ease}',
    '.robbo-wn--on-light.robbo-wn .robbo-wn__button{color:var(--robbo-wn-green)}',
    '.robbo-wn.robbo-wn .robbo-wn__button:hover{background:rgba(255,255,255,.18)}',
    '.robbo-wn.robbo-wn .robbo-wn__button:active{transform:scale(.94)}',
    '.robbo-wn.robbo-wn .robbo-wn__button[aria-expanded="true"]{background:#fff;border-color:#fff;',
    'color:var(--robbo-wn-green-dark)}',
    '.robbo-wn--on-light.robbo-wn .robbo-wn__button:hover{background:rgba(0,175,65,.08)}',
    '.robbo-wn--on-light.robbo-wn .robbo-wn__button[aria-expanded="true"]{background:var(--robbo-wn-green);',
    'border-color:var(--robbo-wn-green);color:#fff}',
    '.robbo-wn.robbo-wn .robbo-wn__button:focus{outline:none}',
    '.robbo-wn.robbo-wn .robbo-wn__button:focus-visible{outline:2px solid #fff;outline-offset:3px}',
    '.robbo-wn--on-light.robbo-wn .robbo-wn__button:focus-visible{outline-color:var(--robbo-wn-green)}',
    '.robbo-wn .robbo-wn__button svg{display:block;pointer-events:none}',
    '.robbo-wn .robbo-wn__badge{animation:robbo-wn-pop .25s ease-out;background:#fff;border-radius:999px;',
    'box-shadow:0 0 0 2px var(--robbo-wn-green),0 1px 3px rgba(0,0,0,.25);box-sizing:border-box;',
    'color:var(--robbo-wn-green-dark);font:800 11px/18px ',
    'var(--robbo-font-body,"Proxima Nova","ProximaNova",Helvetica,Arial,sans-serif);height:18px;',
    'min-width:18px;padding:0 4px;pointer-events:none;position:absolute;right:-7px;text-align:center;',
    'top:-7px}',
    '.robbo-wn--on-light .robbo-wn__badge{background:var(--robbo-wn-green);box-shadow:0 0 0 2px #fff;color:#fff}',
    '.robbo-wn .robbo-wn__badge[hidden]{display:none}',
    '@keyframes robbo-wn-pop{from{opacity:0;transform:scale(.4)}to{opacity:1;transform:scale(1)}}',

    '.robbo-wn-panel{--robbo-wn-green:#00af41;--robbo-wn-green-dark:#007e2f;--robbo-wn-green-tint:#effaf3;',
    '--robbo-wn-green-soft:#dcf3e4;--robbo-wn-coal:#383838;--robbo-wn-text:#1f2328;--robbo-wn-muted:#5f6670;',
    '--robbo-wn-grey:#989898;--robbo-wn-line:#e8eaed;--robbo-wn-surface:#fff;--robbo-wn-hover:#f6f7f8;',
    '--robbo-wn-chip:#f1f2f4;--robbo-wn-action:#fffbea;--robbo-wn-action-line:#f2d75c;',
    '--robbo-wn-caret:20px;--robbo-wn-head:#e3f6ea;--robbo-wn-new:#00af41;--robbo-wn-new-ink:#00873a;--robbo-wn-new-bg:#e3f6ea;',
    '--robbo-wn-important:#e5484d;--robbo-wn-important-ink:#c4282d;--robbo-wn-important-bg:#ffeaea;',
    '--robbo-wn-improved:#2f6fdf;--robbo-wn-improved-ink:#2457b8;--robbo-wn-improved-bg:#e8effc;',
    '--robbo-wn-fixed:#ef7d0f;--robbo-wn-fixed-ink:#b85a00;--robbo-wn-fixed-bg:#fff1e0;',
    '--robbo-wn-authors-ink:#5b3cc4;--robbo-wn-authors-bg:#efeaff;--robbo-wn-teachers-ink:#0e7a74;',
    '--robbo-wn-teachers-bg:#ddf3f1;--robbo-wn-admins-ink:#b4234a;--robbo-wn-admins-bg:#fde7ee;',
    'background:var(--robbo-wn-surface);border:1px solid var(--robbo-wn-line);border-radius:16px;',
    'box-shadow:0 18px 48px rgba(17,24,39,.18),0 2px 6px rgba(17,24,39,.08);box-sizing:border-box;',
    'color:var(--robbo-wn-text);display:flex;flex-direction:column;',
    'font-family:var(--robbo-font-body,"Proxima Nova","ProximaNova",Helvetica,Arial,sans-serif);font-size:16px;',
    'line-height:1.5;max-width:calc(100vw - 16px);opacity:0;position:fixed;text-align:left;',
    'transform:translateY(-6px) scale(.98);transform-origin:top right;',
    'transition:opacity .16s ease,transform .16s ease;width:400px;z-index:1060}',
    '.robbo-wn-panel.is-open{opacity:1;transform:none}',
    '.robbo-wn-panel[hidden]{display:none}',
    '.robbo-wn-panel *{box-sizing:border-box}',
    '.robbo-wn-panel .robbo-wn__caret{background:var(--robbo-wn-head);border-left:1px solid var(--robbo-wn-line);',
    'border-top:1px solid var(--robbo-wn-line);height:14px;left:var(--robbo-wn-caret);position:absolute;',
    'top:-7px;transform:rotate(45deg);width:14px}',
    '.robbo-wn-panel .robbo-wn__head{align-items:flex-start;display:flex;gap:12px;justify-content:space-between;',
    'background:linear-gradient(135deg,var(--robbo-wn-head) 0%,var(--robbo-wn-surface) 85%);',
    'border-radius:16px 16px 0 0;padding:16px 16px 14px 20px;position:relative}',
    '.robbo-wn-panel .robbo-wn__title{color:var(--robbo-wn-text);font-family:inherit;font-size:20px;',
    'font-style:normal;font-weight:800;letter-spacing:-.01em;line-height:1.25;margin:0;outline:none;padding:0;',
    'text-transform:none}',
    '.robbo-wn-panel .robbo-wn__summary{color:var(--robbo-wn-muted);font-size:14px;line-height:1.4;',
    'margin:2px 0 0;min-height:1.225em}',
    '.robbo-wn-panel .robbo-wn__summary.has-unread{color:var(--robbo-wn-green-dark);font-weight:700}',
    '.robbo-wn-panel.robbo-wn-panel .robbo-wn__close{align-items:center;appearance:none;-webkit-appearance:none;',
    'background:transparent;background-image:none;border:0;border-radius:999px;box-shadow:none;',
    'color:var(--robbo-wn-muted);cursor:pointer;display:inline-flex;flex:0 0 auto;height:40px;justify-content:center;',
    'margin:-4px -4px 0 0;padding:0;text-shadow:none;transition:background-color .15s ease;width:40px}',
    '.robbo-wn-panel.robbo-wn-panel .robbo-wn__close:hover{background:var(--robbo-wn-hover);color:var(--robbo-wn-text)}',
    '.robbo-wn-panel.robbo-wn-panel .robbo-wn__close:focus{outline:none}',
    '.robbo-wn-panel.robbo-wn-panel .robbo-wn__close:focus-visible{outline:2px solid var(--robbo-wn-green)}',
    '.robbo-wn-panel .robbo-wn__close svg{display:block}',
    '.robbo-wn-panel .robbo-wn__body{border-top:1px solid var(--robbo-wn-line);flex:1 1 auto;min-height:0;',
    'overflow-y:auto;overscroll-behavior:contain;padding:0 8px 8px;scrollbar-color:#d5d8dc transparent;',
    'scrollbar-width:thin}',
    '.robbo-wn-panel .robbo-wn__day + .robbo-wn__day{margin-top:4px}',
    '.robbo-wn-panel .robbo-wn__date{align-items:baseline;background:var(--robbo-wn-surface);color:var(--robbo-wn-text);',
    'display:flex;flex-wrap:wrap;font-family:inherit;font-size:13px;font-weight:800;gap:0 8px;',
    'letter-spacing:.04em;line-height:1.3;margin:0;padding:14px 12px 8px;position:sticky;',
    'text-transform:uppercase;top:0;z-index:1}',
    '.robbo-wn-panel .robbo-wn__version{color:var(--robbo-wn-grey);font-size:12px;font-weight:400;',
    'letter-spacing:0;text-transform:none}',
    '.robbo-wn-panel .robbo-wn__group{align-items:center;color:var(--robbo-wn-grey);display:flex;font-size:11px;',
    'font-weight:800;gap:6px;letter-spacing:.06em;line-height:1.4;margin:6px 12px 4px;text-transform:uppercase}',
    '.robbo-wn-panel .robbo-wn__group::before{background:currentColor;border-radius:50%;content:"";height:7px;',
    'width:7px}',
    '.robbo-wn-panel .robbo-wn__group--major{color:var(--robbo-wn-new-ink)}',
    '.robbo-wn-panel .robbo-wn__group--notable{color:var(--robbo-wn-improved-ink)}',
    '.robbo-wn-panel .robbo-wn__entries{display:flex;flex-direction:column;gap:2px;list-style:none;margin:0;',
    'padding:0}',
    '.robbo-wn-panel .robbo-wn__entry{border-radius:12px;display:flex;gap:12px;margin:0;padding:10px 12px;',
    'position:relative;transition:background-color .15s ease}',
    '.robbo-wn-panel .robbo-wn__entry:hover{background:var(--robbo-wn-hover)}',
    '.robbo-wn-panel .robbo-wn__entry.is-unread{background:var(--robbo-wn-green-tint)}',
    '.robbo-wn-panel .robbo-wn__kind{align-items:center;border-radius:10px;display:inline-flex;flex:0 0 auto;',
    'height:32px;justify-content:center;margin-top:1px;width:32px}',
    '.robbo-wn-panel .robbo-wn__kind svg{display:block}',
    '.robbo-wn-panel .robbo-wn__entry--important{--robbo-wn-kind-ink:var(--robbo-wn-important-ink);',
    '--robbo-wn-kind-bg:var(--robbo-wn-important-bg);box-shadow:inset 3px 0 0 var(--robbo-wn-important)}',
    '.robbo-wn-panel .robbo-wn__entry--new{--robbo-wn-kind-ink:var(--robbo-wn-new-ink);--robbo-wn-kind-bg:var(--robbo-wn-new-bg)}',
    '.robbo-wn-panel .robbo-wn__entry--improved{--robbo-wn-kind-ink:var(--robbo-wn-improved-ink);',
    '--robbo-wn-kind-bg:var(--robbo-wn-improved-bg)}',
    '.robbo-wn-panel .robbo-wn__entry--fixed{--robbo-wn-kind-ink:var(--robbo-wn-fixed-ink);--robbo-wn-kind-bg:var(--robbo-wn-fixed-bg)}',
    '.robbo-wn-panel .robbo-wn__kind{background:var(--robbo-wn-kind-bg);color:var(--robbo-wn-kind-ink)}',
    '.robbo-wn-panel .robbo-wn__meta-kind{color:var(--robbo-wn-kind-ink);font-weight:700}',
    '.robbo-wn-panel .robbo-wn__entry--minor .robbo-wn__kind{border-radius:8px;height:26px;width:26px}',
    '.robbo-wn-panel .robbo-wn__content{flex:1 1 auto;min-width:0}',
    '.robbo-wn-panel .robbo-wn__entry-title{color:var(--robbo-wn-text);font-size:15px;font-weight:700;',
    'line-height:1.35;margin:0;overflow-wrap:anywhere}',
    '.robbo-wn-panel .robbo-wn__entry--major .robbo-wn__entry-title{font-size:16px;font-weight:800}',
    '.robbo-wn-panel .robbo-wn__entry--minor .robbo-wn__entry-title{font-size:14px;font-weight:600}',
    '.robbo-wn-panel .robbo-wn__dot{background:var(--robbo-wn-green);border-radius:50%;display:inline-block;',
    'height:8px;margin:0 6px 1px 0;vertical-align:middle;width:8px}',
    '.robbo-wn-panel .robbo-wn__text{color:var(--robbo-wn-muted);font-size:14px;line-height:1.5;margin:4px 0 0;',
    'overflow-wrap:anywhere}',
    '.robbo-wn-panel .robbo-wn__entry--minor .robbo-wn__text{font-size:13px}',
    '.robbo-wn-panel .robbo-wn__meta{align-items:center;color:var(--robbo-wn-grey);display:flex;flex-wrap:wrap;',
    'font-size:12px;gap:4px 8px;line-height:1.3;margin:8px 0 0}',
    '.robbo-wn-panel .robbo-wn__meta-sep{color:#c4c7cc}',
    '.robbo-wn-panel .robbo-wn__audience{background:var(--robbo-wn-coal);border-radius:999px;color:#fff;',
    'font-size:11px;font-weight:700;padding:2px 8px}',
    '.robbo-wn-panel .robbo-wn__audience--authors{background:var(--robbo-wn-authors-bg);color:var(--robbo-wn-authors-ink)}',
    '.robbo-wn-panel .robbo-wn__audience--teachers{background:var(--robbo-wn-teachers-bg);',
    'color:var(--robbo-wn-teachers-ink)}',
    '.robbo-wn-panel .robbo-wn__audience--platform_admins{background:var(--robbo-wn-admins-bg);',
    'color:var(--robbo-wn-admins-ink)}',
    '.robbo-wn-panel .robbo-wn__action{background:var(--robbo-wn-action);border:1px solid var(--robbo-wn-action-line);',
    'border-radius:10px;margin:8px 0 0;padding:8px 10px}',
    '.robbo-wn-panel .robbo-wn__action-title{color:var(--robbo-wn-coal);font-size:11px;font-weight:800;',
    'letter-spacing:.04em;margin:0;text-transform:uppercase}',
    '.robbo-wn-panel .robbo-wn__action .robbo-wn__text{color:var(--robbo-wn-text);margin-top:2px}',
    '.robbo-wn-panel .robbo-wn__image{border:1px solid var(--robbo-wn-line);border-radius:8px;display:block;',
    'height:auto;margin:8px 0 0;max-width:100%}',
    '.robbo-wn-panel a.robbo-wn__link{align-items:center;color:var(--robbo-wn-green-dark);display:inline-flex;',
    'font-size:13px;font-weight:700;gap:4px;margin:6px 0 0;min-height:28px;text-decoration:none}',
    '.robbo-wn-panel a.robbo-wn__link:hover{color:var(--robbo-wn-text);text-decoration:underline}',
    '.robbo-wn-panel a.robbo-wn__link svg,.robbo-wn-panel a.robbo-wn__all svg{transition:transform .15s ease}',
    '.robbo-wn-panel a.robbo-wn__link:hover svg,.robbo-wn-panel a.robbo-wn__all:hover svg{transform:translateX(2px)}',
    '.robbo-wn-panel .robbo-wn__foot{border-top:1px solid var(--robbo-wn-line);padding:8px}',
    '.robbo-wn-panel a.robbo-wn__all{align-items:center;border-radius:10px;color:var(--robbo-wn-green-dark);',
    'display:flex;font-size:15px;font-weight:700;gap:6px;justify-content:center;min-height:44px;',
    'text-decoration:none;transition:background-color .15s ease}',
    '.robbo-wn-panel a.robbo-wn__all:hover{background:var(--robbo-wn-green-tint);color:var(--robbo-wn-green-dark)}',
    '.robbo-wn-panel a.robbo-wn__link:focus-visible,.robbo-wn-panel a.robbo-wn__all:focus-visible{',
    'outline:2px solid var(--robbo-wn-green);outline-offset:2px}',
    '.robbo-wn-panel .robbo-wn__note{align-items:center;color:var(--robbo-wn-muted);display:flex;flex-direction:column;',
    'font-size:15px;gap:8px;padding:32px 16px;text-align:center}',
    '.robbo-wn-panel .robbo-wn__note p{margin:0}',
    '.robbo-wn-panel .robbo-wn__note svg{color:var(--robbo-wn-green)}',
    '.robbo-wn-panel .robbo-wn__skeleton{display:flex;gap:12px;padding:12px}',
    '.robbo-wn-panel .robbo-wn__skeleton i{animation:robbo-wn-shimmer 1.2s ease-in-out infinite;',
    'background:var(--robbo-wn-chip);border-radius:8px;display:block;height:12px}',
    '.robbo-wn-panel .robbo-wn__skeleton > i{border-radius:10px;flex:0 0 32px;height:32px}',
    '.robbo-wn-panel .robbo-wn__skeleton span{display:flex;flex:1 1 auto;flex-direction:column;gap:8px;',
    'padding-top:4px}',
    '.robbo-wn-panel .robbo-wn__skeleton span i:nth-child(1){width:70%}',
    '.robbo-wn-panel .robbo-wn__skeleton span i:nth-child(2){width:95%}',
    '.robbo-wn-panel .robbo-wn__skeleton span i:nth-child(3){width:45%}',
    '@keyframes robbo-wn-shimmer{50%{opacity:.45}}',
    '.robbo-wn-panel .robbo-wn__sr{border:0;clip:rect(0 0 0 0);height:1px;margin:-1px;overflow:hidden;padding:0;',
    'position:absolute;white-space:nowrap;width:1px}',
    '@media (prefers-reduced-motion:reduce){.robbo-wn-panel,.robbo-wn .robbo-wn__badge,',
    '.robbo-wn-panel .robbo-wn__skeleton i{animation:none;transition:none}}',
    'body.indigo-dark-theme .robbo-wn-panel{--robbo-wn-surface:#1b2a22;--robbo-wn-text:#f8f8f8;',
    '--robbo-wn-muted:#c8d5cd;--robbo-wn-line:#3a4a41;--robbo-wn-hover:#24382d;--robbo-wn-chip:#2c3b33;',
    '--robbo-wn-coal:#e5e7eb;--robbo-wn-green-dark:#86efac;--robbo-wn-green-tint:#173524;',
    '--robbo-wn-green-soft:#14532d;--robbo-wn-action:#2a2a1a;--robbo-wn-action-line:#6b5f22;--robbo-wn-head:#173524;',
    '--robbo-wn-new-ink:#86efac;--robbo-wn-new-bg:#14532d;--robbo-wn-improved-ink:#9cbcf5;--robbo-wn-improved-bg:#1e2f4d;',
    '--robbo-wn-important-ink:#ff9b9e;--robbo-wn-important-bg:#4a1d1f;',
    '--robbo-wn-fixed-ink:#ffb26b;--robbo-wn-fixed-bg:#45300f;--robbo-wn-authors-ink:#c7b6ff;--robbo-wn-authors-bg:#2f2552;',
    '--robbo-wn-teachers-ink:#8de0d8;--robbo-wn-teachers-bg:#163f3c;--robbo-wn-admins-ink:#ffa3bd;',
    '--robbo-wn-admins-bg:#4a1b29}',
    'body.indigo-dark-theme .robbo-wn-panel .robbo-wn__audience{color:#1b2a22}'
  ].join('');

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) {
      return;
    }
    var style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = CSS;
    document.head.appendChild(style);
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    if (text !== undefined && text !== null) {
      node.textContent = text;
    }
    return node;
  }

  function prefersReducedMotion() {
    return window.matchMedia(REDUCED_MOTION_QUERY).matches;
  }

  function request(state, path, method, token) {
    var headers = {Accept: 'application/json'};
    if (token) {
      headers['X-CSRFToken'] = token;
    }
    var url = state.lmsUrl + API + path + (method === 'GET' ? '?lang=' + encodeURIComponent(state.lang) : '');
    return fetch(url, {method: method, credentials: 'include', headers: headers}).then(function (response) {
      if (!response.ok) {
        var error = new Error('HTTP ' + response.status);
        error.status = response.status;
        throw error;
      }
      return response.json();
    });
  }

  function csrfToken(state) {
    return fetch(state.lmsUrl + '/csrf/api/v1/token', {credentials: 'include'})
      .then(function (response) { return response.json(); })
      .then(function (data) { return data.csrfToken; });
  }

  function setUnread(state, count, texts) {
    state.unread = count;
    state.badge.hidden = !count;
    state.badge.textContent = count > 9 ? '9+' : String(count || '');
    if (texts) {
      state.texts = texts;
    }
    var label = count && state.texts.button_unread
      ? state.texts.button_unread.replace('{count}', String(count))
      : (state.texts.title || state.button.getAttribute('aria-label'));
    state.button.setAttribute('aria-label', label);
    state.button.title = label;
  }

  function renderEntry(entry, texts) {
    var item = el('li', 'robbo-wn__entry robbo-wn__entry--' + entry.importance + ' robbo-wn__entry--' + entry.kind
      + (entry.unread ? ' is-unread' : ''));
    var kind = el('span', 'robbo-wn__kind robbo-wn__kind--' + entry.kind);
    kind.innerHTML = KIND_ICONS[entry.kind] || '';
    kind.title = entry.kind_label;
    item.appendChild(kind);

    var content = el('div', 'robbo-wn__content');
    var title = el('p', 'robbo-wn__entry-title');
    if (entry.unread) {
      title.appendChild(el('span', 'robbo-wn__dot')).setAttribute('aria-hidden', 'true');
      title.appendChild(el('span', 'robbo-wn__sr', texts.unread + ': '));
    }
    title.appendChild(document.createTextNode(entry.title));
    content.appendChild(title);
    (entry.paragraphs || []).forEach(function (paragraph) {
      content.appendChild(el('p', 'robbo-wn__text', paragraph));
    });
    if (entry.action) {
      var action = el('div', 'robbo-wn__action');
      action.appendChild(el('p', 'robbo-wn__action-title', texts.action));
      action.appendChild(el('p', 'robbo-wn__text', entry.action));
      content.appendChild(action);
    }
    if (entry.image_url) {
      var image = el('img', 'robbo-wn__image');
      image.src = entry.image_url;
      image.alt = entry.title;
      image.loading = 'lazy';
      content.appendChild(image);
    }
    if (entry.link_url) {
      var link = el('a', 'robbo-wn__link', entry.link_label);
      link.href = entry.link_url;
      link.insertAdjacentHTML('beforeend', ICON_ARROW);
      content.appendChild(link);
    }
    var meta = el('p', 'robbo-wn__meta');
    meta.appendChild(el('span', 'robbo-wn__meta-kind', entry.kind_label));
    meta.appendChild(el('span', 'robbo-wn__meta-sep', '·')).setAttribute('aria-hidden', 'true');
    meta.appendChild(el('span', null, entry.section_label));
    if (entry.audience_label) {
      meta.appendChild(el('span', 'robbo-wn__audience robbo-wn__audience--' + entry.audience, entry.audience_label));
    }
    content.appendChild(meta);
    item.appendChild(content);
    return item;
  }

  function renderNote(state, text, withIcon) {
    var note = el('div', 'robbo-wn__note');
    if (withIcon) {
      note.insertAdjacentHTML('beforeend', ICON_DONE);
    }
    note.appendChild(el('p', null, text));
    state.body.textContent = '';
    state.body.appendChild(note);
  }

  function renderSkeleton(state) {
    state.body.textContent = '';
    for (var i = 0; i < 3; i += 1) {
      var row = el('div', 'robbo-wn__skeleton');
      row.setAttribute('aria-hidden', 'true');
      row.innerHTML = '<i></i><span><i></i><i></i><i></i></span>';
      state.body.appendChild(row);
    }
    state.body.appendChild(el('p', 'robbo-wn__sr', state.texts.loading || '…'));
  }

  function renderPanel(state, data) {
    var texts = data.texts;
    state.title.textContent = texts.title;
    state.summary.textContent = texts.summary;
    state.summary.classList.toggle('has-unread', Boolean(data.unread));
    state.close.setAttribute('aria-label', texts.close);
    state.all.textContent = texts.all_changes;
    state.all.insertAdjacentHTML('beforeend', ICON_ARROW);
    state.all.href = data.page_url;
    if (!data.releases.length) {
      renderNote(state, texts.empty, true);
      return;
    }
    state.body.textContent = '';
    data.releases.forEach(function (release) {
      var day = el('section', 'robbo-wn__day');
      var date = el('h3', 'robbo-wn__date');
      date.appendChild(el('time', null, release.date_label)).setAttribute('datetime', release.date_iso);
      if (release.version) {
        date.appendChild(el('span', 'robbo-wn__version', texts.version + ' ' + release.version));
      }
      day.appendChild(date);
      release.groups.forEach(function (group) {
        if (release.groups.length > 1) {
          day.appendChild(el('p', 'robbo-wn__group robbo-wn__group--' + group.importance, group.heading));
        }
        var list = el('ul', 'robbo-wn__entries');
        group.entries.forEach(function (entry) {
          list.appendChild(renderEntry(entry, texts));
        });
        day.appendChild(list);
      });
      state.body.appendChild(day);
    });
  }

  function place(state) {
    var rect = state.button.getBoundingClientRect();
    var viewport = document.documentElement.clientWidth;
    var top = Math.round(rect.bottom + 10);
    var panel = state.panel;
    panel.style.top = top + 'px';
    if (window.matchMedia(NARROW_QUERY).matches) {
      panel.style.left = '8px';
      panel.style.right = '8px';
      panel.style.width = 'auto';
    } else {
      panel.style.left = 'auto';
      panel.style.right = Math.max(8, Math.round(viewport - rect.right - 4)) + 'px';
      panel.style.width = '';
    }
    panel.style.maxHeight = Math.max(240, window.innerHeight - top - 12) + 'px';
    // The caret points at the middle of the button wherever the panel ends up.
    var panelLeft = panel.getBoundingClientRect().left;
    panel.style.setProperty('--robbo-wn-caret', Math.round(rect.left + rect.width / 2 - panelLeft - 7) + 'px');
  }

  function buildPanel(state) {
    var panel = el('div', 'robbo-wn-panel');
    panel.id = 'robbo-wn-panel-' + state.id;
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-labelledby', panel.id + '-title');
    panel.hidden = true;
    panel.appendChild(el('span', 'robbo-wn__caret')).setAttribute('aria-hidden', 'true');

    var head = el('div', 'robbo-wn__head');
    var heading = el('div');
    state.title = el('h2', 'robbo-wn__title', state.texts.title);
    state.title.id = panel.id + '-title';
    state.title.tabIndex = -1;
    state.summary = el('p', 'robbo-wn__summary', '');
    heading.appendChild(state.title);
    heading.appendChild(state.summary);
    state.close = el('button', 'robbo-wn__close');
    state.close.type = 'button';
    state.close.innerHTML = ICON_CLOSE;
    state.close.setAttribute('aria-label', state.texts.close || 'Close');
    state.close.addEventListener('click', function () { close(state, true); });
    head.appendChild(heading);
    head.appendChild(state.close);

    state.body = el('div', 'robbo-wn__body');
    var foot = el('div', 'robbo-wn__foot');
    state.all = el('a', 'robbo-wn__all', state.texts.all_changes || '');
    state.all.href = state.lmsUrl + '/whats-new';
    foot.appendChild(state.all);
    panel.appendChild(head);
    panel.appendChild(state.body);
    panel.appendChild(foot);
    document.body.appendChild(panel);
    state.panel = panel;
    state.button.setAttribute('aria-controls', panel.id);
  }

  function onDocumentPointer(state, event) {
    if (!state.panel.contains(event.target) && !state.button.contains(event.target)) {
      close(state, false);
    }
  }

  function onKey(state, event) {
    if (event.key === 'Escape') {
      close(state, true);
    }
  }

  function open(state) {
    if (!state.panel) {
      buildPanel(state);
    }
    window.clearTimeout(state.closeTimer);
    state.isOpen = true;
    state.panel.hidden = false;
    state.button.setAttribute('aria-expanded', 'true');
    place(state);
    window.requestAnimationFrame(function () {
      if (state.isOpen) {
        state.panel.classList.add('is-open');
      }
    });
    document.addEventListener('pointerdown', state.listeners.pointer, true);
    document.addEventListener('keydown', state.listeners.key);
    window.addEventListener('resize', state.listeners.place);
    window.addEventListener('scroll', state.listeners.place, true);
    state.title.focus({preventScroll: true});
    if (state.loaded) {
      return;
    }
    renderSkeleton(state);
    request(state, 'entries', 'GET').then(function (data) {
      state.loaded = true;
      renderPanel(state, data);
      setUnread(state, data.unread, data.texts);
      if (data.unread) {
        csrfToken(state)
          .then(function (token) { return request(state, 'read', 'POST', token); })
          .then(function () { setUnread(state, 0); })
          .catch(function () { /* stays unread until the next open */ });
      }
    }).catch(function () {
      renderNote(state, state.texts.error || 'Error', false);
    });
  }

  function close(state, returnFocus) {
    if (!state.isOpen) {
      return;
    }
    state.isOpen = false;
    state.panel.classList.remove('is-open');
    state.button.setAttribute('aria-expanded', 'false');
    document.removeEventListener('pointerdown', state.listeners.pointer, true);
    document.removeEventListener('keydown', state.listeners.key);
    window.removeEventListener('resize', state.listeners.place);
    window.removeEventListener('scroll', state.listeners.place, true);
    state.closeTimer = window.setTimeout(function () {
      if (!state.isOpen) {
        state.panel.hidden = true;
      }
    }, prefersReducedMotion() ? 0 : CLOSE_DELAY);
    if (returnFocus) {
      state.button.focus();
    }
  }

  function mount(container, options) {
    if (!container || container.getAttribute('data-robbo-wn-mounted')) {
      return null;
    }
    options = options || {};
    ensureStyle();
    container.setAttribute('data-robbo-wn-mounted', '1');
    container.classList.add('robbo-wn', 'robbo-wn--' + (options.variant || 'on-dark'));
    counter += 1;
    var state = {
      id: counter,
      lmsUrl: String(options.lmsUrl || window.location.origin).replace(/\/+$/, ''),
      lang: String(options.lang || document.documentElement.lang || 'ru').toLowerCase().split('-')[0],
      texts: {},
      unread: 0,
      isOpen: false,
      loaded: false,
      closeTimer: null,
    };
    state.texts.title = state.lang === 'en' ? "What's new" : 'Что нового';
    state.listeners = {
      pointer: function (event) { onDocumentPointer(state, event); },
      key: function (event) { onKey(state, event); },
      place: function () { place(state); },
    };
    state.button = el('button', 'robbo-wn__button');
    state.button.type = 'button';
    state.button.innerHTML = ICON_NEWS;
    state.button.setAttribute('aria-haspopup', 'dialog');
    state.button.setAttribute('aria-expanded', 'false');
    state.badge = el('span', 'robbo-wn__badge');
    state.badge.setAttribute('aria-hidden', 'true');
    state.badge.hidden = true;
    state.button.appendChild(state.badge);
    state.button.addEventListener('click', function () {
      if (state.isOpen) {
        close(state, false);
      } else {
        open(state);
      }
    });
    setUnread(state, 0);
    container.hidden = true;
    container.appendChild(state.button);
    request(state, 'status', 'GET').then(function (data) {
      container.hidden = false;
      setUnread(state, data.unread, data.texts);
    }).catch(function () {
      // Guests (401), accounts not activated yet (403) and a broken API: no button at all.
      container.hidden = true;
    });
    return {
      unmount: function () {
        close(state, false);
        window.clearTimeout(state.closeTimer);
        if (state.panel) {
          state.panel.remove();
        }
        container.textContent = '';
        container.removeAttribute('data-robbo-wn-mounted');
      },
    };
  }

  function autoMount() {
    var nodes = document.querySelectorAll('[data-robbo-whats-new]:not([data-robbo-wn-mounted])');
    Array.prototype.forEach.call(nodes, function (node) {
      mount(node, {
        lmsUrl: node.getAttribute('data-lms-url'),
        lang: node.getAttribute('data-lang'),
        variant: node.getAttribute('data-variant'),
      });
    });
  }

  window.RobboWhatsNew = {mount: mount};

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', autoMount);
  } else {
    autoMount();
  }
}());
