/**
 * Stripe Custom Checkout — sidebar panel.
 *
 * Uses Stripe Custom Checkout (ui_mode: "custom") with Payment Element
 * mounted in a sidebar panel. No redirect — payment completes in-page.
 *
 * Reference: https://docs.stripe.com/checkout/custom/quickstart
 */
import SignalAuth from './auth.js';

var _stripe = null;
var _checkout = null;

// ---------------------------------------------------------------------------
// Stripe.js loader
// ---------------------------------------------------------------------------

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
    script.src = "https://js.stripe.com/basil/stripe.js";
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

// ---------------------------------------------------------------------------
// Sidebar DOM
// ---------------------------------------------------------------------------

function ensureSidebar() {
  if (document.getElementById("checkout-sidebar")) return;

  var style = document.createElement("style");
  style.textContent =
    '#checkout-sidebar{position:fixed;inset:0;z-index:99999;display:none;background:rgba(1,4,9,0.7);backdrop-filter:blur(4px)}' +
    '#checkout-sidebar.open{display:flex;justify-content:flex-end}' +
    '.checkout-panel{width:480px;max-width:100%;height:100%;background:#0d1117;border-left:1px solid #30363d;display:flex;flex-direction:column;overflow:hidden}' +
    '.checkout-header{display:flex;align-items:center;justify-content:space-between;padding:14px 20px;border-bottom:1px solid #30363d;flex-shrink:0}' +
    '.checkout-header span{font-family:"JetBrains Mono",monospace;font-size:13px;font-weight:600;color:#e6edf3}' +
    '.checkout-close{background:none;border:1px solid #30363d;border-radius:6px;color:#8b949e;font-size:13px;cursor:pointer;padding:5px 14px;font-family:"JetBrains Mono",monospace}' +
    '.checkout-close:hover{color:#e6edf3;border-color:#8b949e;background:#161b22}' +
    '.checkout-body{flex:1;overflow-y:auto;padding:20px}' +
    '.checkout-footer{padding:16px 20px;border-top:1px solid #30363d;flex-shrink:0}' +
    '#checkout-pay-btn{width:100%;padding:12px;background:#238636;color:#fff;border:none;border-radius:6px;font-size:14px;font-weight:600;cursor:pointer;font-family:inherit}' +
    '#checkout-pay-btn:hover{background:#2ea043}' +
    '#checkout-pay-btn:disabled{opacity:0.5;cursor:not-allowed}' +
    '#checkout-error{color:#f85149;font-size:12px;margin-top:8px;min-height:18px}' +
    '#payment-element{min-height:200px}' +
    '.checkout-loading{display:flex;align-items:center;justify-content:center;height:100%;color:#8b949e;font-size:14px}' +
    '.checkout-plan{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;margin-bottom:20px}' +
    '.checkout-plan-name{font-family:"JetBrains Mono",monospace;font-size:11px;font-weight:600;color:#8b949e;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px}' +
    '.checkout-plan-price{font-size:24px;font-weight:700;color:#e6edf3}' +
    '.checkout-plan-price span{font-size:14px;font-weight:400;color:#8b949e}' +
    '.checkout-plan-trial{font-size:12px;color:#3fb950;margin-top:6px}' +
    '.checkout-plan-sep{border:none;border-top:1px solid #30363d;margin:16px 0}';
  document.head.appendChild(style);

  var sidebar = document.createElement("div");
  sidebar.id = "checkout-sidebar";
  sidebar.innerHTML =
    '<div class="checkout-panel">' +
      '<div class="checkout-header">' +
        '<span>// CHECKOUT</span>' +
        '<button class="checkout-close" id="checkout-close">Cancel</button>' +
      '</div>' +
      '<div class="checkout-body" id="checkout-body">' +
        '<div class="checkout-loading">Loading\u2026</div>' +
      '</div>' +
      '<div class="checkout-footer" id="checkout-footer" style="display:none">' +
        '<button id="checkout-pay-btn">Subscribe</button>' +
        '<div id="checkout-error"></div>' +
      '</div>' +
    '</div>';
  document.body.appendChild(sidebar);

  document.getElementById("checkout-close").addEventListener("click", closeCheckoutSidebar);
  sidebar.addEventListener("click", function (e) {
    if (e.target === sidebar) closeCheckoutSidebar();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && sidebar.classList.contains("open")) closeCheckoutSidebar();
  });
}

// ---------------------------------------------------------------------------
// Plan metadata
// ---------------------------------------------------------------------------

var PLAN_INFO = {
  pro:  { name: 'Pro', price: '$29.99', trial: '30-day free trial', btnText: 'Start Free Trial' },
  max:  { name: 'Max', price: '$89.99', trial: null, btnText: 'Subscribe \u2014 $89.99/mo' },
};

// ---------------------------------------------------------------------------
// Open
// ---------------------------------------------------------------------------

