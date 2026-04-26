/**
 * nav.js — Universal sidebar injector for Agent Trading Expert webapp.
 *
 * Usage: add <script src="nav.js"></script> before </body> in every page.
 * The script finds .sidebar, populates it with the standard navigation,
 * detects the current page and marks the active item.
 * Also exposes window.toggleSidebar() used by the topbar toggle button.
 */
(function () {
  const NAV = [
    {
      section: 'Overview',
      items: [
        { icon: '◉', label: 'Overview',      href: 'index.html' },
      ],
    },
    {
      section: 'AI Pipeline',
      items: [
        { icon: '◈', label: 'Pipeline',      href: 'dashboard_pipeline.html' },
        { icon: '◎', label: 'Research',      href: 'dashboard_research.html' },
        { icon: '◐', label: 'Models',        href: 'dashboard_models.html' },
      ],
    },
    {
      section: 'Strategy',
      items: [
        { icon: '◆', label: 'Builder',       href: 'dashboard_builder.html' },
        { icon: '◑', label: 'Strategies',    href: 'strategy.html' },
        { icon: '◒', label: 'Backtest',      href: 'dashboard_backtest.html' },
        { icon: '◓', label: 'Validation',    href: 'dashboard_validation.html' },
      ],
    },
    {
      section: 'Execution',
      items: [
        { icon: '▶', label: 'Live Trading',  href: 'dashboard_live.html' },
        { icon: '▣', label: 'Execution',     href: 'dashboard_execution.html' },
        { icon: '▤', label: 'Performance',   href: 'dashboard_performance.html' },
        { icon: '◔', label: 'Risk',          href: 'dashboard_risk.html' },
      ],
    },
    {
      section: 'System',
      items: [
        { icon: '▧', label: 'Agents',        href: 'dashboard_agents.html' },
        { icon: '▨', label: 'Chat',          href: 'dashboard_with_chat.html' },
        { icon: '◇', label: 'Docs',          href: 'dashboard_documentation.html' },
      ],
    },
  ];

  function currentPage() {
    const path = window.location.pathname;
    return path.split('/').pop() || 'index.html';
  }

  function buildHTML(activePage) {
    let html = '';
    NAV.forEach(function (group) {
      html += '<div class="sidebar-section">';
      html += '<div class="sidebar-title">' + group.section + '</div>';
      group.items.forEach(function (item) {
        const isActive = item.href === activePage;
        html +=
          '<a href="' + item.href + '" class="sidebar-item' + (isActive ? ' active' : '') + '">' +
          '<span>' + item.icon + '</span> ' + item.label +
          '</a>';
      });
      html += '</div>';
    });
    html +=
      '<div class="status-indicator" style="margin-top:auto;">' +
      '<span class="status-dot"></span>' +
      '<span> SYSTEM ACTIVE</span>' +
      '</div>';
    return html;
  }

  var NAV_BADGE_CSS =
    '.nav-badge{margin-left:auto;background:var(--bg-tertiary);color:var(--text-muted);' +
    'border:1px solid var(--border);border-radius:2px;font-size:9px;padding:0 5px;' +
    'min-width:18px;text-align:center;flex-shrink:0;}';

  function injectBadgeStyle() {
    if (document.getElementById('nav-badge-style')) return;
    var s = document.createElement('style');
    s.id = 'nav-badge-style';
    s.textContent = NAV_BADGE_CSS;
    document.head.appendChild(s);
  }

  function inject() {
    const sidebar = document.querySelector('.sidebar');
    if (!sidebar) return;
    sidebar.innerHTML = buildHTML(currentPage());
    injectBadgeStyle();
    // Populate live badges via DU if available
    if (window.DU && window.DU.fetchSummary) {
      window.DU.fetchSummary().then(function (s) {
        if (s) window.DU.applyNavBadges(s);
      });
    }
  }

  window.toggleSidebar = function () {
    const terminal = document.querySelector('.terminal');
    if (terminal) terminal.classList.toggle('sidebar-collapsed');
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inject);
  } else {
    inject();
  }
})();
