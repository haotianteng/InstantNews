/**
 * Shared pricing card renderer.
 * Fetches /api/pricing and renders cards into a container.
 * Used by landing.js, pricing.js, and account.js.
 */

var _cachedPricing = null;

/**
 * Fetch pricing data (cached after first call).
 * @returns {Promise<{tiers: Array, max_limits: Object}>}
 */
export function fetchPricing() {
  if (_cachedPricing) return Promise.resolve(_cachedPricing);
  return fetch("/api/pricing")
    .then(function (r) { return r.json(); })
    .then(function (data) { _cachedPricing = data; return data; });
}

/**
 * Render pricing cards into a container.
 *
 * @param {string} containerId — DOM element ID to render into
 * @param {Object} options
 * @param {string|null} options.userTier — current user tier key (e.g. "pro"), null if unknown
 * @param {Function} options.onSubscribe — called with tier key when a checkout button is clicked
 * @param {boolean} options.showDowngrade — if true, lower tiers show "Downgrade" in red
 * @returns {Promise<Object>} — resolves with pricing data
 */
export function renderPricingCards(containerId, options) {
  options = options || {};
  var userTier = options.userTier || null;
  var onSubscribe = options.onSubscribe || function () {};
  var showDowngrade = options.showDowngrade || false;

  return fetchPricing().then(function (data) {
    var container = document.getElementById(containerId);
    if (!container) return data;

    var tierOrder = data.tiers.map(function (t) { return t.key; });
    var currentIdx = userTier ? tierOrder.indexOf(userTier) : -1;
    var html = "";

    data.tiers.forEach(function (tier, idx) {
      var d = tier.display;
      var isCurrent = tier.key === userTier;
      var isDowngrade = showDowngrade && currentIdx >= 0 && idx < currentIdx;
      var isUpgrade = currentIdx >= 0 && idx > currentIdx;

      html += '<div class="price-card' + (d.featured && !isCurrent ? ' price-card-featured' : '') + (isCurrent ? ' price-card-current' : '') + '">';
      if (isCurrent) html += '<div class="price-current-label">Current Plan</div>';
      else if (d.featured) html += '<div class="price-popular">Most Popular</div>';
      html += '<div class="price-tier">' + tier.name + '</div>';

      // Price
      var priceParts = d.price.match(/^\$(\d+)(?:\.(\d+))?$/);
      if (priceParts) {
        html += '<div class="price-amount"><span class="price-currency">$</span>' + priceParts[1];
        if (priceParts[2]) html += '<span class="price-amount-sm">.' + priceParts[2] + '</span>';
        html += '<span class="price-period">' + d.price_period + '</span></div>';
      } else {
        html += '<div class="price-amount">' + d.price + '<span class="price-period">' + d.price_period + '</span></div>';
      }

      html += '<p class="price-desc">' + d.description + '</p>';
      if (d.trial_text) html += '<p class="price-trial">' + d.trial_text + '</p>';

      // Feature list
      html += '<ul class="price-features">';
      d.feature_list.forEach(function (f) {
        html += '<li class="' + (f.included ? 'included' : 'excluded') + '">' + f.text + '</li>';
      });
      html += '</ul>';

      html += '<div class="price-limits">' + d.limits_summary + '</div>';

      // CTA button
      if (isCurrent) {
        html += '<button class="btn btn-outline btn-block" disabled>Current Plan</button>';
      } else if (isDowngrade) {
        html += '<button class="btn btn-block btn-downgrade" data-tier="' + tier.key + '">Downgrade</button>';
      } else if (d.cta_action === "link") {
        html += '<a href="' + d.cta_href + '" class="btn btn-' + d.cta_style + ' btn-block">' + d.cta_label + '</a>';
      } else {
        html += '<button class="btn btn-' + d.cta_style + ' btn-block" data-tier="' + tier.key + '">' + d.cta_label + '</button>';
      }

      html += '</div>';
    });

    container.innerHTML = html;

    // Bind click handlers
    container.querySelectorAll("[data-tier]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        onSubscribe(btn.getAttribute("data-tier"));
      });
    });

    return data;
  });
}

/**
 * Build a lookup object from pricing data: { tierKey: tierObj }
 */
export function buildTierLookup(pricingData) {
  var lookup = {};
  pricingData.tiers.forEach(function (t) { lookup[t.key] = t; });
  return lookup;
}
