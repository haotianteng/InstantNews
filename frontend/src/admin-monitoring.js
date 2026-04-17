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
  formatUsd,
  sparklineSvg,
  sumSeries,
  maxSeries,
  minSeries,
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
  // Best-effort immediate recount — individual panel refreshers also recount
  // at the tail of their async work so the counter reflects fetched data.
  try { recomputeSummary(); } catch (_err) { /* noop */ }
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

/**
 * Legacy single-call counter updater. Used by early scaffolding tests that
 * relied on counters being driven by imperative numbers. US-013 superseded
 * this with recomputeSummary() which counts DOM badges directly, but we
 * keep this for external introspection via window.__monitoring__.
 */
function updateSummary(criticals, warnings) {
  const critNum = document.querySelector('#mon-summary [data-role="crit-count"]');
  const warnNum = document.querySelector('#mon-summary [data-role="warn-count"]');
  if (critNum) critNum.textContent = String(criticals);
  if (warnNum) warnNum.textContent = String(warnings);
}

// ── Central anomaly thresholds (consumed by panels + US-013) ──────────
const THRESHOLDS = {
  ingestion_p95_s: { warn: 60, crit: 180 },
  ai_queue_depth: { warn: 100, crit: 500 },
  x_rate_limit_pct: { warn: 50, crit: 80 },        // % of 450 used
  minimax_fallback_pct: { warn: 20, crit: 50 },    // % falling off minimax
};

// ── US-013: badge apply + summary counter ────────────────────────────
/**
 * Set `badge--<level>` on an element, removing the other two. Idempotent.
 * Pass `null` to strip all badge classes.
 */
function applyBadge(el, level) {
  if (!el) return;
  el.classList.remove('badge--ok', 'badge--warn', 'badge--crit');
  if (level === 'ok' || level === 'warn' || level === 'crit') {
    el.classList.add(`badge--${level}`);
  }
}

/**
 * Count currently-rendered `.badge--crit` / `.badge--warn` elements and
 * update the top-right summary counter. Called at the tail of every panel
 * refresh and by refreshAllPanels() after each tick.
 */
function recomputeSummary() {
  const crits = document.querySelectorAll('.badge--crit').length;
  const warns = document.querySelectorAll('.badge--warn').length;
  const critNum = document.querySelector('#mon-summary [data-role="crit-count"]');
  const warnNum = document.querySelector('#mon-summary [data-role="warn-count"]');
  if (critNum) critNum.textContent = String(crits);
  if (warnNum) warnNum.textContent = String(warns);
  return { crits, warns };
}

/**
 * Toggle the body filter class used by CSS to hide/show badged elements by
 * severity. Passing null clears the filter.
 */
function setSeverityFilter(severity) {
  const body = document.body;
  if (!body) return;
  body.classList.remove('body-filter--crit', 'body-filter--warn');
  const critBtn = document.querySelector('#mon-summary [data-severity="crit"]');
  const warnBtn = document.querySelector('#mon-summary [data-severity="warn"]');
  const clearBtn = document.querySelector('#mon-summary [data-role="clear-filter"]');
  if (critBtn) critBtn.setAttribute('aria-pressed', severity === 'crit' ? 'true' : 'false');
  if (warnBtn) warnBtn.setAttribute('aria-pressed', severity === 'warn' ? 'true' : 'false');
  if (severity === 'crit') {
    body.classList.add('body-filter--crit');
    if (clearBtn) clearBtn.removeAttribute('hidden');
  } else if (severity === 'warn') {
    body.classList.add('body-filter--warn');
    if (clearBtn) clearBtn.removeAttribute('hidden');
  } else if (clearBtn) {
    clearBtn.setAttribute('hidden', '');
  }
}

