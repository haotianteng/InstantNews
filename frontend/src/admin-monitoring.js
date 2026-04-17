/**
 * admin-monitoring.js — Dashboard shell + panels.
 *
 * US-008 (shell): time-range control, panel registry, fetchMetrics/fetchCost.
 * US-009 (ingestion panel): per-source latency tiles + sparklines + drawer.
 *
 * window.__monitoring__ is exposed for Playwright/DevTools introspection.
 */

import uPlot from 'uplot';
import 'uplot/dist/uPlot.min.css';

import './styles/admin-monitoring.css';
import SignalAuth from './auth.js';
import {
  classifyStatus,
  formatSeconds,
  formatNumber,
  sparklineSvg,
  sumSeries,
  maxSeries,
  escapeHtml,
} from './admin-monitoring-helpers.js';

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
const panels = {};

function registerPanel(name, refreshFn) {
  if (typeof refreshFn !== 'function') {
    console.warn('[monitoring] registerPanel ignored — refreshFn must be a function', name);
    return;
  }
  panels[name] = refreshFn;
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

// ── fetchMetrics / fetchCost ──────────────────────────────────────────
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

function updateSummary(criticals, warnings) {
  const critEl = document.getElementById('mon-summary-crit');
  const warnEl = document.getElementById('mon-summary-warn');
  if (critEl) critEl.textContent = `${criticals} critical${criticals === 1 ? '' : 's'}`;
  if (warnEl) warnEl.textContent = `${warnings} warning${warnings === 1 ? '' : 's'}`;
}

// ── Central anomaly thresholds (consumed by panels + US-013) ──────────
const THRESHOLDS = {
  ingestion_p95_s: { warn: 60, crit: 180 },
  ai_queue_depth: { warn: 100, crit: 500 },
  x_rate_limit_pct: { warn: 50, crit: 80 },
  minimax_fallback_pct: { warn: 20, crit: 50 },
};

// ── US-009: Ingestion panel ───────────────────────────────────────────
const _ingestionState = {
  sources: null,
  lastSeries: {},
  pinnedSource: null,
};

async function _loadSourceList() {
  if (_ingestionState.sources) return _ingestionState.sources;
  try {
    const res = await SignalAuth.fetch('/api/sources', { credentials: 'include' });
    if (!res.ok) throw new Error(`/api/sources ${res.status}`);
    const data = await res.json();
    const list = (data.sources || []).map((s) => ({
      name: s.name,
      source_type: s.source_type
        || (/^Twitter\/@|^TruthSocial\/@/.test(s.name) ? 'social' : 'rss'),
    }));
    _ingestionState.sources = list;
    return list;
  } catch (err) {
    console.warn('[monitoring] failed to load /api/sources', err);
    _ingestionState.sources = [];
    return [];
  }
}

function _ingestionPanelBody() {
  return document.querySelector('.panel--ingestion .panel__body');
}

function _renderIngestionSkeleton(sources) {
  const body = _ingestionPanelBody();
  if (!body) return;
  if (!sources || sources.length === 0) {
    body.innerHTML = '<div class="placeholder" data-panel="ingestion">No sources configured</div>';
    return;
  }
  const tiles = sources.map((s) => {
    const badge = s.source_type === 'social' ? 'social' : 'rss';
    return `
      <article class="ingest-tile" data-source="${escapeHtml(s.name)}" data-source-type="${badge}" data-status="ok">
        <header class="ingest-tile__head">
          <span class="ingest-tile__name" title="${escapeHtml(s.name)}">${escapeHtml(s.name)}</span>
          <span class="ingest-tile__badge ingest-tile__badge--${badge}">${badge}</span>
        </header>
        <div class="ingest-tile__stats">
          <span class="ingest-tile__dot" aria-hidden="true"></span>
          <span class="ingest-tile__p50 num" data-numeric>–</span>
          <span class="ingest-tile__p95 num" data-numeric>p95 –</span>
        </div>
        <div class="ingest-tile__spark" aria-hidden="true"></div>
      </article>
    `;
  }).join('');
  body.innerHTML = `<div class="ingest-grid">${tiles}</div>`;

  body.querySelectorAll('.ingest-tile').forEach((tile) => {
    tile.addEventListener('click', () => {
      const name = tile.getAttribute('data-source');
      if (name) _openIngestionDrawer(name);
    });
  });
}

function _updateIngestionTile(name, { p50, p95, sparkValues }) {
  const body = _ingestionPanelBody();
  if (!body) return;
  const tile = body.querySelector(
    `.ingest-tile[data-source="${CSS.escape(name)}"]`,
  );
  if (!tile) return;

  const p50El = tile.querySelector('.ingest-tile__p50');
  const p95El = tile.querySelector('.ingest-tile__p95');
  const sparkEl = tile.querySelector('.ingest-tile__spark');

  if (p50El) p50El.textContent = formatSeconds(p50);
  if (p95El) p95El.textContent = `p95 ${formatSeconds(p95)}`;

  const status = classifyStatus(p50, 30, 120);
  tile.setAttribute('data-status', status);

  if (sparkEl) sparkEl.innerHTML = sparklineSvg(sparkValues || [], {
    width: 140, height: 24,
  });
}

function _sortIngestionTiles() {
  const body = _ingestionPanelBody();
  if (!body) return;
  const grid = body.querySelector('.ingest-grid');
  if (!grid) return;
  const tiles = Array.from(grid.querySelectorAll('.ingest-tile'));
  tiles.sort((a, b) => {
    const ap = Number(a.dataset.p95 || '0');
    const bp = Number(b.dataset.p95 || '0');
    return bp - ap;
  });
  for (const t of tiles) grid.appendChild(t);
}

async function _refreshIngestion(range) {
  const sources = await _loadSourceList();
  const body = _ingestionPanelBody();
  if (!body) return;
  if (!body.querySelector('.ingest-grid')) {
    _renderIngestionSkeleton(sources);
  }
  if (!sources.length) return;

  const queries = [];
  const meta = new Map();
  sources.forEach((s, idx) => {
    const items = `q${idx}i`;
    const p50 = `q${idx}p50`;
    const p95 = `q${idx}p95`;
    queries.push({
      id: items, namespace: 'InstantNews/Ingestion', metric: 'NewItems',
      dimensions: { Source: s.name, SourceType: s.source_type }, stat: 'Sum',
    });
    queries.push({
      id: p50, namespace: 'InstantNews/Ingestion', metric: 'IngestLatencySeconds',
      dimensions: { Source: s.name, SourceType: s.source_type }, stat: 'p50',
    });
    queries.push({
      id: p95, namespace: 'InstantNews/Ingestion', metric: 'IngestLatencySeconds',
      dimensions: { Source: s.name, SourceType: s.source_type }, stat: 'p95',
    });
    meta.set(items, { source: s.name, kind: 'items' });
    meta.set(p50, { source: s.name, kind: 'p50' });
    meta.set(p95, { source: s.name, kind: 'p95' });
  });

  let series = {};
  try {
    series = await fetchMetrics(queries, range);
  } catch (err) {
    console.warn('[monitoring] ingestion fetchMetrics failed', err);
    return;
  }

  const bySource = new Map();
  for (const [qid, { source, kind }] of meta.entries()) {
    const s = series[qid] || { values: [] };
    let bucket = bySource.get(source);
    if (!bucket) {
      bucket = { items: [], p50: [], p95: [] };
      bySource.set(source, bucket);
    }
    bucket[kind] = s.values || [];
  }

  const lastFinite = (arr) => {
    for (let i = arr.length - 1; i >= 0; i -= 1) {
      const v = Number(arr[i]);
      if (Number.isFinite(v)) return v;
    }
    return null;
  };

  for (const s of sources) {
    const b = bySource.get(s.name) || { items: [], p50: [], p95: [] };
    const p50 = lastFinite(b.p50);
    const p95 = lastFinite(b.p95) ?? maxSeries(b.p95);
    const spark = (b.items || []).slice(-60);

    _updateIngestionTile(s.name, { p50, p95, sparkValues: spark });
    const tile = _ingestionPanelBody().querySelector(
      `.ingest-tile[data-source="${CSS.escape(s.name)}"]`,
    );
    if (tile) {
      tile.dataset.p50 = p50 == null ? '' : String(p50);
      tile.dataset.p95 = p95 == null ? '' : String(p95);
    }
    _ingestionState.lastSeries[s.name] = b;
  }
  _sortIngestionTiles();
}

// ── Ingestion drawer (pin one source, 24h uPlot) ─────────────────────
function _ensureDrawer() {
  let drawer = document.querySelector('.mon-drawer');
  if (drawer) return drawer;
  drawer = document.createElement('aside');
  drawer.className = 'mon-drawer';
  drawer.setAttribute('aria-hidden', 'true');
  drawer.innerHTML = `
    <header class="mon-drawer__head">
      <h3 class="mon-drawer__title"></h3>
      <button type="button" class="mon-drawer__close" aria-label="Close">×</button>
    </header>
    <div class="mon-drawer__body"></div>
  `;
  document.body.appendChild(drawer);
  drawer.querySelector('.mon-drawer__close').addEventListener('click', _closeDrawer);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') _closeDrawer();
  });
  return drawer;
}

