/**
 * SIGNAL News Trading Terminal — Frontend Application
 * Auto-refreshing financial news aggregator with sentiment analysis
 */

"use strict";

import SignalAuth from './auth.js';

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const API = "/api";
const DEFAULT_LIMIT = 200;
const NEW_THRESHOLD_MS = 60000; // 60 seconds
const MARKET_REFRESH_MS = 10000; // 10 seconds
const MAX_CONCURRENT_FETCHES = 10;

// ---------------------------------------------------------------------------
// Column Definitions
// ---------------------------------------------------------------------------

const COLUMN_DEFS = [
  { id: 'time', label: 'Time', defaultVisible: true, required: false, requiredFeature: null },
  { id: 'sentiment', label: 'Sentiment', defaultVisible: true, required: false, requiredFeature: 'sentiment_filter' },
  { id: 'source', label: 'Source', defaultVisible: true, required: false, requiredFeature: null },
  { id: 'headline', label: 'Headline', defaultVisible: true, required: true, requiredFeature: null },
  { id: 'summary', label: 'Summary', defaultVisible: true, required: false, requiredFeature: null },
  { id: 'ticker', label: 'Ticker', defaultVisible: false, required: false, requiredFeature: 'ai_ticker_recommendations' },
  { id: 'confidence', label: 'Confidence', defaultVisible: false, required: false, requiredFeature: 'ai_ticker_recommendations' },
  { id: 'risk', label: 'Risk Level', defaultVisible: false, required: false, requiredFeature: 'ai_ticker_recommendations' },
  { id: 'tradeable', label: 'Tradeable', defaultVisible: false, required: false, requiredFeature: 'ai_ticker_recommendations' },
];

const LS_COLUMN_KEY = 'instnews_column_visibility';
const LS_COLUMN_ORDER_KEY = 'instnews_column_order';
const LS_COLUMN_WIDTHS_KEY = 'instnews_column_widths';
const MIN_COL_WIDTH = 60;

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let state = {
  items: [],
  seenIds: new Set(),
  newIds: new Set(),
  sources: [],
  stats: null,
  filter: {
    sentiment: "all",
    sources: new Set(), // empty = all selected
    query: "",
    dateFrom: "",
    dateTo: "",
    hideDuplicates: false,
  },
  refreshInterval: 5000,
  refreshTimer: null,
  lastRefresh: null,
  connected: false,
  loading: true,
  totalFetched: 0,
  fetchCount: 0,
  itemsPerSecond: 0,
  startTime: Date.now(),
  sidebarOpen: false,
  modalOpen: false,
  detailModalOpen: false,
  detailItem: null,
  userTier: null,
  userFeatures: {},
  soundEnabled: false,
  columnVisibility: {},
  columnOrder: COLUMN_DEFS.map(c => c.id),
  columnWidths: {},
  columnSettingsOpen: false,
  marketPrices: {},
  priceRefreshTimer: null,
  companyProfileOpen: false,
  companyProfileSymbol: null,
  companyProfileData: null,
  companyProfileLoading: false,
};

// ---------------------------------------------------------------------------
// DOM References
// ---------------------------------------------------------------------------

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function formatTime(dateStr) {
  if (!dateStr) return "--:--:--";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return "--:--:--";
    return d.toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch {
    return "--:--:--";
  }
}

function formatDate(dateStr) {
  if (!dateStr) return "";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}

function timeAgo(dateStr) {
  if (!dateStr) return "";
  try {
    const d = new Date(dateStr);
    const now = new Date();
    const diff = now - d;
    if (diff < 0) return "just now";
    if (diff < 60000) return `${Math.floor(diff / 1000)}s ago`;
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return `${Math.floor(diff / 86400000)}d ago`;
  } catch {
    return "";
  }
}

function isNew(dateStr) {
  if (!dateStr) return false;
  try {
    const d = new Date(dateStr);
    return (Date.now() - d.getTime()) < NEW_THRESHOLD_MS;
  } catch {
    return false;
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function truncate(str, max) {
  if (!str) return "";
  return str.length > max ? str.slice(0, max) + "\u2026" : str;
}

function formatMarketCap(val) {
  if (val == null) return "\u2014";
  if (val >= 1e12) return "$" + (val / 1e12).toFixed(2) + "T";
  if (val >= 1e9) return "$" + (val / 1e9).toFixed(2) + "B";
  if (val >= 1e6) return "$" + (val / 1e6).toFixed(2) + "M";
  return "$" + val.toLocaleString();
}

// ---------------------------------------------------------------------------
// API Calls
// ---------------------------------------------------------------------------

async function fetchNews() {
  try {
    const params = new URLSearchParams({ limit: DEFAULT_LIMIT });
    if (state.filter.dateFrom) params.set("from", state.filter.dateFrom);
    if (state.filter.dateTo) params.set("to", state.filter.dateTo);
    const res = await SignalAuth.fetch(`${API}/news?${params}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.connected = true;
    state.loading = false;
    state.fetchCount++;
    state.lastRefresh = new Date().toISOString();

    if (data.items && data.items.length > 0) {
      // Detect new items
      const newIds = new Set();
      for (const item of data.items) {
        if (!state.seenIds.has(item.id)) {
          newIds.add(item.id);
          state.seenIds.add(item.id);
        }
      }

      // Play sound for new items if enabled
      if (state.soundEnabled && newIds.size > 0 && state.fetchCount > 1) {
        playNotificationSound();
      }

      state.newIds = newIds;
      state.items = data.items;
      state.totalFetched = data.count;

      // Calculate items/second
      const elapsed = (Date.now() - state.startTime) / 1000;
      state.itemsPerSecond = elapsed > 0 ? (state.totalFetched / elapsed).toFixed(1) : 0;
    }

    renderNews();
    updateStatusBar();
    updateConnectionStatus(true);
    fetchMarketPrices();
  } catch (err) {
    state.connected = false;
    state.loading = false;
    updateConnectionStatus(false);
    if (state.items.length === 0) {
      renderEmpty("Unable to connect to API. Retrying...");
    }
  }
}

async function fetchSources() {
  try {
    const res = await SignalAuth.fetch(`${API}/sources`);
    if (!res.ok) return;
    const data = await res.json();
    state.sources = data.sources || [];
    renderSources();
  } catch {
    // silent
  }
}

async function fetchStats() {
  try {
    const res = await SignalAuth.fetch(`${API}/stats`);
    if (!res.ok) return;
    state.stats = await res.json();
    updateHeaderStats();
  } catch {
    // silent
  }
}

async function fetchMarketPrices() {
  if (!state.userFeatures.ai_ticker_recommendations) return;
  if (!state.columnVisibility.ticker) return;

  const tickers = [...new Set(state.items.map(i => i.target_asset).filter(Boolean))];
  if (tickers.length === 0) return;

  for (let i = 0; i < tickers.length; i += MAX_CONCURRENT_FETCHES) {
    const batch = tickers.slice(i, i + MAX_CONCURRENT_FETCHES);
    const promises = batch.map(async (symbol) => {
      try {
        const res = await SignalAuth.fetch(`${API}/market/${encodeURIComponent(symbol)}`);
        if (res.ok) {
          state.marketPrices[symbol] = await res.json();
        }
      } catch {
        // silent — price just won't display
      }
    });
    await Promise.all(promises);
  }

  renderNews();
}

function startPriceRefresh() {
  stopPriceRefresh();
  if (!state.userFeatures.ai_ticker_recommendations) return;
  if (!state.columnVisibility.ticker) return;
  state.priceRefreshTimer = setInterval(fetchMarketPrices, MARKET_REFRESH_MS);
}

function stopPriceRefresh() {
  if (state.priceRefreshTimer) {
    clearInterval(state.priceRefreshTimer);
    state.priceRefreshTimer = null;
  }
}

async function forceRefresh() {
  try {
    const btn = $("#btn-refresh");
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spinning"><path d="M21 12a9 9 0 11-6.219-8.56"/></svg>Refreshing`;
    }
    await SignalAuth.fetch(`${API}/refresh`, { method: "POST" });
    await fetchNews();
    await fetchStats();
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 11-6.219-8.56"/><path d="M22 3v6h-6"/></svg>Refresh`;
    }
  } catch {
    const btn = $("#btn-refresh");
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 11-6.219-8.56"/><path d="M22 3v6h-6"/></svg>Refresh`;
    }
  }
}