function bindSummaryButtons() {
  const root = document.getElementById('mon-summary');
  if (!root) return;
  root.addEventListener('click', (ev) => {
    const btn = ev.target.closest('button[data-severity], button[data-role="clear-filter"]');
    if (!btn) return;
    if (btn.dataset.role === 'clear-filter') {
      setSeverityFilter(null);
      return;
    }
    const sev = btn.dataset.severity;
    const alreadyActive = btn.getAttribute('aria-pressed') === 'true';
    setSeverityFilter(alreadyActive ? null : sev);
  });
}

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
      // US-013: tile-level badge based on p95 vs THRESHOLDS. Additive — the
      // existing p50 dot-status coloring lives on inner .ingest-tile__dot.
      const { warn, crit } = THRESHOLDS.ingestion_p95_s;
      applyBadge(tile, classifyStatus(p95, warn, crit));
    }
    _ingestionState.lastSeries[s.name] = b;
  }
  _sortIngestionTiles();
  recomputeSummary();
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
  const qdWidget = body.querySelector('.widget--queue-depth');
  if (qdEl) qdEl.textContent = qdLast == null ? '–' : formatNumber(qdLast);
  if (qdSpark) qdSpark.innerHTML = sparklineSvg((qd.values || []).slice(-60), {
    width: 160, height: 32, stroke: 'var(--blue)',
  });
  // US-013: badge on queue-depth widget.
  if (qdWidget) {
    const { warn, crit } = THRESHOLDS.ai_queue_depth;
    applyBadge(qdWidget, qdLast == null ? 'ok' : classifyStatus(qdLast, warn, crit));
  }

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

  // US-013: badge on fallback-chain widget based on non-minimax share (%).
  // No data → ok (absence of routing is not an anomaly here).
  const fallbackWidget = body.querySelector('.widget--fallback-chain');
  if (fallbackWidget) {
    const { warn, crit } = THRESHOLDS.minimax_fallback_pct;
    if (total <= 0) {
      applyBadge(fallbackWidget, 'ok');
    } else {
      const fallbackPct = (1 - shares.minimax) * 100;
      applyBadge(fallbackWidget, classifyStatus(fallbackPct, warn, crit));
    }
  }

  recomputeSummary();
}

// ── US-011: Upstream APIs panel ───────────────────────────────────────
function _upstreamPanelBody() {
  return document.querySelector('.panel--upstream .panel__body');
}

function _renderUpstreamSkeleton() {
  const body = _upstreamPanelBody();
  if (!body) return;
  if (body.querySelector('.upstream-grid')) return;
  body.innerHTML = `
    <div class="upstream-grid">
      <div class="tile meter--x-api" data-status="ok">
        <div class="tile__label">X API rate-limit</div>
        <div class="tile__value">
          <span class="meter-bar-wrap" title="Window: 15 min rolling">
            <span class="meter-bar" style="width:0%"></span>
          </span>
          <span class="tile__num num" data-numeric>– / 450</span>
        </div>
        <div class="tile__hint">search_recent</div>
      </div>
      <a class="tile tile--polygon" target="_blank" rel="noopener"
         href="https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/$252Fecs$252Finstantnews-worker$253FfilterPattern$253D%2522polygon%2522">
        <div class="tile__label">Polygon</div>
        <div class="tile__placeholder">Pending instrumentation</div>
        <div class="tile__hint">Open CloudWatch logs</div>
      </a>
      <a class="tile tile--edgar" target="_blank" rel="noopener"
         href="https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/$252Fecs$252Finstantnews-worker$253FfilterPattern$253D%2522edgar%2522">
        <div class="tile__label">EDGAR</div>
        <div class="tile__placeholder">Pending instrumentation</div>
        <div class="tile__hint">Open CloudWatch logs</div>
      </a>
      <a class="tile tile--stripe" target="_blank" rel="noopener"
         href="https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/$252Fecs$252Finstantnews-web$253FfilterPattern$253D%2522stripe_webhook%2522">
        <div class="tile__label">Stripe webhook</div>
        <div class="tile__placeholder">Pending instrumentation</div>
        <div class="tile__hint">Open CloudWatch logs</div>
      </a>
    </div>
  `;
}

