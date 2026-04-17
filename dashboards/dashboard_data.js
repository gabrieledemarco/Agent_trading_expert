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

  function candidateApiPaths(path) {
    const normalized = path.startsWith('/') ? path : `/${path}`;
    const candidates = [normalized];

    // Optional base path for reverse proxy deployments.
    if (window.__API_BASE_PATH && typeof window.__API_BASE_PATH === 'string') {
      const base = window.__API_BASE_PATH.replace(/\/$/, '');
      candidates.unshift(`${base}${normalized}`);
    }

    return [...new Set(candidates)];
  }

  async function fetchJson(path) {
    const candidates = candidateApiPaths(path);
    let lastError = null;

    for (const candidate of candidates) {
      try {
        const response = await fetch(candidate, {
          method: 'GET',
          headers: { Accept: 'application/json' },
        });

        if (!response.ok) {
          lastError = new Error(`HTTP ${response.status} on ${candidate}`);
          continue;
        }

        return response.json();
      } catch (error) {
        lastError = error;
      }
    }

    throw lastError || new Error(`Unable to fetch ${path}`);
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

  function uniqueAgentsCount(activities) {
    const names = new Set(
      (activities || [])
        .map((a) => a && a.agent_name)
        .filter(Boolean)
    );
    return names.size;
  }

  function updateSummaryWidgets(summary, strategies, activities) {
    const totalStrategies = strategies.length;
    const activeStrategies = strategies.filter((s) => String(s.status || '').toUpperCase() === 'APPROVED').length;

    setBadgeByText('Research', asNumber(summary.research_papers));
    setBadgeByText('Strategies', totalStrategies);

    const agentsCount = uniqueAgentsCount(activities);
    if (agentsCount > 0) {
      setBadgeByText('Agents', agentsCount);
    }

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
      const [summary, strategiesResponse, activityResponse] = await Promise.all([
        fetchJson('/dashboard/summary'),
        fetchJson('/strategies').catch(() => ({ strategies: [] })),
        fetchJson('/dashboard/agent-activity?limit=100').catch(() => ({ activities: [] })),
      ]);

      const strategies = Array.isArray(strategiesResponse.strategies) ? strategiesResponse.strategies : [];
      const activities = Array.isArray(activityResponse.activities) ? activityResponse.activities : [];
      updateSummaryWidgets(summary || {}, strategies, activities);
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