// ---------------------------------------------------------------------------
// Sound
// ---------------------------------------------------------------------------

function playNotificationSound() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.type = "sine";
    osc.frequency.setValueAtTime(880, ctx.currentTime);
    osc.frequency.setValueAtTime(1100, ctx.currentTime + 0.05);
    gain.gain.setValueAtTime(0.08, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.15);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.15);
  } catch {
    // silent
  }
}

// ---------------------------------------------------------------------------
// Filtering
// ---------------------------------------------------------------------------

function getFilteredItems() {
  return state.items.filter((item) => {
    // Sentiment filter
    if (state.filter.sentiment !== "all" && item.sentiment_label !== state.filter.sentiment) {
      return false;
    }
    // Source filter
    if (state.filter.sources.size > 0 && !state.filter.sources.has(item.source)) {
      return false;
    }
    // Query filter
    if (state.filter.query) {
      const q = state.filter.query.toLowerCase();
      const inTitle = (item.title || "").toLowerCase().includes(q);
      const inSummary = (item.summary || "").toLowerCase().includes(q);
      if (!inTitle && !inSummary) return false;
    }
    // Duplicate filter
    if (state.filter.hideDuplicates && item.duplicate) {
      return false;
    }
    return true;
  });
}

function getSentimentCounts() {
  const counts = { all: 0, bullish: 0, bearish: 0, neutral: 0 };
  for (const item of state.items) {
    counts.all++;
    if (counts[item.sentiment_label] !== undefined) {
      counts[item.sentiment_label]++;
    }
  }
  return counts;
}

// ---------------------------------------------------------------------------
// Column Configuration
// ---------------------------------------------------------------------------

function loadColumnVisibility() {
  try {
    const stored = localStorage.getItem(LS_COLUMN_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      const vis = {};
      for (const col of COLUMN_DEFS) {
        vis[col.id] = col.id in parsed ? parsed[col.id] : col.defaultVisible;
      }
      state.columnVisibility = vis;
      return;
    }
  } catch {
    // Fall through to defaults
  }
  const vis = {};
  for (const col of COLUMN_DEFS) {
    vis[col.id] = col.defaultVisible;
  }
  state.columnVisibility = vis;
}

function saveColumnVisibility() {
  try {
    localStorage.setItem(LS_COLUMN_KEY, JSON.stringify(state.columnVisibility));
  } catch {
    // Silent
  }
}

function loadColumnOrder() {
  try {
    const stored = localStorage.getItem(LS_COLUMN_ORDER_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      if (Array.isArray(parsed)) {
        const knownIds = new Set(COLUMN_DEFS.map(c => c.id));
        const valid = parsed.filter(id => knownIds.has(id));
        // Append any new columns not in stored order
        for (const col of COLUMN_DEFS) {
          if (!valid.includes(col.id)) valid.push(col.id);
        }
        state.columnOrder = valid;
        return;
      }
    }
  } catch {
    // Fall through to defaults
  }
  state.columnOrder = COLUMN_DEFS.map(c => c.id);
}

function saveColumnOrder() {
  try {
    localStorage.setItem(LS_COLUMN_ORDER_KEY, JSON.stringify(state.columnOrder));
  } catch {
    // Silent
  }
}

function loadColumnWidths() {
  try {
    const stored = localStorage.getItem(LS_COLUMN_WIDTHS_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      if (parsed && typeof parsed === 'object') {
        const widths = {};
        for (const col of COLUMN_DEFS) {
          if (col.id in parsed && typeof parsed[col.id] === 'number' && parsed[col.id] >= MIN_COL_WIDTH) {
            widths[col.id] = parsed[col.id];
          }
        }
        state.columnWidths = widths;
        return;
      }
    }
  } catch {
    // Fall through to defaults
  }
  state.columnWidths = {};
}

function saveColumnWidths() {
  try {
    localStorage.setItem(LS_COLUMN_WIDTHS_KEY, JSON.stringify(state.columnWidths));
  } catch {
    // Silent
  }
}

function getOrderedColumnDefs() {
  const defMap = {};
  for (const col of COLUMN_DEFS) defMap[col.id] = col;
  return state.columnOrder.map(id => defMap[id]).filter(Boolean);
}

function isColumnLocked(col) {
  if (!col.requiredFeature) return false;
  if (state.userTier === null) return false;
  return !state.userFeatures[col.requiredFeature];
}

function getVisibleColumns() {
  return getOrderedColumnDefs().filter(col => {
    if (isColumnLocked(col)) return false;
    return state.columnVisibility[col.id] !== false;
  });
}