async function _refreshUpstream(range) {
  const body = _upstreamPanelBody();
  if (!body) return;
  _renderUpstreamSkeleton();

  let series = {};
  try {
    series = await fetchMetrics([
      { id: 'xrl', namespace: 'InstantNews/Twitter', metric: 'RateLimitRemaining',
        dimensions: { Endpoint: 'search_recent' }, stat: 'Minimum' },
    ], range);
  } catch (err) {
    console.warn('[monitoring] upstream fetchMetrics failed', err);
    return;
  }

  const remainingMin = minSeries((series.xrl || {}).values);
  const meter = body.querySelector('.meter--x-api');
  const bar = body.querySelector('.meter--x-api .meter-bar');
  const numEl = body.querySelector('.meter--x-api .tile__num');

  if (meter && bar && numEl) {
    // Quota for search_recent on Basic tier is 450 per 15min window.
    const quota = 450;
    if (remainingMin == null) {
      bar.style.width = '0%';
      numEl.textContent = '– / 450';
      meter.setAttribute('data-status', 'ok');
      meter.classList.remove('meter--ok', 'meter--warn', 'meter--danger');
      meter.classList.add('meter--ok');
      // US-013: no data → ok badge.
      applyBadge(meter, 'ok');
    } else {
      const used = Math.max(0, quota - remainingMin);
      const pct = Math.max(0, Math.min(100, (used / quota) * 100));
      bar.style.width = `${pct.toFixed(1)}%`;
      numEl.textContent = `${used} / ${quota}`;
      meter.classList.remove('meter--ok', 'meter--warn', 'meter--danger');
      let cls = 'meter--ok';
      if (pct > 80) cls = 'meter--danger';
      else if (pct >= 50) cls = 'meter--warn';
      meter.classList.add(cls);
      meter.setAttribute('data-status',
        cls === 'meter--danger' ? 'crit' : (cls === 'meter--warn' ? 'warn' : 'ok'));
      // US-013: badge mirrors the existing meter-- classes via central
      // THRESHOLDS so all badges share one ruleset.
      const { warn, crit } = THRESHOLDS.x_rate_limit_pct;
      applyBadge(meter, classifyStatus(pct, warn, crit));
    }
  }

  // US-013: the three "pending instrumentation" tiles are flagged as warn —
  // they're known-unimplemented and should not read as green/ok.
  for (const sel of ['.tile--polygon', '.tile--edgar', '.tile--stripe']) {
    const tile = body.querySelector(sel);
    if (tile) applyBadge(tile, 'warn');
  }

  recomputeSummary();
}

// ── US-012: Cost panel ────────────────────────────────────────────────
const _costState = { cache: null, cacheAt: 0 };

function _costPanelBody() {
  return document.querySelector('.panel--cost .panel__body');
}

function _renderCostSkeleton() {
  const body = _costPanelBody();
  if (!body) return;
  if (body.querySelector('.cost-grid')) return;
  body.innerHTML = `
    <div class="cost-grid">
      <div class="summary--mtd">
        <div class="summary__row">
          <span class="summary__label">MTD spend</span>
          <span class="summary__value num" data-numeric data-role="mtd">–</span>
        </div>
        <div class="summary__row">
          <span class="summary__label">Projected month-end</span>
          <span class="summary__value num" data-numeric data-role="proj">–</span>
        </div>
      </div>
      <div class="chart--aws-daily" aria-label="AWS daily spend stacked bar chart"></div>
      <div class="meter--x-api-monthly">
        <div class="meter__row">
          <span class="meter__label" data-role="x-label">– / – posts</span>
          <span class="meter__days" data-role="x-days"></span>
        </div>
        <div class="meter-bar-wrap">
          <span class="meter-bar" style="width:0%"></span>
        </div>
        <div class="meter__note" data-role="x-est" hidden>estimated</div>
      </div>
    </div>
  `;
}

function _resolveCostRangeKey(range) {
  // Cost API accepts 24h | 7d | 30d; dashboard uses 1h | 24h | 7d.
  if (range === '1h' || range === '24h') return '24h';
  if (range === '7d') return '7d';
  return '7d';
}

