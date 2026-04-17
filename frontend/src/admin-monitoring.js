/**
 * admin-monitoring.js — Dashboard shell (US-008)
 *
 * Wires up:
 *   - Time-range segmented control (1h/24h/7d) with auto-refresh polling.
 *   - A panel registry so US-009..US-013 can each call registerPanel(name, fn)
 *     to be invoked on every refresh.
 *   - fetchMetrics() helper that POSTs to /admin/api/metrics/cloudwatch via
 *     the shared SignalAuth.fetch() wrapper (carries Bearer token).
 *   - uPlot import so the bundle resolves correctly for panel stories.
 *
 * No panel content is rendered here; this story is the shell only.
 *
 * window.__monitoring__ is exposed for Playwright/DevTools introspection.
 */

import uPlot from 'uplot';
import 'uplot/dist/uPlot.min.css';

import './styles/admin-monitoring.css';
import SignalAuth from './auth.js';

// ── Time-range config ───────────────────────────────────────────────────
export const TIME_RANGES = ['1h', '24h', '7d'];
export const POLL_INTERVALS = {
  '1h': 10_000,
  '24h': 60_000,
  '7d': 60_000,
};

// ── Dashboard state ────────────────────────────────────────────────────
const state = {
  range: '1h',
  pollTimer: null,
};

// ── Panel registry ─────────────────────────────────────────────────────
// Each panel story (US-009+) calls registerPanel('name', fn). On every
// refreshAllPanels() tick we invoke every registered fn with the current range.
const panels = {};

function registerPanel(name, refreshFn) {
  if (typeof refreshFn !== 'function') {
    console.warn('[monitoring] registerPanel ignored — refreshFn must be a function', name);
    return;
  }
  panels[name] = refreshFn;
  // Fire once immediately on registration so late-joining panels still get data.
  try {
    refreshFn(state.range);
  } catch (err) {
    console.error('[monitoring] panel initial refresh failed', name, err);
  }
}

function refreshAllPanels() {
  console.debug('[monitoring] refresh triggered', state.range, new Date().toISOString());
  for (const name of Object.keys(panels)) {
    try {
      panels[name](state.range);
    } catch (err) {
      console.error('[monitoring] panel refresh failed', name, err);
    }
  }
}

// ── Time-range control ────────────────────────────────────────────────
export function setRange(range) {
  if (!TIME_RANGES.includes(range)) {
    console.warn('[monitoring] setRange ignored — unknown range', range);
    return;
  }
  state.range = range;

  if (state.pollTimer) {
    clearInterval(state.pollTimer);
    state.pollTimer = null;
  }
  const interval = POLL_INTERVALS[range];
  state.pollTimer = setInterval(refreshAllPanels, interval);

  // Visual / a11y state on buttons
  const buttons = document.querySelectorAll('.timerange-btn');
  buttons.forEach((btn) => {
    const active = btn.dataset.range === range;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-pressed', active ? 'true' : 'false');
  });

  refreshAllPanels();
}

function bindTimeRangeButtons() {
  const buttons = document.querySelectorAll('.timerange-btn');
  buttons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const range = btn.dataset.range;
      if (range) setRange(range);
    });
  });
}

// ── fetchMetrics helper ───────────────────────────────────────────────
/**
 * POST a CloudWatch GetMetricData batch through the admin API.
 *
 * @param {Array<Object>} queries — [{id, namespace, metric, dimensions, stat}, ...]
 * @param {string} [range] — '1h' | '24h' | '7d', defaults to current dashboard range.
 * @returns {Promise<Object>} series keyed by query id: {q1: {timestamps, values}, ...}
 */
export async function fetchMetrics(queries, range) {
  const rng = range || state.range;
  const res = await SignalAuth.fetch('/admin/api/metrics/cloudwatch', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ range: rng, queries }),
  });
  if (!res.ok) {
    throw new Error(`fetchMetrics ${res.status}`);
  }
  const data = await res.json();
  return data.series;
}

/**
 * GET /admin/api/metrics/cost — authoritative AWS + X-API spend figures.
 *
 * @param {string} [range] — '24h' | '7d' | '30d', defaults to '7d'.
 */
export async function fetchCost(range) {
  const rng = range || '7d';
  const res = await SignalAuth.fetch(
    `/admin/api/metrics/cost?range=${encodeURIComponent(rng)}`,
    { credentials: 'include' },
  );
  if (!res.ok) {
    throw new Error(`fetchCost ${res.status}`);
  }
  return res.json();
}

// ── Summary counter (placeholder wiring for US-013) ───────────────────
function updateSummary(criticals, warnings) {
  const critEl = document.getElementById('mon-summary-crit');
  const warnEl = document.getElementById('mon-summary-warn');
  if (critEl) critEl.textContent = `${criticals} critical${criticals === 1 ? '' : 's'}`;
  if (warnEl) warnEl.textContent = `${warnings} warning${warnings === 1 ? '' : 's'}`;
}

// ── Public interface (window.__monitoring__) ──────────────────────────
window.__monitoring__ = {
  state,
  setRange,
  registerPanel,
  refreshAllPanels,
  panels,
  fetchMetrics,
  fetchCost,
  updateSummary,
  uPlot,
  TIME_RANGES,
  POLL_INTERVALS,
};

// ── Bootstrap ─────────────────────────────────────────────────────────
function boot() {
  // Init auth so Bearer tokens are attached to subsequent fetches. We don't
  // *block* on it — the page shell renders regardless, and panel stories will
  // retry on auth-change.
  try {
    SignalAuth.init();
    SignalAuth.onAuthChange(() => {
      refreshAllPanels();
    });
  } catch (err) {
    console.warn('[monitoring] SignalAuth.init failed', err);
  }

  bindTimeRangeButtons();
  // Kick off polling at the default range (1h / 10s).
  setRange(state.range);
  // Seed summary counter (no panels yet, so zero/zero).
  updateSummary(0, 0);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot);
} else {
  boot();
}

// uPlot is imported purely to verify the bundle resolves. We attach it to
// window.__monitoring__.uPlot (above) for panel stories to pick up; no chart
// is instantiated in US-008.
export { uPlot };