function renderTableHeader() {
  const head = document.querySelector('.news-table thead');
  if (!head) return;
  const cols = getVisibleColumns();
  head.innerHTML = '<tr>' + cols.map(col => {
    const w = state.columnWidths[col.id];
    const style = w ? ` style="width:${w}px"` : '';
    return `<th class="col-${col.id}"${style}>${col.label}<span class="col-resize-handle" data-col-id="${col.id}"></span></th>`;
  }).join('') + '</tr>';

  // Apply table-layout: fixed when any custom width is set
  const table = document.querySelector('.news-table');
  if (table) {
    table.style.tableLayout = Object.keys(state.columnWidths).length > 0 ? 'fixed' : '';
  }

  bindColumnResizeHandles();
}

function bindColumnResizeHandles() {
  const handles = document.querySelectorAll('.col-resize-handle');
  handles.forEach(handle => {
    handle.addEventListener('mousedown', onResizeStart);
    handle.addEventListener('dblclick', onResizeAutoFit);
  });
}

function onResizeStart(e) {
  e.preventDefault();
  e.stopPropagation();
  const handle = e.target;
  const th = handle.parentElement;
  const colId = handle.dataset.colId;
  const startX = e.clientX;
  const startWidth = th.offsetWidth;

  const table = document.querySelector('.news-table');
  if (table) table.style.tableLayout = 'fixed';

  document.body.style.cursor = 'col-resize';
  document.body.style.userSelect = 'none';
  handle.classList.add('active');

  function onMouseMove(ev) {
    const delta = ev.clientX - startX;
    const newWidth = Math.max(MIN_COL_WIDTH, startWidth + delta);
    th.style.width = newWidth + 'px';
  }

  function onMouseUp(ev) {
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onMouseUp);
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    handle.classList.remove('active');

    const delta = ev.clientX - startX;
    const finalWidth = Math.max(MIN_COL_WIDTH, startWidth + delta);
    state.columnWidths[colId] = finalWidth;
    saveColumnWidths();
    renderTableHeader();
    renderNews();
  }

  document.addEventListener('mousemove', onMouseMove);
  document.addEventListener('mouseup', onMouseUp);
}

function onResizeAutoFit(e) {
  e.preventDefault();
  e.stopPropagation();
  const colId = e.target.dataset.colId;
  const cols = getVisibleColumns();
  const colIndex = cols.findIndex(c => c.id === colId);
  if (colIndex === -1) return;

  const rows = document.querySelectorAll('#news-body tr');
  let maxWidth = MIN_COL_WIDTH;

  // Measure header text width
  const th = e.target.parentElement;
  const headerSpan = document.createElement('span');
  headerSpan.style.cssText = 'visibility:hidden;position:absolute;white-space:nowrap;font-size:10px;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;';
  headerSpan.textContent = th.textContent;
  document.body.appendChild(headerSpan);
  maxWidth = Math.max(maxWidth, headerSpan.offsetWidth + 32); // 24px padding + 8px handle
  document.body.removeChild(headerSpan);

  // Measure cell content widths
  rows.forEach(row => {
    if (row.classList.contains('skeleton-row')) return;
    const cells = row.querySelectorAll('td');
    const cell = cells[colIndex];
    if (!cell) return;
    const measurer = document.createElement('div');
    measurer.style.cssText = 'visibility:hidden;position:absolute;white-space:nowrap;font-size:12px;';
    measurer.innerHTML = cell.innerHTML;
    document.body.appendChild(measurer);
    maxWidth = Math.max(maxWidth, measurer.offsetWidth + 24); // 24px padding
    document.body.removeChild(measurer);
  });

  // Cap at reasonable max
  maxWidth = Math.min(maxWidth, 600);

  const table = document.querySelector('.news-table');
  if (table) table.style.tableLayout = 'fixed';

  state.columnWidths[colId] = maxWidth;
  saveColumnWidths();
  renderTableHeader();
  renderNews();
}

function renderCell(colId, item, isFresh, dupBadge) {
  switch (colId) {
    case 'time':
      return `<td class="cell-time" title="${timeAgo(item.published)}">${formatTime(item.published)}</td>`;
    case 'sentiment':
      return `<td class="cell-sentiment"><span class="sentiment-badge ${item.sentiment_label}"><span class="sentiment-dot"></span>${item.sentiment_label}</span></td>`;
    case 'source':
      return `<td class="cell-source"><span class="source-tag">${escapeHtml(item.source || "")}</span></td>`;
    case 'headline':
      return `<td class="cell-headline"><a href="${escapeHtml(item.link || "#")}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.title || "Untitled")}</a>${isFresh ? '<span class="badge-new">NEW</span>' : ''}${dupBadge}</td>`;
    case 'summary':
      return `<td class="cell-summary">${escapeHtml(truncate(item.summary, 120))}</td>`;
    case 'ticker': {
      if (!item.target_asset) return '<td class="cell-ticker"><span class="cell-dash">\u2014</span></td>';
      const ticker = escapeHtml(item.target_asset);
      const mkt = state.marketPrices[item.target_asset];
      let priceHtml = '';
      if (mkt && mkt.price != null) {
        const pct = mkt.change_percent || 0;
        const sign = pct >= 0 ? '+' : '';
        const cls = pct > 0 ? 'price-up' : pct < 0 ? 'price-down' : 'price-flat';
        priceHtml = `<span class="ticker-price ${cls}">$${mkt.price.toFixed(2)} <span class="ticker-change">${sign}${pct.toFixed(2)}%</span></span>`;
      }
      return `<td class="cell-ticker"><span class="ticker-badge" data-ticker="${ticker}">${ticker}${priceHtml}</span></td>`;
    }
    case 'confidence':
      return `<td class="cell-confidence">${item.confidence != null ? Math.round(item.confidence * 100) + '%' : '<span class="cell-dash">\u2014</span>'}</td>`;
    case 'risk': {
      if (!item.risk_level) return '<td class="cell-risk"><span class="cell-dash">\u2014</span></td>';
      const rl = item.risk_level.toLowerCase();
      const rc = rl === 'low' ? 'green' : rl === 'high' ? 'red' : 'yellow';
      return `<td class="cell-risk"><span class="risk-badge ${rc}">${escapeHtml(item.risk_level.toUpperCase())}</span></td>`;
    }
    case 'tradeable':
      if (item.tradeable == null) return '<td class="cell-tradeable"><span class="cell-dash">\u2014</span></td>';
      return `<td class="cell-tradeable"><span class="tradeable-badge ${item.tradeable ? 'yes' : 'no'}">${item.tradeable ? 'YES' : 'NO'}</span></td>`;
    default:
      return '<td></td>';
  }
}

