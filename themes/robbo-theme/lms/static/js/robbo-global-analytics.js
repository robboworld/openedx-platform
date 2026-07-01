(function () {
  var filterForm = document.querySelector('[data-robbo-analytics-filter]');
  if (filterForm) {
    filterForm.addEventListener('change', function () {
      filterForm.submit();
    });
  }

  document.querySelectorAll('[data-robbo-analytics-course]').forEach(function (block) {
    var tabs = block.querySelectorAll('[data-robbo-tab]');
    var panels = block.querySelectorAll('[data-robbo-tab-panel]');

    tabs.forEach(function (tab) {
      tab.addEventListener('click', function () {
        var target = tab.getAttribute('data-robbo-tab');
        tabs.forEach(function (item) {
          var isActive = item === tab;
          item.classList.toggle('is-active', isActive);
          item.setAttribute('aria-selected', isActive ? 'true' : 'false');
        });
        panels.forEach(function (panel) {
          var isActive = panel.getAttribute('data-robbo-tab-panel') === target;
          panel.classList.toggle('is-active', isActive);
          panel.hidden = !isActive;
        });
      });
    });
  });
}());
