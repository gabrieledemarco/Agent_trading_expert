(function () {
  'use strict';

  const REFRESH_MS = 30000;

  function asNumber(value, fallback = 0) {
    const n = Number(value);
    return Number.isFinite(n) ? n : fallback;
  }

  function formatCurrency(value) {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 0,
    }).format(asNumber(value));
  }

  function formatPercent(value, decimals = 2) {
    const n = asNumber(value) * (Math.abs(asNumber(value)) <= 1 ? 100 : 1);
    const sign = n > 0 ? '+' : '';
    return `${sign}${n.toFixed(decimals)}%`;
  }

  async function fetchJson(path) {
    const response = await fetch(path, {
      method: 'GET',
      headers: { 'Accept': 'application/json' },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status} on ${path}`);
    }

    return response.json();
  }

  function setText(id, value) {
    const node = document.getElementById(id);
    if (node) {
      node.textContent = value;
    }
  }

  function setBadgeByText(labelText, value) {
    document.querySelectorAll('.sidebar-item').forEach((item) => {
      if (!item.textContent.includes(labelText)) return;
      const badge = item.querySelector('.badge');
      if (badge) {
        badge.textContent = String(value);
      }
    });
  }

  function updateSummaryWidgets(summary, strategies) {
    const totalStrategies = strategies.length;
    const activeStrategies = strategies.filter((s) => String(s.status || '').toUpperCase() === 'APPROVED').length;

    setBadgeByText('Research', asNumber(summary.research_papers));
    setBadgeByText('Strategies', totalStrategies);
    setBadgeByText('Agents', 6);

    setText('portfolioValue', formatCurrency(summary.current_equity));
    setText('totalCapital', formatCurrency(summary.current_equity));
    setText('totalReturn', formatPercent(summary.total_return));
    setText('portfolioSharpe', asNumber(summary.sharpe_ratio).toFixed(2));
    setText('activeStrategies', `${activeStrategies}/${Math.max(totalStrategies, activeStrategies)}`);

    setText('kpiTotalTrades', String(asNumber(summary.total_trades)));
    setText('kpiValidatedModels', String(asNumber(summary.models_validated)));
  }

  async function refreshDashboardData() {
    try {
      const [summary, strategiesResponse] = await Promise.all([
        fetchJson('/dashboard/summary'),
        fetchJson('/strategies').catch(() => ({ strategies: [] })),
      ]);

      const strategies = Array.isArray(strategiesResponse.strategies) ? strategiesResponse.strategies : [];
      updateSummaryWidgets(summary || {}, strategies);
      window.__dashboardDataLastUpdate = new Date().toISOString();
    } catch (error) {
      // Keep UI usable with existing static values when API is unavailable.
      window.__dashboardDataError = error.message;
    }
  }

  function init() {
    refreshDashboardData();
    setInterval(refreshDashboardData, REFRESH_MS);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.DashboardData = {
    refresh: refreshDashboardData,
    formatCurrency,
    formatPercent,
  };
})();