function _renderAwsStackedBars(awsData) {
  const body = _costPanelBody();
  if (!body) return;
  const host = body.querySelector('.chart--aws-daily');
  if (!host) return;

  const dailyTotals = awsData.daily_totals || [];
  const byService = awsData.by_service || [];
  if (!dailyTotals.length) {
    host.innerHTML = '<div class="widget__empty">No AWS cost data</div>';
    return;
  }

  // Pick the top-4 preferred services, everything else rolls up as "other".
  const SERVICE_ALIASES = {
    'Amazon Elastic Container Service': 'ECS',
    'Amazon Relational Database Service': 'RDS',
    'Amazon ElastiCache': 'ElastiCache',
    'AmazonCloudWatch': 'CloudWatch',
    'Amazon CloudWatch': 'CloudWatch',
  };
  const preferred = ['ECS', 'RDS', 'ElastiCache', 'CloudWatch'];
  const topServiceNames = new Set();
  for (const alias of Object.keys(SERVICE_ALIASES)) {
    if (byService.some((s) => s.service === alias)) topServiceNames.add(alias);
  }
  // If fewer than 4 preferred aliases matched, fill from top-by-cost.
  for (const s of byService) {
    if (topServiceNames.size >= 4) break;
    topServiceNames.add(s.service);
  }

  const labelFor = (svc) => SERVICE_ALIASES[svc] || svc;
  const PALETTE = {
    ECS: '#3fb950',
    RDS: '#58a6ff',
    ElastiCache: '#d29922',
    CloudWatch: '#bc8cff',
    other: '#8b949e',
  };

  // CE's by_service payload is summed across the range, so per-day breakdown
  // isn't directly available. Approximate by scaling each day's total by the
  // across-range service mix (honest given the data we have).
  const rangeTotal = byService.reduce((acc, s) => acc + (Number(s.cost) || 0), 0);
  const topTotal = byService.reduce((acc, s) => (
    topServiceNames.has(s.service) ? acc + (Number(s.cost) || 0) : acc
  ), 0);
  const mix = {};
  for (const s of byService) {
    if (topServiceNames.has(s.service)) {
      mix[labelFor(s.service)] = rangeTotal > 0 ? (Number(s.cost) || 0) / rangeTotal : 0;
    }
  }
  mix.other = rangeTotal > 0 ? (rangeTotal - topTotal) / rangeTotal : 0;

  const stackKeys = preferred.filter((k) => mix[k] !== undefined && mix[k] > 0);
  if (!stackKeys.length) {
    for (const svc of Object.keys(mix)) {
      if (svc !== 'other' && mix[svc] > 0) stackKeys.push(svc);
    }
  }
  if (mix.other > 0) stackKeys.push('other');

  const width = host.clientWidth || 480;
  const height = 160;
  const padL = 36;
  const padR = 8;
  const padT = 8;
  const padB = 22;
  const plotW = width - padL - padR;
  const plotH = height - padT - padB;
  const maxDaily = Math.max(1e-6, ...dailyTotals.map((d) => Number(d.cost) || 0));
  const bw = Math.max(4, plotW / dailyTotals.length - 4);

  let bars = '';
  dailyTotals.forEach((d, i) => {
    const total = Number(d.cost) || 0;
    const x = padL + i * (plotW / dailyTotals.length) + 2;
    let yCursor = padT + plotH;
    for (const k of stackKeys) {
      const share = mix[k] || 0;
      const h = total > 0 ? (total / maxDaily) * plotH * share : 0;
      if (h <= 0) continue;
      const y = yCursor - h;
      const color = PALETTE[k] || '#484f58';
      bars += `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" fill="${color}" data-service="${escapeHtml(k)}" data-date="${escapeHtml(d.date)}">
        <title>${escapeHtml(d.date)} ${escapeHtml(k)} ${formatUsd(total * share)}</title>
      </rect>`;
      yCursor = y;
    }
    if (i % Math.max(1, Math.round(dailyTotals.length / 7)) === 0) {
      const lx = x + bw / 2;
      const ly = padT + plotH + 14;
      const short = String(d.date || '').slice(5); // MM-DD
      bars += `<text x="${lx.toFixed(1)}" y="${ly}" text-anchor="middle" fill="#8b949e" font-size="10">${escapeHtml(short)}</text>`;
    }
  });

  bars += `<text x="4" y="${padT + 10}" fill="#8b949e" font-size="10">${escapeHtml(formatUsd(maxDaily))}</text>`;
  bars += `<text x="4" y="${padT + plotH}" fill="#8b949e" font-size="10">$0</text>`;

  const legend = stackKeys.map((k) => (
    `<span class="legend-item"><i style="background:${PALETTE[k] || '#484f58'}"></i>${escapeHtml(k)}</span>`
  )).join('');

  host.innerHTML = `
    <svg class="aws-bars" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
      ${bars}
    </svg>
    <div class="aws-legend">${legend}</div>
  `;
}

function _renderCostMtd(awsData) {
  const body = _costPanelBody();
  if (!body) return;
  const daily = awsData.daily_totals || [];
  const mtdEl = body.querySelector('[data-role="mtd"]');
  const projEl = body.querySelector('[data-role="proj"]');
  const now = new Date();
  const monthIdx = now.getUTCMonth();
  const monthYear = now.getUTCFullYear();
  let mtd = 0;
  for (const d of daily) {
    const parts = String(d.date || '').split('-');
    if (parts.length !== 3) continue;
    if (Number(parts[0]) === monthYear && Number(parts[1]) - 1 === monthIdx) {
      mtd += Number(d.cost) || 0;
    }
  }
  if (mtd === 0 && daily.length) {
    // Range may start before month boundary — fall back to range total.
    mtd = daily.reduce((acc, d) => acc + (Number(d.cost) || 0), 0);
  }
  const daysElapsed = Math.max(1, now.getUTCDate());
  const daysInMonth = new Date(Date.UTC(monthYear, monthIdx + 1, 0)).getUTCDate();
  const projected = (mtd / daysElapsed) * daysInMonth;
  if (mtdEl) mtdEl.textContent = formatUsd(mtd);
  if (projEl) projEl.textContent = formatUsd(projected);
}

