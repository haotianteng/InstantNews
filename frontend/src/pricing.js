/**
 * Pricing page entry — renders cards dynamically from /api/pricing
 */
import './styles/base.css';
import './styles/terminal.css';
import './styles/landing.css';
import SignalAuth from './auth.js';
import { renderPricingCards } from './pricing-renderer.js';
import { openCheckoutSidebar } from './checkout.js';

// Initialize auth
if (typeof SignalAuth !== "undefined") {
  SignalAuth.init();
}

// Show success/cancel alerts from redirect
(function () {
  var params = new URLSearchParams(window.location.search);
  var container = document.getElementById("alert-container");
  if (params.get("success") === "true") {
    container.innerHTML = '<div class="alert success">Subscription activated! Your account has been upgraded.</div>';
    history.replaceState({}, "", "/pricing");
  } else if (params.get("canceled") === "true") {
    container.innerHTML = '<div class="alert canceled">Checkout was canceled. No charges were made.</div>';
    history.replaceState({}, "", "/pricing");
  }
})();

// Render pricing cards
function loadPricingPage() {
  var userTier = null;

  function render(tier) {
    renderPricingCards("pricing-page-grid", {
      userTier: tier,
      onSubscribe: function (t) { handleSubscribe(t); },
      showDowngrade: false,
    });
  }

  if (SignalAuth.isSignedIn()) {
    SignalAuth.fetch("/api/auth/tier")
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) { render(data ? data.tier : null); })
      .catch(function () { render(null); });
  } else {
    render(null);
  }
}

SignalAuth.onAuthChange(function () { loadPricingPage(); });
loadPricingPage();

// Subscribe handler
async function handleSubscribe(tier) {
  if (!SignalAuth.isSignedIn()) {
    SignalAuth.showAuthModal("signin", { type: "checkout", tier: tier });
    return;
  }
  doCheckout(tier);
}

// Exposed globally so auth.js can call after redirect sign-in
window.doCheckout = function (tier) {
  openCheckoutSidebar(tier);
};

window.handleSubscribe = handleSubscribe;