// ---------------------------------------------------------------------------
// Column Settings Panel
// ---------------------------------------------------------------------------

function toggleColumnSettings(forceState) {
  const open = typeof forceState === 'boolean' ? forceState : !state.columnSettingsOpen;
  state.columnSettingsOpen = open;
  const panel = $('#column-settings-panel');
  if (panel) panel.classList.toggle('open', open);
}

function renderColumnSettings() {
  const panel = $('#column-settings-panel');
  if (!panel) return;

  const orderedDefs = getOrderedColumnDefs();
  const items = orderedDefs.map(col => {
    const locked = isColumnLocked(col);
    const checked = !locked && state.columnVisibility[col.id] !== false;
    const disabled = col.required || locked;

    return `<div class="col-toggle-item${locked ? ' locked' : ''}${col.required ? ' required' : ''}" draggable="true" data-col-id="${col.id}">
      <span class="col-drag-handle" aria-label="Drag to reorder">
        <svg width="10" height="14" viewBox="0 0 10 14" fill="currentColor">
          <circle cx="3" cy="2" r="1.2"/><circle cx="7" cy="2" r="1.2"/>
          <circle cx="3" cy="7" r="1.2"/><circle cx="7" cy="7" r="1.2"/>
          <circle cx="3" cy="12" r="1.2"/><circle cx="7" cy="12" r="1.2"/>
        </svg>
      </span>
      <span class="col-toggle-label">
        ${locked ? '<svg class="col-lock-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>' : ''}
        ${escapeHtml(col.label)}
      </span>
      <span class="col-toggle-switch${disabled ? ' disabled' : ''}">
        <input type="checkbox" ${checked ? 'checked' : ''} ${disabled ? 'disabled' : ''} data-col-id="${col.id}">
        <span class="col-toggle-track"><span class="col-toggle-thumb"></span></span>
      </span>
    </div>`;
  });

  panel.innerHTML = `<div class="col-settings-header"><span>Columns</span></div>
    <div class="col-settings-list">${items.join('')}</div>`;

  // Toggle visibility
  panel.querySelectorAll('input[type="checkbox"]').forEach(cb => {
    cb.addEventListener('change', (e) => {
      const colId = e.target.dataset.colId;
      state.columnVisibility[colId] = e.target.checked;
      saveColumnVisibility();
      renderTableHeader();
      renderNews();
    });
  });

  // Drag-and-drop reorder
  const list = panel.querySelector('.col-settings-list');
  let dragSrcEl = null;

  list.querySelectorAll('.col-toggle-item[draggable]').forEach(item => {
    item.addEventListener('dragstart', (e) => {
      dragSrcEl = item;
      item.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', item.dataset.colId);
    });

    item.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      if (!dragSrcEl || item === dragSrcEl) return;

      // Remove existing drop indicator
      list.querySelectorAll('.col-toggle-item').forEach(el => el.classList.remove('drag-over-above', 'drag-over-below'));

      const rect = item.getBoundingClientRect();
      const midY = rect.top + rect.height / 2;
      if (e.clientY < midY) {
        item.classList.add('drag-over-above');
      } else {
        item.classList.add('drag-over-below');
      }
    });

    item.addEventListener('dragleave', () => {
      item.classList.remove('drag-over-above', 'drag-over-below');
    });

    item.addEventListener('drop', (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (!dragSrcEl || item === dragSrcEl) return;

      list.querySelectorAll('.col-toggle-item').forEach(el => el.classList.remove('drag-over-above', 'drag-over-below'));

      const rect = item.getBoundingClientRect();
      const midY = rect.top + rect.height / 2;
      if (e.clientY < midY) {
        list.insertBefore(dragSrcEl, item);
      } else {
        list.insertBefore(dragSrcEl, item.nextSibling);
      }

      // Update column order from DOM order
      const newOrder = [...list.querySelectorAll('.col-toggle-item[data-col-id]')].map(el => el.dataset.colId);
      state.columnOrder = newOrder;
      saveColumnOrder();
      renderTableHeader();
      renderNews();
    });

    item.addEventListener('dragend', () => {
      item.classList.remove('dragging');
      list.querySelectorAll('.col-toggle-item').forEach(el => el.classList.remove('drag-over-above', 'drag-over-below'));
    });
  });
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

function renderNews() {
  const container = $("#news-body");
  if (!container) return;

  const items = getFilteredItems();
  const visibleCols = getVisibleColumns();
  const colCount = visibleCols.length;

  if (items.length === 0 && !state.loading) {
    container.innerHTML = `
      <tr>
        <td colspan="${colCount}">
          <div class="empty-state">
            <div class="icon">\u25C7</div>
            <div>No items match current filters</div>
            <div style="font-size:11px">Try adjusting sentiment or source filters</div>
          </div>
        </td>
      </tr>`;
    return;
  }

  const rows = items.map((item) => {
    const isNewItem = state.newIds.has(item.id);
    const isFresh = isNew(item.fetched_at);
    const rowClass = isNewItem ? "news-row-new" : "";
    const dupBadge = item.duplicate ? '<span class="badge-dup">DUP</span>' : '';
    const cells = visibleCols.map(col => renderCell(col.id, item, isFresh, dupBadge)).join('');
    return `<tr class="${rowClass}" data-id="${item.id}">${cells}</tr>`;
  });

  container.innerHTML = rows.join("");
  updateSentimentFilters();
  updateItemCount();
}

function renderSkeleton() {
  const container = $("#news-body");
  if (!container) return;
  const visibleCols = getVisibleColumns();
  const rows = Array.from({ length: 15 }, () => {
    const cells = visibleCols.map(col => {
      const w = col.id === 'headline' ? (200 + Math.random() * 200)
        : col.id === 'summary' ? (100 + Math.random() * 100)
        : (50 + Math.random() * 30);
      return `<td><div class="skeleton-block" style="width:${w}px"></div></td>`;
    }).join('');
    return `<tr class="skeleton-row">${cells}</tr>`;
  });
  container.innerHTML = rows.join("");
}

function renderEmpty(message) {
  const container = $("#news-body");
  if (!container) return;
  const colCount = getVisibleColumns().length;
  container.innerHTML = `
    <tr>
      <td colspan="${colCount}">
        <div class="loading-state">
          <div class="loading-spinner"></div>
          <div>${escapeHtml(message)}</div>
        </div>
      </td>
    </tr>`;
}