function _closeDrawer() {
  const drawer = document.querySelector('.mon-drawer');
  if (!drawer) return;
  drawer.classList.remove('mon-drawer--open');
  drawer.setAttribute('aria-hidden', 'true');
  _ingestionState.pinnedSource = null;
  const body = drawer.querySelector('.mon-drawer__body');
  if (body) body.innerHTML = '';
}

async function _openIngestionDrawer(sourceName) {
  const drawer = _ensureDrawer();
  if (_ingestionState.pinnedSource === sourceName) {
    _closeDrawer();
    return;
  }
  _ingestionState.pinnedSource = sourceName;
  drawer.querySelector('.mon-drawer__title').textContent = sourceName;
  drawer.setAttribute('aria-hidden', 'false');
  drawer.classList.add('mon-drawer--open');
  const body = drawer.querySelector('.mon-drawer__body');
  body.innerHTML = '<div class="mon-drawer__loading">Loading 24h latency…</div>';

  const sources = await _loadSourceList();
  const src = sources.find((s) => s.name === sourceName)
    || { name: sourceName, source_type: /^Twitter\/@|^TruthSocial\/@/.test(sourceName) ? 'social' : 'rss' };

  let series = {};
  try {
    series = await fetchMetrics([
      {
        id: 'p50', namespace: 'InstantNews/Ingestion', metric: 'IngestLatencySeconds',
        dimensions: { Source: src.name, SourceType: src.source_type }, stat: 'p50',
      },
      {
        id: 'p95', namespace: 'InstantNews/Ingestion', metric: 'IngestLatencySeconds',
        dimensions: { Source: src.name, SourceType: src.source_type }, stat: 'p95',
      },
    ], '24h');
  } catch (err) {
    body.innerHTML = `<div class="mon-drawer__error">Failed to load latency: ${escapeHtml(err && err.message || err)}</div>`;
    return;
  }

  const p50 = series.p50 || { timestamps: [], values: [] };
  const p95 = series.p95 || { timestamps: [], values: [] };
  if (!p50.timestamps.length && !p95.timestamps.length) {
    body.innerHTML = '<div class="mon-drawer__empty">No data in the last 24h.</div>';
    return;
  }

  const xs = p50.timestamps.length >= p95.timestamps.length ? p50.timestamps : p95.timestamps;
  const alignValues = (vals, ts) => {
    if (vals.length === xs.length) return vals;
    const out = new Array(xs.length).fill(null);
    for (let i = 0; i < ts.length; i += 1) {
      const xi = xs.indexOf(ts[i]);
      if (xi !== -1) out[xi] = vals[i];
    }
    return out;
  };
  const data = [
    xs,
    alignValues(p50.values, p50.timestamps),
    alignValues(p95.values, p95.timestamps),
  ];

  body.innerHTML = '<div class="mon-drawer__chart" style="width:100%;height:260px;"></div>';
  const host = body.querySelector('.mon-drawer__chart');
  const opts = {
    width: host.clientWidth || 520,
    height: 240,
    series: [
      {},
      { label: 'p50 latency (s)', stroke: '#3fb950', width: 1.5 },
      { label: 'p95 latency (s)', stroke: '#d29922', width: 1.5 },
    ],
    axes: [
      { stroke: '#8b949e' },
      { stroke: '#8b949e', label: 'seconds' },
    ],
    scales: { x: { time: true } },
  };
  try {
    // eslint-disable-next-line no-new
    new uPlot(opts, data, host);
  } catch (err) {
    body.innerHTML = `<div class="mon-drawer__error">Chart init failed: ${escapeHtml(err && err.message || err)}</div>`;
  }
}

