/**
 * dashboard_utils.js — shared formatters + global summary fetcher.
 * Exposes window.DU = { formatCurrency, formatPct, formatSharpe, fetchSummary }
 */
(function () {
  'use strict';

  var _cache = null;
  var _cacheTs = 0;
  var CACHE_TTL = 60000; // 60 s

  function formatCurrency(v) {
    var n = Number(v) || 0;
    return '$' + n.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
  }

  function formatPct(v, decimals) {
    var n = Number(v) || 0;
    var d = decimals != null ? decimals : 2;
    var sign = n >= 0 ? '+' : '';
    return sign + n.toFixed(d) + '%';
  }

  function formatSharpe(v) {
    return (Number(v) || 0).toFixed(2);
  }

  function fetchSummary() {
    var now = Date.now();
    if (_cache && (now - _cacheTs) < CACHE_TTL) {
      return Promise.resolve(_cache);
    }
    return fetch('/api/dashboard/summary')
      .then(function (r) { return r.json(); })
      .then(function (d) { _cache = d; _cacheTs = Date.now(); return d; })
      .catch(function () { return _cache || null; });
  }

  function applyNavBadges(summary) {
    if (!summary) return;
    var map = {
      'dashboard_research.html': summary.research  && summary.research.papers,
      'strategy.html':           summary.strategies && summary.strategies.total,
      'dashboard_agents.html':   summary.agents    && summary.agents.total,
      'dashboard_models.html':   summary.models    && summary.models.total,
    };
    document.querySelectorAll('.sidebar-item').forEach(function (el) {
      var href = el.getAttribute('href') || '';
      var page = href.split('/').pop();
      if (map[page] != null) {
        var existing = el.querySelector('.nav-badge');
        if (!existing) {
          var badge = document.createElement('span');
          badge.className = 'nav-badge';
          el.appendChild(badge);
        }
        el.querySelector('.nav-badge').textContent = map[page];
      }
    });
  }

  window.DU = {
    formatCurrency: formatCurrency,
    formatPct: formatPct,
    formatSharpe: formatSharpe,
    fetchSummary: fetchSummary,
    applyNavBadges: applyNavBadges,
  };
})();