function renderSources() {
  const container = $("#source-list");
  if (!container) return;

  if (!state.sources.length) {
    // Show all feed names from a static list
    const feedNames = [
      "CNBC", "CNBC_World", "Reuters_Business", "MarketWatch", "MarketWatch_Markets",
      "Investing_com", "Yahoo_Finance", "Nasdaq", "SeekingAlpha", "Benzinga",
      "AP_News", "Bloomberg_Business", "Bloomberg_Markets",
      "BBC_Business", "Google_News_Business"
    ];
    container.innerHTML = feedNames.map((name) => `
      <label class="source-item">
        <input type="checkbox" checked data-source="${name}">
        <span>${name.replace(/_/g, " ")}</span>
        <span class="source-count">--</span>
      </label>`).join("");
  } else {
    container.innerHTML = state.sources.map((s) => `
      <label class="source-item">
        <input type="checkbox" checked data-source="${s.name}">
        <span>${s.name.replace(/_/g, " ")}</span>
        <span class="source-count">${s.total_items}</span>
      </label>`).join("");
  }

  // Bind change events
  container.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
    cb.addEventListener("change", () => {
      updateSourceFilter();
      renderNews();
    });
  });
}

function updateSourceFilter() {
  const unchecked = new Set();
  const allChecked = [];
  $$('#source-list input[type="checkbox"]').forEach((cb) => {
    if (!cb.checked) {
      unchecked.add(cb.dataset.source);
    } else {
      allChecked.push(cb.dataset.source);
    }
  });
  // If all are checked, sources is empty (meaning "all")
  if (unchecked.size === 0) {
    state.filter.sources = new Set();
  } else {
    state.filter.sources = new Set(allChecked);
  }
}

function updateSentimentFilters() {
  const counts = getSentimentCounts();
  const countEls = {
    all: $("#sentiment-count-all"),
    bullish: $("#sentiment-count-bullish"),
    bearish: $("#sentiment-count-bearish"),
    neutral: $("#sentiment-count-neutral"),
  };
  Object.entries(countEls).forEach(([key, el]) => {
    if (el) el.textContent = counts[key] || 0;
  });
}

function updateItemCount() {
  const el = $("#total-items");
  if (el) {
    const filtered = getFilteredItems();
    el.textContent = filtered.length;
  }
}

function updateHeaderStats() {
  if (!state.stats) return;
  const el = $("#total-items");
  if (el && state.filter.sentiment === "all" && state.filter.sources.size === 0 && !state.filter.query) {
    el.textContent = state.stats.total_items;
  }
  const feedCountEl = $("#feed-count");
  if (feedCountEl) feedCountEl.textContent = state.stats.feed_count;
  const avgSentEl = $("#avg-sentiment");
  if (avgSentEl) {
    const score = state.stats.avg_sentiment_score;
    avgSentEl.textContent = (score >= 0 ? "+" : "") + score.toFixed(3);
    avgSentEl.style.color = score > 0.05 ? "var(--green)" : score < -0.05 ? "var(--red)" : "var(--yellow)";
  }
}

function updateConnectionStatus(connected) {
  const dot = $("#connection-dot");
  const label = $("#connection-label");
  if (dot) {
    dot.className = connected ? "status-dot connected" : "status-dot disconnected";
  }
  if (label) {
    label.textContent = connected ? "LIVE" : "DISCONNECTED";
  }
}

function updateStatusBar() {
  const lastRefreshEl = $("#last-refresh");
  if (lastRefreshEl && state.lastRefresh) {
    lastRefreshEl.textContent = formatTime(state.lastRefresh);
  }
  const ipsEl = $("#items-per-sec");
  if (ipsEl) {
    ipsEl.textContent = state.itemsPerSecond;
  }
}

// ---------------------------------------------------------------------------
// Clock
// ---------------------------------------------------------------------------

function updateClock() {
  const el = $("#clock");
  if (!el) return;
  const now = new Date();
  const time = now.toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
  const date = now.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric", year: "numeric" });
  el.textContent = `${date}  ${time}`;
}

// ---------------------------------------------------------------------------
// Auto-refresh
// ---------------------------------------------------------------------------

function startAutoRefresh() {
  stopAutoRefresh();
  state.refreshTimer = setInterval(() => {
    fetchNews();
  }, state.refreshInterval);
}

function stopAutoRefresh() {
  if (state.refreshTimer) {
    clearInterval(state.refreshTimer);
    state.refreshTimer = null;
  }
}

// ---------------------------------------------------------------------------
// Event Handlers
// ---------------------------------------------------------------------------