// ── US-010: AI pipeline panel ─────────────────────────────────────────
const _aiState = { uplot: null };

function _aiPanelBody() {
  return document.querySelector('.panel--ai .panel__body');
}

function _renderAiSkeleton() {
  const body = _aiPanelBody();
  if (!body) return;
  if (body.querySelector('.ai-widgets')) return;
  body.innerHTML = `
    <div class="banner banner--warn ai-banner" hidden>MiniMax fallback active — check credits</div>
    <div class="ai-widgets">
      <div class="widget widget--queue-depth">
        <div class="widget__label">Queue depth</div>
        <div class="widget__value num" data-numeric>–</div>
        <div class="widget__spark" aria-hidden="true"></div>
      </div>
      <div class="widget widget--batch-duration">
        <div class="widget__label">Batch duration (p50 / p95)</div>
        <div class="widget__chart" style="width:100%;height:140px;"></div>
      </div>
      <div class="widget widget--fallback-chain">
        <div class="widget__label">Backend fallback chain</div>
        <svg class="fallback-donut" viewBox="0 0 42 42" width="120" height="120" aria-hidden="true">
          <circle class="donut-track" cx="21" cy="21" r="15.9155" fill="none"
            stroke="var(--bg-surface-3)" stroke-width="4"></circle>
          <circle data-backend="minimax" cx="21" cy="21" r="15.9155" fill="none"
            stroke="var(--green)" stroke-width="4" stroke-dasharray="0 100"
            stroke-dashoffset="25" transform="rotate(-90 21 21)"></circle>
          <circle data-backend="claude" cx="21" cy="21" r="15.9155" fill="none"
            stroke="var(--blue)" stroke-width="4" stroke-dasharray="0 100"
            stroke-dashoffset="25" transform="rotate(-90 21 21)"></circle>
          <circle data-backend="bedrock" cx="21" cy="21" r="15.9155" fill="none"
            stroke="var(--yellow)" stroke-width="4" stroke-dasharray="0 100"
            stroke-dashoffset="25" transform="rotate(-90 21 21)"></circle>
        </svg>
        <div class="fallback-legend">
          <span><i style="background:var(--green)"></i>minimax <b data-share="minimax">0%</b></span>
          <span><i style="background:var(--blue)"></i>claude <b data-share="claude">0%</b></span>
          <span><i style="background:var(--yellow)"></i>bedrock <b data-share="bedrock">0%</b></span>
        </div>
      </div>
    </div>
  `;
}

