/**
 * admin-monitoring-helpers.js — Shared helpers used across panel stories
 * (US-009..US-013).
 *
 * These helpers are pure / side-effect-free (DOM mutation helpers that touch
 * existing elements are OK; they don't register timers, don't open sockets).
 */

// ── Status classification (shared with US-013 summary counter) ────────────
/**
 * Classify a numeric reading into one of 'ok' | 'warn' | 'crit' given two
 * ascending thresholds. `warn` and `crit` are the *minimum* values at which
 * those states begin. If `value` is null/undefined/NaN we return 'ok' (absent
 * data is not a critical condition here — the UI will show a dash).
 */
export function classifyStatus(value, warn, crit) {
  if (value === null || value === undefined) return 'ok';
  const v = Number(value);
  if (!Number.isFinite(v)) return 'ok';
  if (v >= crit) return 'crit';
  if (v >= warn) return 'warn';
  return 'ok';
}

// ── Number formatting ─────────────────────────────────────────────────────
export function formatSeconds(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '–';
  }
  const v = Number(value);
  if (v < 10) return `${v.toFixed(1)}s`;
  if (v < 600) return `${Math.round(v)}s`;
  const mins = Math.round(v / 60);
  return `${mins}m`;
}

export function formatNumber(value, opts = {}) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '–';
  }
  const v = Number(value);
  const { digits = 0 } = opts;
  if (Math.abs(v) >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (Math.abs(v) >= 1e3) return `${(v / 1e3).toFixed(1)}k`;
  return v.toFixed(digits);
}

export function formatUsd(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '–';
  }
  const v = Number(value);
  if (Math.abs(v) >= 1000) return `$${v.toFixed(0)}`;
  return `$${v.toFixed(2)}`;
}

export function formatPercent(value, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '–';
  }
  return `${(Number(value) * 100).toFixed(digits)}%`;
}

// ── Sparkline (inline SVG <polyline>) ─────────────────────────────────────
/**
 * Build an inline SVG sparkline string from a numeric series.
 *
 *   const html = sparklineSvg(values, { width: 120, height: 28 });
 *   el.innerHTML = html;
 *
 * If the series is empty, returns a faint dash. Non-finite values are
 * treated as 0 so the path remains continuous.
 */
export function sparklineSvg(values, opts = {}) {
  const {
    width = 120,
    height = 28,
    stroke = 'currentColor',
    strokeWidth = 1.25,
    fill = 'none',
  } = opts;

  const pts = Array.isArray(values) ? values.map((v) => {
    const n = Number(v);
    return Number.isFinite(n) ? n : 0;
  }) : [];

  if (pts.length === 0) {
    return `<svg class="sparkline" width="${width}" height="${height}" aria-hidden="true">`
      + `<line x1="0" y1="${height / 2}" x2="${width}" y2="${height / 2}" `
      + `stroke="var(--text-faint)" stroke-width="1" stroke-dasharray="2,2" /></svg>`;
  }

  const min = Math.min(...pts);
  const max = Math.max(...pts);
  const range = max - min || 1;
  const stepX = pts.length > 1 ? width / (pts.length - 1) : width;
  const pad = 2;
  const plotH = height - pad * 2;

  const coords = pts.map((v, i) => {
    const x = i * stepX;
    const y = pad + plotH - ((v - min) / range) * plotH;
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(' ');

  return `<svg class="sparkline" width="${width}" height="${height}" `
    + `viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">`
    + `<polyline points="${coords}" fill="${fill}" stroke="${stroke}" `
    + `stroke-width="${strokeWidth}" stroke-linecap="round" stroke-linejoin="round" />`
    + `</svg>`;
}

// ── Percentile from a series ──────────────────────────────────────────────
/**
 * Return the percentile-p value from an array of numbers. Defensive against
 * empty arrays (returns null). Used when the server hands back a Maximum
 * series and we want our own rollup client-side (rare — mostly we ask
 * CloudWatch for the stat directly).
 */
export function percentile(values, p) {
  const pts = (values || []).filter((v) => Number.isFinite(Number(v))).map(Number);
  if (pts.length === 0) return null;
  const sorted = pts.slice().sort((a, b) => a - b);
  const idx = Math.min(sorted.length - 1, Math.max(0, Math.round((p / 100) * (sorted.length - 1))));
  return sorted[idx];
}

export function sumSeries(values) {
  let total = 0;
  for (const v of values || []) {
    const n = Number(v);
    if (Number.isFinite(n)) total += n;
  }
  return total;
}

export function maxSeries(values) {
  let max = null;
  for (const v of values || []) {
    const n = Number(v);
    if (!Number.isFinite(n)) continue;
    if (max === null || n > max) max = n;
  }
  return max;
}

export function minSeries(values) {
  let min = null;
  for (const v of values || []) {
    const n = Number(v);
    if (!Number.isFinite(n)) continue;
    if (min === null || n < min) min = n;
  }
  return min;
}

// ── Escape HTML for text content (defensive) ──────────────────────────────
export function escapeHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