function bindEvents() {
  // Sentiment filter buttons
  $$(".sentiment-filter-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const value = btn.dataset.sentiment;
      state.filter.sentiment = value;
      $$(".sentiment-filter-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      renderNews();
    });
  });

  // Search input
  const searchInput = $("#search-input");
  if (searchInput) {
    let debounceTimer;
    searchInput.addEventListener("input", (e) => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        state.filter.query = e.target.value.trim();
        renderNews();
      }, 150);
    });
  }

  // Date range inputs
  const dateFrom = $("#date-from");
  const dateTo = $("#date-to");
  if (dateFrom) {
    dateFrom.addEventListener("change", (e) => {
      state.filter.dateFrom = e.target.value;
      fetchNews();
    });
  }
  if (dateTo) {
    dateTo.addEventListener("change", (e) => {
      state.filter.dateTo = e.target.value;
      fetchNews();
    });
  }
  const clearDateBtn = $("#btn-clear-dates");
  if (clearDateBtn) {
    clearDateBtn.addEventListener("click", () => {
      state.filter.dateFrom = "";
      state.filter.dateTo = "";
      if (dateFrom) dateFrom.value = "";
      if (dateTo) dateTo.value = "";
      fetchNews();
    });
  }

  // Hide duplicates toggle
  const hideDupsCb = $("#hide-duplicates");
  if (hideDupsCb) {
    hideDupsCb.addEventListener("change", (e) => {
      state.filter.hideDuplicates = e.target.checked;
      renderNews();
    });
  }

  // Refresh button
  const refreshBtn = $("#btn-refresh");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", forceRefresh);
  }

  // Refresh interval selector
  const intervalSelect = $("#refresh-interval");
  if (intervalSelect) {
    intervalSelect.addEventListener("change", (e) => {
      state.refreshInterval = parseInt(e.target.value, 10);
      startAutoRefresh();
    });
  }

  // API docs button
  const docsBtn = $("#btn-docs");
  if (docsBtn) {
    docsBtn.addEventListener("click", () => toggleModal(true));
  }

  // Modal close
  const modalClose = $("#modal-close");
  if (modalClose) {
    modalClose.addEventListener("click", () => toggleModal(false));
  }

  const modalOverlay = $("#modal-overlay");
  if (modalOverlay) {
    modalOverlay.addEventListener("click", (e) => {
      if (e.target === modalOverlay) toggleModal(false);
    });
  }

  // Column settings button
  const colSettingsBtn = $('#btn-col-settings');
  if (colSettingsBtn) {
    colSettingsBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      toggleColumnSettings();
      if (state.columnSettingsOpen) renderColumnSettings();
    });
  }

  // Close column settings on outside click
  document.addEventListener('click', (e) => {
    if (state.columnSettingsOpen && !e.target.closest('#column-settings-wrap')) {
      toggleColumnSettings(false);
    }
  });

  // Detail modal — row click (event delegation)
  const newsBody = $("#news-body");
  if (newsBody) {
    newsBody.addEventListener("click", (e) => {
      // Don't intercept link clicks — let them open in new tab
      if (e.target.closest("a")) return;
      // Ticker badge click → open company profile modal
      const badge = e.target.closest(".ticker-badge[data-ticker]");
      if (badge) {
        e.stopPropagation();
        openCompanyProfile(badge.dataset.ticker);
        return;
      }
      const row = e.target.closest("tr[data-id]");
      if (!row) return;
      const itemId = row.dataset.id;
      const item = state.items.find((i) => String(i.id) === itemId);
      if (item) openDetailModal(item);
    });
  }

  // Detail modal close
  const detailClose = $("#detail-modal-close");
  if (detailClose) {
    detailClose.addEventListener("click", closeDetailModal);
  }
  const detailOverlay = $("#detail-modal-overlay");
  if (detailOverlay) {
    detailOverlay.addEventListener("click", (e) => {
      if (e.target === detailOverlay) closeDetailModal();
    });
  }

  // Company profile modal close
  const cpClose = $("#company-profile-close");
  if (cpClose) {
    cpClose.addEventListener("click", closeCompanyProfile);
  }
  const cpOverlay = $("#company-profile-overlay");
  if (cpOverlay) {
    cpOverlay.addEventListener("click", (e) => {
      if (e.target === cpOverlay) closeCompanyProfile();
    });
  }

  // Sound toggle
  const soundBtn = $("#btn-sound");
  if (soundBtn) {
    soundBtn.addEventListener("click", () => {
      state.soundEnabled = !state.soundEnabled;
      soundBtn.classList.toggle("active", state.soundEnabled);
      soundBtn.title = state.soundEnabled ? "Sound alerts ON" : "Sound alerts OFF";
      const icon = soundBtn.querySelector(".sound-icon");
      if (icon) {
        icon.innerHTML = state.soundEnabled
          ? '<path d="M11 5L6 9H2v6h4l5 4V5z"/><path d="M19.07 4.93a10 10 0 010 14.14M15.54 8.46a5 5 0 010 7.07"/>'
          : '<path d="M11 5L6 9H2v6h4l5 4V5z"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/>';
      }
    });
  }

  // Hamburger
  const hamburgerBtn = $("#hamburger-btn");
  if (hamburgerBtn) {
    hamburgerBtn.addEventListener("click", toggleSidebar);
  }

  const sidebarBackdrop = $("#sidebar-backdrop");
  if (sidebarBackdrop) {
    sidebarBackdrop.addEventListener("click", () => toggleSidebar(false));
  }

  // Keyboard shortcuts
  document.addEventListener("keydown", (e) => {
    // Don't intercept when typing in inputs
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.tagName === "SELECT") {
      if (e.key === "Escape") {
        e.target.blur();
      }
      return;
    }

    switch (e.key.toLowerCase()) {
      case "r":
        e.preventDefault();
        forceRefresh();
        break;
      case "f":
        e.preventDefault();
        const si = $("#search-input");
        if (si) si.focus();
        break;
      case "1":
        e.preventDefault();
        setSentimentFilter("all");
        break;
      case "2":
        e.preventDefault();
        setSentimentFilter("bullish");
        break;
      case "3":
        e.preventDefault();
        setSentimentFilter("bearish");
        break;
      case "4":
        e.preventDefault();
        setSentimentFilter("neutral");
        break;
      case "escape":
        if (state.companyProfileOpen) closeCompanyProfile();
        else if (state.detailModalOpen) closeDetailModal();
        else if (state.modalOpen) toggleModal(false);
        if (state.sidebarOpen) toggleSidebar(false);
        break;
    }
  });

  // Copy API URL
  const apiUrlEl = $("#api-url");
  if (apiUrlEl) {
    apiUrlEl.addEventListener("click", () => {
      const url = `${API}/news`;
      if (navigator.clipboard) {
        navigator.clipboard.writeText(url).then(() => {
          apiUrlEl.textContent = "Copied!";
          setTimeout(() => {
            apiUrlEl.textContent = `${API}/news`;
          }, 1500);
        });
      }
    });
  }
}

function setSentimentFilter(value) {
  state.filter.sentiment = value;
  $$(".sentiment-filter-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.sentiment === value);
  });
  renderNews();
}

function toggleSidebar(forceState) {
  const open = typeof forceState === "boolean" ? forceState : !state.sidebarOpen;
  state.sidebarOpen = open;
  const sidebar = $(".sidebar");
  const backdrop = $("#sidebar-backdrop");
  if (sidebar) sidebar.classList.toggle("open", open);
  if (backdrop) backdrop.classList.toggle("open", open);
}

function toggleModal(open) {
  state.modalOpen = open;
  const overlay = $("#modal-overlay");
  if (overlay) overlay.classList.toggle("open", open);
  // Populate API base URL in docs
  if (open) {
    $$(".api-base-url").forEach((el) => {
      el.textContent = window.location.origin + window.location.pathname.replace(/\/[^/]*$/, "");
    });
  }
}

// ---------------------------------------------------------------------------
// Detail Modal (Ticker Recommendation)
// ---------------------------------------------------------------------------

