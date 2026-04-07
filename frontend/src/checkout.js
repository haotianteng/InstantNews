/**
 * Stripe Embedded Checkout — sidebar overlay.
 * Loads Stripe.js, creates an embedded checkout session, mounts in a sidebar.
 */
import SignalAuth from './auth.js';

var _stripe = null;
var _checkout = null;

/**
 * Initialize Stripe.js (lazy-loads the script).
 */
function loadStripeJs() {
  if (_stripe) return Promise.resolve(_stripe);
  if (window.Stripe) {
    return _getPublishableKey().then(function (pk) {
      _stripe = window.Stripe(pk);
      return _stripe;
    });
  }
  return new Promise(function (resolve, reject) {
    var script = document.createElement("script");
    script.src = "https://js.stripe.com/v3/";
    script.onload = function () {
      _getPublishableKey().then(function (pk) {
        _stripe = window.Stripe(pk);
        resolve(_stripe);
      }).catch(reject);
    };
    script.onerror = function () { reject(new Error("Failed to load Stripe.js")); };
    document.head.appendChild(script);
  });
}

function _getPublishableKey() {
  return fetch("/api/billing/config")
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (!data.publishable_key) throw new Error("Stripe publishable key not configured");
      return data.publishable_key;
    });
}

/**
 * Ensure the sidebar DOM exists (inject if needed).
 */
function ensureSidebar() {
  if (document.getElementById("checkout-sidebar")) return;

  var style = document.createElement("style");
  style.textContent =
    '.checkout-sidebar{position:fixed;inset:0;z-index:99999;display:none;background:rgba(1,4,9,0.7);backdrop-filter:blur(4px)}' +
    '.checkout-sidebar.open{display:flex;justify-content:flex-end}' +
    '.checkout-sidebar-panel{width:480px;max-width:100%;height:100%;background:#0d1117;border-left:1px solid #30363d;overflow-y:auto;display:flex;flex-direction:column}' +
    '.checkout-sidebar-header{display:flex;align-items:center;justify-content:space-between;padding:16px 20px;border-bottom:1px solid #30363d}' +
    '.checkout-sidebar-title{font-size:16px;font-weight:600;color:#e6edf3}' +
    '.checkout-sidebar-close{background:none;border:none;color:#8b949e;font-size:22px;cursor:pointer;padding:4px 8px;border-radius:4px}' +
    '.checkout-sidebar-close:hover{color:#e6edf3;background:#21262d}' +
    '#checkout-mount{flex:1;padding:20px;min-height:400px}';
  document.head.appendChild(style);

  var sidebar = document.createElement("div");
  sidebar.id = "checkout-sidebar";
  sidebar.className = "checkout-sidebar";
  sidebar.innerHTML =
    '<div class="checkout-sidebar-panel">' +
      '<div class="checkout-sidebar-header">' +
        '<span class="checkout-sidebar-title">Complete Your Purchase</span>' +
        '<button class="checkout-sidebar-close" id="checkout-sidebar-close">&times;</button>' +
      '</div>' +
      '<div id="checkout-mount"></div>' +
    '</div>';
  document.body.appendChild(sidebar);

  document.getElementById("checkout-sidebar-close").addEventListener("click", closeCheckoutSidebar);
  sidebar.addEventListener("click", function (e) {
    if (e.target === sidebar) closeCheckoutSidebar();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && sidebar.classList.contains("open")) closeCheckoutSidebar();
  });
}

/**
 * Open the embedded checkout sidebar for a given tier.
 */
export function openCheckoutSidebar(tier) {
  ensureSidebar();
  var mountEl = document.getElementById("checkout-mount");
  mountEl.innerHTML = '<div style="text-align:center;padding:40px;color:#8b949e">Loading checkout...</div>';
  document.getElementById("checkout-sidebar").classList.add("open");

  // Get client_secret from backend
  SignalAuth.fetch("/api/billing/checkout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tier: tier, embedded: true }),
  })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.error) {
        mountEl.innerHTML = '<div style="text-align:center;padding:40px;color:#f85149">' + data.error + '</div>';
        return;
      }
      if (!data.client_secret) {
        // Fallback to redirect mode if embedded not supported
        if (data.url) {
          window.location.href = data.url;
          return;
        }
        mountEl.innerHTML = '<div style="text-align:center;padding:40px;color:#f85149">Checkout unavailable.</div>';
        return;
      }
      return loadStripeJs().then(function (stripe) {
        mountEl.innerHTML = "";
        return stripe.initEmbeddedCheckout({
          clientSecret: data.client_secret,
        });
      }).then(function (checkout) {
        _checkout = checkout;
        checkout.mount("#checkout-mount");
      });
    })
    .catch(function (err) {
      console.error("Checkout error:", err);
      mountEl.innerHTML = '<div style="text-align:center;padding:40px;color:#f85149">Unable to load checkout. Please try again.</div>';
    });
}

function closeCheckoutSidebar() {
  var sidebar = document.getElementById("checkout-sidebar");
  if (sidebar) sidebar.classList.remove("open");
  if (_checkout) {
    _checkout.destroy();
    _checkout = null;
  }
}