function _updateFallbackDonut(shares) {
  const body = _aiPanelBody();
  if (!body) return;
  const svg = body.querySelector('.fallback-donut');
  if (!svg) return;
  let offset = 0;
  for (const key of ['minimax', 'claude', 'bedrock']) {
    const share = Math.max(0, Math.min(1, Number(shares[key]) || 0));
    const pct = share * 100;
    const circle = svg.querySelector(`circle[data-backend="${key}"]`);
    if (circle) {
      circle.setAttribute('stroke-dasharray', `${pct.toFixed(2)} ${(100 - pct).toFixed(2)}`);
      circle.setAttribute('stroke-dashoffset', (25 - offset).toFixed(2));
    }
    const label = body.querySelector(`[data-share="${key}"]`);
    if (label) label.textContent = `${Math.round(pct)}%`;
    offset += pct;
  }
}

async function _refreshAI(range) {
  const body = _aiPanelBody();
  if (!body) return;
  _renderAiSkeleton();

  const queries = [
    { id: 'qd', namespace: 'InstantNews/AIPipeline', metric: 'QueueDepth',
      dimensions: {}, stat: 'Maximum' },
    { id: 'bd50', namespace: 'InstantNews/AIPipeline', metric: 'BatchDurationMs',
      dimensions: {}, stat: 'p50' },
    { id: 'bd95', namespace: 'InstantNews/AIPipeline', metric: 'BatchDurationMs',
      dimensions: {}, stat: 'p95' },
    { id: 'bmm', namespace: 'InstantNews/AIPipeline', metric: 'BackendChosen',
      dimensions: { Backend: 'minimax' }, stat: 'Sum' },
    { id: 'bcl', namespace: 'InstantNews/AIPipeline', metric: 'BackendChosen',
      dimensions: { Backend: 'claude' }, stat: 'Sum' },
    { id: 'bbr', namespace: 'InstantNews/AIPipeline', metric: 'BackendChosen',
      dimensions: { Backend: 'bedrock' }, stat: 'Sum' },
  ];

  let series = {};
  try {
    series = await fetchMetrics(queries, range);
  } catch (err) {
    console.warn('[monitoring] ai fetchMetrics failed', err);
    return;
  }

  const qd = series.qd || { timestamps: [], values: [] };
  const qdLast = (() => {
    for (let i = qd.values.length - 1; i >= 0; i -= 1) {
      const v = Number(qd.values[i]);
      if (Number.isFinite(v)) return v;
    }
    return null;
  })();
  const qdEl = body.querySelector('.widget--queue-depth .widget__value');
  const qdSpark = body.querySelector('.widget--queue-depth .widget__spark');
  if (qdEl) qdEl.textContent = qdLast == null ? '–' : formatNumber(qdLast);
  if (qdSpark) qdSpark.innerHTML = sparklineSvg((qd.values || []).slice(-60), {
    width: 160, height: 32, stroke: 'var(--blue)',
  });

  const bd50 = series.bd50 || { timestamps: [], values: [] };
  const bd95 = series.bd95 || { timestamps: [], values: [] };
  const xs = bd50.timestamps.length >= bd95.timestamps.length
    ? bd50.timestamps : bd95.timestamps;
  const align = (vals, ts) => {
    if (vals.length === xs.length) return vals;
    const out = new Array(xs.length).fill(null);
    for (let i = 0; i < ts.length; i += 1) {
      const xi = xs.indexOf(ts[i]);
      if (xi !== -1) out[xi] = vals[i];
    }
    return out;
  };
  const chartHost = body.querySelector('.widget--batch-duration .widget__chart');
  if (chartHost && xs.length > 0) {
    const data = [
      xs,
      align(bd50.values, bd50.timestamps),
      align(bd95.values, bd95.timestamps),
    ];
    if (_aiState.uplot) {
      try { _aiState.uplot.destroy(); } catch (_e) { /* noop */ }
      _aiState.uplot = null;
    }
    const opts = {
      width: chartHost.clientWidth || 320,
      height: 140,
      series: [
        {},
        { label: 'p50 ms', stroke: '#3fb950', width: 1.25 },
        { label: 'p95 ms', stroke: '#d29922', width: 1.25 },
      ],
      axes: [
        { stroke: '#8b949e' },
        { stroke: '#8b949e' },
      ],
      scales: { x: { time: true } },
      legend: { show: false },
    };
    try {
      _aiState.uplot = new uPlot(opts, data, chartHost);
    } catch (err) {
      console.warn('[monitoring] batch duration uplot failed', err);
    }
  } else if (chartHost) {
    chartHost.innerHTML = '<div class="widget__empty">No data</div>';
  }

  const bmm = sumSeries((series.bmm || {}).values);
  const bcl = sumSeries((series.bcl || {}).values);
  const bbr = sumSeries((series.bbr || {}).values);
  const total = bmm + bcl + bbr;
  const shares = total > 0
    ? { minimax: bmm / total, claude: bcl / total, bedrock: bbr / total }
    : { minimax: 0, claude: 0, bedrock: 0 };
  _updateFallbackDonut(shares);

  const banner = body.querySelector('.ai-banner');
  if (banner) {
    if (total > 0 && shares.minimax < 0.8) {
      banner.removeAttribute('hidden');
    } else {
      banner.setAttribute('hidden', '');
    }
  }
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
  THRESHOLDS,
  refreshIngestion: _refreshIngestion,
  refreshAI: _refreshAI,
  _helpers: { classifyStatus, formatSeconds, formatNumber, sparklineSvg },
};

// ── Bootstrap ─────────────────────────────────────────────────────────
function boot() {
  try {
    SignalAuth.init();
    SignalAuth.onAuthChange(() => {
      refreshAllPanels();
    });
  } catch (err) {
    console.warn('[monitoring] SignalAuth.init failed', err);
  }

  bindTimeRangeButtons();

  registerPanel('ingestion', _refreshIngestion);
  registerPanel('ai', _refreshAI);

  setRange(state.range);
  updateSummary(0, 0);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot);
} else {
  boot();
}

export { uPlot };