function openDetailModal(item) {
  state.detailItem = item;
  state.detailModalOpen = true;

  const overlay = $("#detail-modal-overlay");
  if (!overlay) return;

  const isMax = state.userTier === "max";
  let content = "";

  // Article context — always shown
  content += `<div class="detail-article">
    <h3 class="detail-headline">${escapeHtml(item.title || "Untitled")}</h3>
    <div class="detail-meta">
      <span class="source-tag">${escapeHtml(item.source || "")}</span>
      <span class="detail-time">${formatTime(item.published)} \u00B7 ${timeAgo(item.published)}</span>
    </div>
  </div>`;

  if (!isMax) {
    // Non-Max users see upgrade prompt
    content += `<div class="detail-upgrade">
      <div class="detail-upgrade-icon">\u25C7</div>
      <h4>Ticker Recommendations</h4>
      <p>Upgrade to Max to see AI ticker recommendations, risk assessment, and trading signals for every article.</p>
      <a href="/pricing" class="detail-upgrade-btn">Upgrade to Max</a>
    </div>`;
  } else if (!item.ai_analyzed) {
    // Max user but analysis hasn't run
    content += `<div class="detail-pending">
      <div class="detail-pending-icon">\u25C7</div>
      <p>Analysis pending</p>
      <span>AI analysis has not yet been run on this article.</span>
    </div>`;
  } else if (!item.target_asset) {
    // Max user, analyzed but no ticker recommendation
    content += `<div class="detail-pending">
      <div class="detail-pending-icon">\u2014</div>
      <p>No recommendation</p>
      <span>AI analysis did not identify a tradeable ticker for this article.</span>
    </div>`;
  } else {
    // Full ticker recommendation
    const confidencePct = item.confidence != null ? Math.round(item.confidence * 100) : "\u2014";
    const riskRaw = (item.risk_level || "").toLowerCase();
    const riskColor = riskRaw === "low" ? "green" : riskRaw === "high" ? "red" : "yellow";
    const tradeableLabel = item.tradeable ? "YES" : "NO";
    const tradeableClass = item.tradeable ? "yes" : "no";
    const sentClass = (item.sentiment_label || "neutral").toLowerCase();
    const sentScore = item.sentiment_score != null
      ? (item.sentiment_score >= 0 ? "+" : "") + Number(item.sentiment_score).toFixed(2)
      : "\u2014";

    content += `<div class="detail-ticker-header">
      <div class="detail-ticker-symbol">${escapeHtml(item.target_asset)}</div>
      <span class="detail-asset-type">${escapeHtml(item.asset_type || "\u2014")}</span>
    </div>
    <div class="detail-metrics">
      <div class="detail-metric">
        <div class="detail-metric-label">Sentiment</div>
        <div class="detail-metric-value">
          <span class="sentiment-badge ${sentClass}"><span class="sentiment-dot"></span>${sentClass}</span>
          <span class="detail-metric-sub">${sentScore}</span>
        </div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">Confidence</div>
        <div class="detail-metric-value detail-confidence">${confidencePct}%</div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">Risk Level</div>
        <div class="detail-metric-value">
          <span class="detail-risk ${riskColor}">${escapeHtml((item.risk_level || "\u2014").toUpperCase())}</span>
        </div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">Tradeable</div>
        <div class="detail-metric-value">
          <span class="detail-tradeable ${tradeableClass}">${tradeableLabel}</span>
        </div>
      </div>
    </div>
    <div class="detail-reasoning">
      <div class="detail-reasoning-label">Reasoning</div>
      <div class="detail-reasoning-text">${escapeHtml(item.reasoning || "No reasoning provided.")}</div>
    </div>`;
  }

  const modalBody = overlay.querySelector(".detail-modal-body");
  if (modalBody) modalBody.innerHTML = content;
  overlay.classList.add("open");
}

function closeDetailModal() {
  state.detailModalOpen = false;
  state.detailItem = null;
  const overlay = $("#detail-modal-overlay");
  if (overlay) overlay.classList.remove("open");
}

// ---------------------------------------------------------------------------
// Company Profile Modal
// ---------------------------------------------------------------------------

async function openCompanyProfile(symbol) {
  state.companyProfileOpen = true;
  state.companyProfileSymbol = symbol;
  state.companyProfileData = null;
  state.companyProfileLoading = true;

  const overlay = $("#company-profile-overlay");
  if (!overlay) return;

  // Update title
  const titleEl = $("#company-profile-title");
  if (titleEl) titleEl.textContent = `// ${symbol.toUpperCase()}`;

  // Show loading state
  const body = $("#company-profile-body");
  if (body) {
    body.innerHTML = `<div class="cp-loading">
      <div class="cp-loading-row"><div class="skeleton" style="width:60%;height:24px"></div></div>
      <div class="cp-loading-row"><div class="skeleton" style="width:40%;height:16px"></div></div>
      <div class="cp-loading-row" style="margin-top:16px"><div class="skeleton" style="width:100%;height:80px"></div></div>
      <div class="cp-loading-grid">
        <div class="skeleton" style="width:100%;height:64px"></div>
        <div class="skeleton" style="width:100%;height:64px"></div>
      </div>
    </div>`;
  }

  overlay.classList.add("open");

  // Fetch company details
  try {
    const res = await SignalAuth.fetch(`${API}/market/${encodeURIComponent(symbol)}/details`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.message || `HTTP ${res.status}`);
    }
    const data = await res.json();
    state.companyProfileData = data;
    state.companyProfileLoading = false;
    renderCompanyFundamentals(data);
  } catch (err) {
    state.companyProfileLoading = false;
    logger.warn("Error fetching company details for", symbol, err);
    if (body) {
      body.innerHTML = `<div class="cp-error">
        <div class="cp-error-icon">!</div>
        <p>Could not load company details for <strong>${escapeHtml(symbol)}</strong></p>
        <span>${escapeHtml(err.message)}</span>
      </div>`;
    }
  }
}

function renderCompanyFundamentals(data) {
  const body = $("#company-profile-body");
  if (!body) return;

  const logoHtml = data.logo_url
    ? `<img class="cp-logo" src="${escapeHtml(data.logo_url)}" alt="${escapeHtml(data.name)}" onerror="this.style.display='none'">`
    : "";

  const homepageHtml = data.homepage_url
    ? `<a class="cp-homepage" href="${escapeHtml(data.homepage_url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(data.homepage_url.replace(/^https?:\/\//, ""))}</a>`
    : "";

  body.innerHTML = `
    <div class="cp-header">
      ${logoHtml}
      <div class="cp-header-info">
        <div class="cp-name">${escapeHtml(data.name || "\u2014")}</div>
        <div class="cp-symbol-row">
          <span class="cp-symbol">${escapeHtml(data.symbol || "\u2014")}</span>
          ${data.sector ? `<span class="cp-sector">${escapeHtml(data.sector)}</span>` : ""}
        </div>
      </div>
    </div>
    <div class="cp-metrics">
      <div class="detail-metric">
        <div class="detail-metric-label">Market Cap</div>
        <div class="detail-metric-value">${formatMarketCap(data.market_cap)}</div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">Sector</div>
        <div class="detail-metric-value" style="font-size:12px">${escapeHtml(data.sector || "\u2014")}</div>
      </div>
    </div>
    ${data.description ? `<div class="cp-description">
      <div class="cp-desc-label">About</div>
      <p class="cp-desc-text">${escapeHtml(data.description)}</p>
    </div>` : ""}
    ${homepageHtml ? `<div class="cp-links">${homepageHtml}</div>` : ""}
  `;
}