export function openCheckoutSidebar(tier) {
  ensureSidebar();
  var body = document.getElementById("checkout-body");
  var footer = document.getElementById("checkout-footer");
  var sidebar = document.getElementById("checkout-sidebar");

  body.innerHTML = '<div class="checkout-loading">Loading checkout\u2026</div>';
  footer.style.display = "none";
  sidebar.classList.add("open");
  document.body.style.overflow = "hidden";

  // Step 1: Get client_secret from backend
  SignalAuth.fetch("/api/billing/checkout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tier: tier, embedded: true }),
  })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.error) {
        body.innerHTML = '<div class="checkout-loading" style="color:#f85149">' + data.error + '</div>';
        return;
      }
      // Test accounts: upgraded directly
      if (data.test_account) {
        footer.style.display = "none";
        body.innerHTML =
          '<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;">' +
          '<div style="font-size:40px;margin-bottom:16px;">\u2705</div>' +
          '<h3 style="color:#e6edf3;margin:0 0 8px;font-size:18px;">Upgraded to ' + (data.tier || 'Max').toUpperCase() + '</h3>' +
          '<p style="color:#8b949e;margin:0 0 20px;font-size:13px;">Test account \u2014 no billing required.</p>' +
          '<button onclick="location.reload()" style="padding:10px 24px;background:#238636;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:600;">Continue</button>' +
          '</div>';
        return;
      }
      if (!data.client_secret) {
        body.innerHTML = '<div class="checkout-loading" style="color:#f85149">Checkout unavailable.</div>';
        return;
      }

      // Step 2: Initialize Stripe Custom Checkout and mount Payment Element
      var clientSecret = data.client_secret;
      var plan = PLAN_INFO[tier] || PLAN_INFO.max;
      loadStripeJs().then(function (stripe) {
        var trialHtml = plan.trial ? '<div class="checkout-plan-trial">\u2713 ' + plan.trial + ' \u2014 cancel anytime</div>' : '';
        body.innerHTML =
          '<div class="checkout-plan">' +
            '<div class="checkout-plan-name">' + plan.name + ' Plan</div>' +
            '<div class="checkout-plan-price">' + plan.price + ' <span>/month</span></div>' +
            trialHtml +
          '</div>' +
          '<div id="payment-element"></div>';
        footer.style.display = "block";
        document.getElementById("checkout-pay-btn").textContent = plan.btnText;

        var checkoutPromise = stripe.initCheckoutElementsSdk({
          fetchClientSecret: function () { return Promise.resolve(clientSecret); },
          elementsOptions: {
            appearance: {
              theme: 'night',
              variables: {
                colorPrimary: '#238636',
                colorBackground: '#0d1117',
                colorText: '#e6edf3',
                colorTextSecondary: '#8b949e',
                colorDanger: '#f85149',
                fontFamily: '"Inter", system-ui, sans-serif',
                borderRadius: '6px',
              },
            },
          },
        });

        checkoutPromise.then(function (checkout) {
          _checkout = checkout;

          // Mount Payment Element
          var paymentElement = checkout.createPaymentElement();
          paymentElement.mount("#payment-element");

          // Update button text
          try {
            var session = checkout.session();
            var amt = session && session.total ? session.total.total.amount : 0;
            if (amt > 0) {
              document.getElementById("checkout-pay-btn").textContent = "Subscribe \u2014 $" + (amt / 100).toFixed(2) + "/mo";
            }
          } catch (e) {
            // session data not available yet, keep default text
          }

          // Wire up pay button
          document.getElementById("checkout-pay-btn").addEventListener("click", function () {
            var btn = document.getElementById("checkout-pay-btn");
            var errEl = document.getElementById("checkout-error");
            btn.disabled = true;
            btn.textContent = "Processing\u2026";
            errEl.textContent = "";

            checkout.confirm().then(function (result) {
              if (result.type === "error") {
                errEl.textContent = result.error.message;
                btn.disabled = false;
                btn.textContent = plan.btnText;
              }
              // On success, Stripe redirects to return_url
            });
          });
        });
      }).catch(function (err) {
        console.error("Stripe init error:", err);
        body.innerHTML = '<div class="checkout-loading" style="color:#f85149">Failed to load payment form. Please try again.</div>';
      });
    })
    .catch(function (err) {
      console.error("Checkout error:", err);
      body.innerHTML = '<div class="checkout-loading" style="color:#f85149">Unable to load checkout. Please try again.</div>';
    });
}

// ---------------------------------------------------------------------------
// Close
// ---------------------------------------------------------------------------

function closeCheckoutSidebar() {
  var sidebar = document.getElementById("checkout-sidebar");
  if (sidebar) sidebar.classList.remove("open");
  document.body.style.overflow = "";
  if (_checkout) {
    _checkout.destroy();
    _checkout = null;
  }
  var body = document.getElementById("checkout-body");
  if (body) body.innerHTML = "";
  var footer = document.getElementById("checkout-footer");
  if (footer) footer.style.display = "none";
}
