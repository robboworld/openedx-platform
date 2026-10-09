/**
 * Robbo: instructor dashboard «Ответы в свободной форме» (edx-ora2 Backgrid listing).
 * Adds a hint button next to every counter in the summary row, applies Robbo labels
 * to the summary and the table header and counts units once in «Блоки».
 * Texts come from #robbo-ora-listing-config (lms/djangoapps/robbo_ora/instructor_listing.py);
 * styles — themes/robbo-theme/lms/static/sass/courseware/_robbo-instructor-ora.scss.
 * edx-ora2 rebuilds the grids on every refresh, so the DOM is re-enhanced on mutation.
 */
(function () {
  'use strict';

  var configEl = document.getElementById('robbo-ora-listing-config');
  var root = document.querySelector('.open-response-assessment-block');
  if (!configEl || !root || root.dataset.robboHints) {
    return;
  }
  root.dataset.robboHints = '1';

  var config;
  try {
    config = JSON.parse(configEl.textContent);
  } catch (e) {
    return;
  }
  var hints = config.hints || {};
  var GAP = 6;
  var EDGE = 8;
  var tip = null;
  var tipOwner = null;
  var seq = 0;

  function columnOf(el, columns) {
    for (var i = 0; i < el.classList.length; i += 1) {
      if (Object.prototype.hasOwnProperty.call(columns, el.classList[i])) {
        return el.classList[i];
      }
    }
    return null;
  }

  function ensureTip() {
    if (!tip) {
      tip = document.createElement('div');
      tip.className = 'robbo-ora-tip';
      tip.setAttribute('aria-hidden', 'true');
      tip.hidden = true;
      document.body.appendChild(tip);
    }
    return tip;
  }

  function hideTip() {
    if (tip) {
      tip.hidden = true;
    }
    if (tipOwner) {
      tipOwner.setAttribute('aria-expanded', 'false');
      tipOwner = null;
    }
  }

  function showTip(button) {
    var el = ensureTip();
    if (tipOwner && tipOwner !== button) {
      tipOwner.setAttribute('aria-expanded', 'false');
    }
    tipOwner = button;
    button.setAttribute('aria-expanded', 'true');
    el.textContent = button.querySelector('.robbo-ora-hint__text').textContent;
    el.style.left = '0px';
    el.style.top = '0px';
    el.hidden = false;

    var anchor = button.getBoundingClientRect();
    var box = el.getBoundingClientRect();
    var viewportWidth = document.documentElement.clientWidth;
    var left = anchor.left + anchor.width / 2 - box.width / 2;
    left = Math.max(EDGE, Math.min(left, viewportWidth - box.width - EDGE));
    var top = anchor.bottom + GAP;
    if (top + box.height > window.innerHeight - EDGE && anchor.top - GAP - box.height >= EDGE) {
      top = anchor.top - GAP - box.height;
    }
    el.style.left = Math.round(left) + 'px';
    el.style.top = Math.round(top) + 'px';
  }

  function hintButton(column, label) {
    var button = document.createElement('button');
    var description = document.createElement('span');
    var mark = document.createElement('span');
    seq += 1;
    button.type = 'button';
    button.className = 'robbo-ora-hint';
    button.setAttribute('aria-label', (config.hintButtonLabel || '{label}').replace('{label}', label));
    button.setAttribute('aria-expanded', 'false');
    button.setAttribute('aria-describedby', 'robbo-ora-hint-' + seq);
    mark.setAttribute('aria-hidden', 'true');
    mark.textContent = '?';
    description.id = 'robbo-ora-hint-' + seq;
    description.className = 'robbo-ora-hint__text';
    description.textContent = hints[column];
    button.appendChild(mark);
    button.appendChild(description);

    button.addEventListener('mouseenter', function () { showTip(button); });
    button.addEventListener('mouseleave', hideTip);
    button.addEventListener('focus', function () { showTip(button); });
    button.addEventListener('blur', hideTip);
    button.addEventListener('click', function () { showTip(button); });
    return button;
  }

  function firstTextNode(el) {
    for (var node = el.firstChild; node; node = node.nextSibling) {
      if (node.nodeType === Node.TEXT_NODE && node.nodeValue.trim()) {
        return node;
      }
    }
    return null;
  }

  function enhanceSummary() {
    var titles = root.querySelectorAll('.open-response-assessment-summary td .ora-summary-title');
    Array.prototype.forEach.call(titles, function (title) {
      var column = columnOf(title.parentNode, hints);
      if (!column || title.dataset.robboHint) {
        return;
      }
      title.dataset.robboHint = '1';
      var label = (config.summaryLabels && config.summaryLabels[column]) || title.textContent.trim();
      // The last word and the hint never wrap apart.
      var split = label.lastIndexOf(' ');
      var tail = document.createElement('span');
      tail.className = 'robbo-ora-hint-tail';
      tail.textContent = label.slice(split + 1);
      tail.appendChild(hintButton(column, label));
      title.textContent = label.slice(0, split + 1);
      title.appendChild(tail);
    });
  }

  function relabelHeader() {
    var labels = config.tableLabels || {};
    var cells = root.querySelectorAll('.open-response-assessment-main-table thead th');
    Array.prototype.forEach.call(cells, function (cell) {
      var column = columnOf(cell, labels);
      var sortButton = cell.querySelector('button');
      var text = column && sortButton && firstTextNode(sortButton);
      if (text && text.nodeValue !== labels[column]) {
        text.nodeValue = labels[column];
      }
    });
  }

  function translateLinks() {
    var texts = config.linkTexts || {};
    var links = root.querySelectorAll('.open-response-assessment-main-table a.staff-esg-link');
    Array.prototype.forEach.call(links, function (link) {
      var source = link.textContent.trim();
      if (Object.prototype.hasOwnProperty.call(texts, source)) {
        link.textContent = texts[source];
        link.title = texts[source];
      }
    });
  }

  // edx-ora2 counts one unit per assignment; count distinct units instead.
  function countUnits() {
    var value = root.querySelector('.open-response-assessment-summary td.parent_name .ora-summary-value');
    var items = document.getElementById('open-response-assessment-items');
    if (!value || !items || value.dataset.robboCount) {
      return;
    }
    value.dataset.robboCount = '1';
    try {
      var units = {};
      JSON.parse(items.textContent).forEach(function (item) { units[item.parent_id] = true; });
      var count = String(Object.keys(units).length);
      value.textContent = count;
      value.title = count;
    } catch (e) {
      // keep the edx-ora2 value
    }
  }

  function enhance() {
    if (tipOwner && !document.body.contains(tipOwner)) {
      hideTip();
    }
    countUnits();
    enhanceSummary();
    relabelHeader();
    translateLinks();
  }

  var scheduled = false;
  new MutationObserver(function () {
    if (scheduled) {
      return;
    }
    scheduled = true;
    window.requestAnimationFrame(function () {
      scheduled = false;
      enhance();
    });
  }).observe(root, { childList: true, subtree: true });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && tipOwner) {
      hideTip();
    }
  });
  document.addEventListener('pointerdown', function (event) {
    if (tipOwner && !tipOwner.contains(event.target)) {
      hideTip();
    }
  });
  window.addEventListener('scroll', hideTip, true);
  window.addEventListener('resize', hideTip);

  enhance();
}());