function closeCompanyProfile() {
  state.companyProfileOpen = false;
  state.companyProfileSymbol = null;
  state.companyProfileData = null;
  state.companyProfileLoading = false;
  const overlay = $("#company-profile-overlay");
  if (overlay) overlay.classList.remove("open");
}

// ---------------------------------------------------------------------------
// Initialize
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Auth UI
// ---------------------------------------------------------------------------

function initAuth() {
  if (typeof SignalAuth === "undefined") return;

  SignalAuth.init();

  // Sign in button
  const btnSignin = $("#btn-signin");
  if (btnSignin) {
    btnSignin.addEventListener("click", () => {
      SignalAuth.showAuthModal("signin");
    });
  }

  // Sign out button
  const btnSignout = $("#btn-signout");
  if (btnSignout) {
    btnSignout.addEventListener("click", () => {
      SignalAuth.signOut();
    });
  }

  // User menu toggle
  const btnUser = $("#btn-user");
  const dropdown = $("#user-dropdown");
  if (btnUser && dropdown) {
    btnUser.addEventListener("click", (e) => {
      e.stopPropagation();
      dropdown.classList.toggle("open");
    });
    document.addEventListener("click", () => {
      dropdown.classList.remove("open");
    });
  }

  // Listen for auth state changes
  SignalAuth.onAuthChange((user) => {
    updateAuthUI(user);
  });
}

function updateAuthUI(user) {
  const btnSignin = $("#btn-signin");
  const userMenu = $("#user-menu");

  if (user) {
    // Signed in
    if (btnSignin) btnSignin.style.display = "none";
    if (userMenu) userMenu.style.display = "flex";

    const avatar = $("#user-avatar");
    const userName = $("#user-name");
    const dropdownEmail = $("#dropdown-email");

    if (avatar && user.photoURL) {
      avatar.src = user.photoURL;
      avatar.alt = user.displayName || "";
    }
    if (userName) userName.textContent = user.displayName || user.email || "";
    if (dropdownEmail) dropdownEmail.textContent = user.email || "";

    // Fetch tier info
    fetchTier();
  } else {
    // Signed out — block terminal for unauthenticated visitors
    if (btnSignin) btnSignin.style.display = "flex";
    if (userMenu) userMenu.style.display = "none";
    showUpgradeGate();
  }
}

async function fetchTier() {
  try {
    const res = await SignalAuth.fetch(`${API}/auth/tier`);
    if (!res.ok) return;
    const data = await res.json();
    const rawTier = data.tier || "free";
    const tier = rawTier === "plus" ? "pro" : rawTier;
    const features = data.features || {};
    state.userTier = tier;
    state.userFeatures = features;

    // Re-render columns with tier-based locks
    renderColumnSettings();
    renderTableHeader();
    renderNews();

    // Start market price refresh for Max users
    fetchMarketPrices();
    startPriceRefresh();

    const badge = $("#tier-badge");
    const dropdownTier = $("#dropdown-tier");

    if (badge) {
      badge.textContent = tier.toUpperCase();
      badge.className = "tier-badge" + (tier !== "free" ? " " + tier : "");
    }
    if (dropdownTier) {
      const labels = { free: "Free Plan", pro: "Pro Plan", plus: "Pro Plan" };
      dropdownTier.textContent = labels[tier] || "Free Plan";
    }

    // Client-side terminal access gate (defense in depth)
    if (features.terminal_access === false || tier === "free") {
      showUpgradeGate();
    } else {
      hideUpgradeGate();
    }
  } catch {
    // silent
  }
}

/**
 * Show a full-screen overlay blocking the terminal for Free-tier users.
 * This is a client-side safety net; the server-side redirect is the
 * primary gate.
 */
function showUpgradeGate() {
  // Avoid creating duplicate overlays
  if ($("#upgrade-gate")) return;

  const overlay = document.createElement("div");
  overlay.id = "upgrade-gate";
  overlay.style.cssText =
    "position:fixed;inset:0;z-index:10000;display:flex;align-items:center;" +
    "justify-content:center;background:rgba(1,4,9,0.95);";
  overlay.innerHTML =
    '<div style="text-align:center;max-width:420px;padding:40px;' +
    'border:1px solid rgba(48,54,61,0.8);border-radius:12px;background:#0d1117;">' +
    '<h2 style="color:#e6edf3;margin:0 0 12px;font-size:22px;">Upgrade to Pro</h2>' +
    '<p style="color:#8b949e;margin:0 0 24px;line-height:1.6;">' +
    "The SIGNAL terminal requires a Pro subscription. " +
    "Get full access to real-time news, sentiment analysis, and deduplication." +
    "</p>" +
    '<a href="/pricing" style="display:inline-block;padding:10px 28px;' +
    "background:#238636;color:#fff;border-radius:6px;text-decoration:none;" +
    'font-weight:600;font-size:14px;">View Plans</a>' +
    '<div style="margin-top:16px;">' +
    '<a href="/" style="color:#8b949e;font-size:13px;text-decoration:underline;">Back to home</a>' +
    "</div></div>";

  document.body.appendChild(overlay);

  // Stop auto-refresh to avoid unnecessary API calls
  stopAutoRefresh();
  stopPriceRefresh();
}

function hideUpgradeGate() {
  const overlay = $("#upgrade-gate");
  if (overlay) overlay.remove();
}


function init() {
  loadColumnVisibility();
  loadColumnOrder();
  loadColumnWidths();
  renderTableHeader();
  renderSkeleton();
  renderSources();
  bindEvents();
  updateClock();
  initAuth();

  // Start clock
  setInterval(updateClock, 1000);

  // Initial fetch
  fetchNews();
  fetchStats();
  fetchSources();

  // Start auto-refresh
  startAutoRefresh();

  // Periodic stats refresh (every 30s)
  setInterval(() => {
    fetchStats();
    fetchSources();
  }, 30000);
}

// Start when DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
