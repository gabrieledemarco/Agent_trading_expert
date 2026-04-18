/**
 * Trading API configuration — set TRADING_API_BASE to your Render server URL.
 *
 * Local dev  : leave empty string ""  (uses same-origin / relative URLs)
 * Production : set to your Render URL, e.g. "https://agent-trading-expert.onrender.com"
 *
 * This file is loaded before all dashboards so every fetch() call uses
 * the correct base URL whether the front-end is served from GitHub Pages
 * or from a local dev server.
 */
window.TRADING_API_BASE = (function () {
  // Auto-detect GitHub Pages: if the page origin includes 'github.io',
  // use the Render server URL.
  if (typeof window !== 'undefined' && window.location.hostname.endsWith('github.io')) {
    return 'https://agent-trading-expert.onrender.com';
  }
  // For local development (localhost / 127.0.0.1): use relative URLs.
  return '';
})();
