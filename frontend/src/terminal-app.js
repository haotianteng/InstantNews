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
  soundEnabled: false,
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
// Rendering
// ---------------------------------------------------------------------------

function renderNews() {
  const container = $("#news-body");
  if (!container) return;

  const items = getFilteredItems();

  if (items.length === 0 && !state.loading) {
    container.innerHTML = `
      <tr>
        <td colspan="5">
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
    const pubTime = formatTime(item.published);
    const ago = timeAgo(item.published);
    const dupBadge = item.duplicate ? '<span class="badge-dup">DUP</span>' : '';

    return `<tr class="${rowClass}" data-id="${item.id}">
      <td class="cell-time" title="${ago}">${pubTime}</td>
      <td><span class="sentiment-badge ${item.sentiment_label}"><span class="sentiment-dot"></span>${item.sentiment_label}</span></td>
      <td><span class="source-tag">${escapeHtml(item.source || "")}</span></td>
      <td class="cell-headline">
        <a href="${escapeHtml(item.link || "#")}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.title || "Untitled")}</a>${isFresh ? '<span class="badge-new">NEW</span>' : ''}${dupBadge}
      </td>
      <td class="cell-summary">${escapeHtml(truncate(item.summary, 120))}</td>
    </tr>`;
  });

  container.innerHTML = rows.join("");
  updateSentimentFilters();
  updateItemCount();
}

function renderSkeleton() {
  const container = $("#news-body");
  if (!container) return;
  const rows = Array.from({ length: 15 }, (_, i) => {
    const w1 = 50 + Math.random() * 20;
    const w2 = 200 + Math.random() * 200;
    const w3 = 100 + Math.random() * 100;
    return `<tr class="skeleton-row">
      <td><div class="skeleton-block" style="width:${w1}px"></div></td>
      <td><div class="skeleton-block" style="width:60px"></div></td>
      <td><div class="skeleton-block" style="width:80px"></div></td>
      <td><div class="skeleton-block" style="width:${w2}px"></div></td>
      <td><div class="skeleton-block" style="width:${w3}px"></div></td>
    </tr>`;
  });
  container.innerHTML = rows.join("");
}

function renderEmpty(message) {
  const container = $("#news-body");
  if (!container) return;
  container.innerHTML = `
    <tr>
      <td colspan="5">
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
        if (state.modalOpen) toggleModal(false);
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
    const features = data.features || {};
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
}

function hideUpgradeGate() {
  const overlay = $("#upgrade-gate");
  if (overlay) overlay.remove();
}

function init() {
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