function _renderXApiMonthly(xApi) {
  const body = _costPanelBody();
  if (!body) return;
  const label = body.querySelector('[data-role="x-label"]');
  const daysEl = body.querySelector('[data-role="x-days"]');
  const estEl = body.querySelector('[data-role="x-est"]');
  const bar = body.querySelector('.meter--x-api-monthly .meter-bar');
  if (!xApi || typeof xApi !== 'object') {
    if (label) label.textContent = '– / – posts';
    if (bar) bar.style.width = '0%';
    return;
  }
  const used = Number(xApi.used_this_month) || 0;
  const quota = Number(xApi.quota) || 0;
  const pct = quota > 0 ? Math.max(0, Math.min(100, (used / quota) * 100)) : 0;
  const now = new Date();
  const daysInMonth = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 0)).getUTCDate();
  const daysLeft = Math.max(0, daysInMonth - now.getUTCDate());

  if (label) {
    if (quota > 0) {
      label.textContent = `${used.toLocaleString()} / ${quota.toLocaleString()} posts`;
    } else {
      label.textContent = `${used.toLocaleString()} posts`;
    }
  }
  if (daysEl) daysEl.textContent = `${daysLeft} days left`;
  if (bar) bar.style.width = `${pct.toFixed(1)}%`;
  if (estEl) {
    if (xApi.estimated === true) {
      estEl.removeAttribute('hidden');
    } else {
      estEl.setAttribute('hidden', '');
    }
  }
}

async function _refreshCost(range) {
  const body = _costPanelBody();
  if (!body) return;
  _renderCostSkeleton();

  const key = _resolveCostRangeKey(range);
  let data = null;
  // Page-local cache (1 minute) so repeated refresh ticks don't hammer the
  // server (which in turn caches CE responses for 1h).
  if (
    _costState.cache
    && _costState.cache._key === key
    && (Date.now() - _costState.cacheAt) < 60_000
  ) {
    data = _costState.cache;
  } else {
    try {
      data = await fetchCost(key);
      data._key = key;
      _costState.cache = data;
      _costState.cacheAt = Date.now();
    } catch (err) {
      console.warn('[monitoring] fetchCost failed', err);
      return;
    }
  }

  const aws = data.aws || { by_service: [], daily_totals: [] };
  _renderAwsStackedBars(aws);
  _renderCostMtd(aws);
  _renderXApiMonthly(data.x_api || {});
  // US-013: cost panel has no threshold-backed badges today, but recount so
  // badges from other panels (which may have refreshed concurrently) stay
  // in sync with the summary counter.
  recomputeSummary();
}

// ── Public interface (window.__monitoring__) ──────────────────────────
window.__monitoring__ = {
  state,
  setRange,
  registerPanel,
  refreshAllPanels,
  refreshAll: refreshAllPanels,    // alias for US-013 tester convenience
  panels,
  fetchMetrics,
  fetchCost,
  updateSummary,
  recomputeSummary,                // US-013: recount badges after mock injects
  setSeverityFilter,               // US-013: programmatic filter toggle
  applyBadge,                      // US-013: direct badge set (debug only)
  uPlot,
  TIME_RANGES,
  POLL_INTERVALS,
  THRESHOLDS,
  refreshIngestion: _refreshIngestion,
  refreshAI: _refreshAI,
  refreshUpstream: _refreshUpstream,
  refreshCost: _refreshCost,
  _helpers: { classifyStatus, formatSeconds, formatNumber, formatUsd, sparklineSvg },
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
  bindSummaryButtons();

  registerPanel('ingestion', _refreshIngestion);
  registerPanel('ai', _refreshAI);
  registerPanel('upstream', _refreshUpstream);
  registerPanel('cost', _refreshCost);

  setRange(state.range);
  recomputeSummary();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot);
} else {
  boot();
}

export { uPlot };
