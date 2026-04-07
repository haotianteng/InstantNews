/* landing.js — Interactive elements for the InstNews landing page */

import SignalAuth from './auth.js';
import { renderPricingCards } from './pricing-renderer.js';
import { openCheckoutSidebar } from './checkout.js';

// ─── Tradeable signal keywords ──────────────────────────────────
// Headlines matching these patterns get the lightning bolt icon.
const SIGNAL_PATTERNS = [
  /\bearnings?\b/i, /\brevenue\b/i, /\bguidance\b/i,
  /\bbeats?\b/i, /\bmiss(?:es)?\b/i, /\bsurpass/i,
  /\bacquisition\b/i, /\bmerger\b/i, /\bbuyout\b/i, /\btakeover\b/i, /\bM&A\b/i,
  /\bFDA\b/i, /\bapprov(?:al|ed|es)\b/i, /\breject(?:s|ed)?\b/i,
  /\btariff/i, /\bsanction/i, /\bban(?:ned|s)?\b/i,
  /\brate\s+(?:cut|hike|decision)\b/i, /\bFed\b/, /\bFOMC\b/,
  /\bIPO\b/i, /\bspin.?off\b/i, /\bbuyback\b/i,
  /\bupgrade[ds]?\b/i, /\bdowngrade[ds]?\b/i,
  /\bsupply.?chain\b/i, /\bshortage\b/i, /\bdisruption\b/i,
  /\bTrump\b/, /\bPowell\b/, /\bMusk\b/, /\bHuang\b/, /\bBessent\b/,
  /\brecord\s+high\b/i, /\brecord\s+low\b/i, /\bcrash/i, /\bsurg(?:e[ds]?|ing)\b/i,
  /\bplunge[ds]?\b/i, /\bsoar(?:s|ed|ing)?\b/i, /\brally/i,
];

function isTradeable(title) {
  return SIGNAL_PATTERNS.some(function (p) { return p.test(title); });
}

// ─── Navbar ─────────────────────────────────────────────────────
var hamburger = document.getElementById("nav-hamburger");
var navLinks = document.getElementById("nav-links");
if (hamburger) {
  hamburger.addEventListener("click", function () {
    navLinks.classList.toggle("open");
  });
}
// Close mobile nav on link click
if (navLinks) {
  navLinks.querySelectorAll("a").forEach(function (a) {
    a.addEventListener("click", function () {
      navLinks.classList.remove("open");
    });
  });
}

// Sticky nav background on scroll
var nav = document.getElementById("nav");
window.addEventListener("scroll", function () {
  if (window.scrollY > 40) {
    nav.style.background = "rgba(10, 14, 20, 0.95)";
  } else {
    nav.style.background = "rgba(10, 14, 20, 0.85)";
  }
});

// ─── Auth integration ──────────────────────────────────────────
function initAuth() {
  if (typeof SignalAuth === "undefined") return;
  SignalAuth.init();

  var navActions = document.getElementById("nav-actions");
  var navSignin = document.getElementById("nav-signin");
  var navCta = document.getElementById("nav-cta");
  var heroCta = document.getElementById("hero-signup");
  var ctaCta = document.getElementById("cta-signup");
  var demoCta = document.getElementById("demo-open-terminal");

  function updateAuthUI() {
    if (SignalAuth.isSignedIn()) {
      // Signed in: show Account + Terminal links
      if (navSignin) { navSignin.textContent = "Account"; navSignin.style.display = ""; navSignin.onclick = function () { window.location.href = "/account"; }; }
      if (navCta) { navCta.textContent = "Open Terminal"; navCta.onclick = function () { window.location.href = "/terminal"; }; }
      if (heroCta) { heroCta.onclick = function () { window.location.href = "/terminal"; }; }
      if (ctaCta) { ctaCta.textContent = "Open Terminal"; ctaCta.onclick = function () { window.location.href = "/terminal"; }; }
      if (demoCta) { demoCta.onclick = function () { window.location.href = "/terminal"; }; }
    } else {
      // Signed out: show Sign In + Create Account buttons
      if (navSignin) {
        navSignin.textContent = "Sign In";
        navSignin.style.display = "";
        navSignin.onclick = function () { SignalAuth.showAuthModal("signin"); };
      }
      if (navCta) {
        navCta.textContent = "Create Account";
        navCta.onclick = function () { SignalAuth.showAuthModal("signup", { type: "navigate", url: "/terminal" }); };
      }
      if (heroCta) {
        heroCta.onclick = function () { SignalAuth.showAuthModal("signup", { type: "navigate", url: "/terminal" }); };
      }
      if (ctaCta) {
        ctaCta.onclick = function () { SignalAuth.showAuthModal("signup", { type: "navigate", url: "/terminal" }); };
      }
      if (demoCta) {
        demoCta.onclick = function () { SignalAuth.showAuthModal("signup", { type: "navigate", url: "/terminal" }); };
      }
    }
  }

  SignalAuth.onAuthChange(function () {
    updateAuthUI();
    loadPricing();
  });
  updateAuthUI();
}

// ─── Load pricing cards from API ────────────────────────────────
function loadPricing() {
  var userTier = null;
  if (SignalAuth.isSignedIn()) {
    SignalAuth.fetch("/api/auth/tier")
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        userTier = data ? data.tier : null;
        _renderPricing(userTier);
      })
      .catch(function () { _renderPricing(null); });
  } else {
    _renderPricing(null);
  }
}

function _renderPricing(userTier) {
  renderPricingCards("landing-pricing-grid", {
    userTier: userTier,
    onSubscribe: function (tier) { window.handleSubscribe(tier); },
    showDowngrade: false,
  });
}

// ─── Stripe checkout (pricing) ─────────────────────────────────
// Exposed globally so auth.js can call it after redirect sign-in
window.doCheckout = function (tier) {
  openCheckoutSidebar(tier);
};

window.handleSubscribe = function (tier) {
  if (typeof SignalAuth === "undefined") return;
  if (!SignalAuth.isSignedIn()) {
    // Show auth modal with checkout intent as pending action.
    // After email sign-in, the pending checkout runs immediately.
    // After Google redirect sign-in, auth.js runs it automatically.
    SignalAuth.showAuthModal("signin", { type: "checkout", tier: tier });
  } else {
    window.doCheckout(tier);
  }
};

// ─── Hero stats ─────────────────────────────────────────────────
function loadStats() {
  fetch("/api/stats")
    .then(function (r) { return r.json(); })
    .then(function (data) {
      var items = document.getElementById("stat-items");
      if (items) items.textContent = formatNumber(data.total_items);
    })
    .catch(function () {});
}

function formatNumber(n) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
  if (n >= 1000) return (n / 1000).toFixed(1) + "K";
  return String(n);
}

// ─── Render a news item row ──────────────────────────────────────
function renderNewsItem(item) {
  var time = new Date(item.published);
  var hh = String(time.getHours()).padStart(2, "0");
  var mm = String(time.getMinutes()).padStart(2, "0");
  var tradeable = isTradeable(item.title || "");
  var source = (item.source || "").replace(/_/g, " ");
  var title = item.title || "";
  var link = item.link || "#";
  // Sentiment may be stripped for free/anonymous users
  var label = item.sentiment_label || "neutral";
  var score = item.sentiment_score;
  var scoreText = (score != null && score !== undefined)
    ? (score >= 0 ? "+" : "") + score.toFixed(2)
    : "";
  return { hh: hh, mm: mm, tradeable: tradeable, source: source, title: title, link: link, label: label, scoreText: scoreText };
}

// ─── Terminal preview (hero) ────────────────────────────────────
function loadTerminalPreview() {
  fetch("/api/news?limit=10")
    .then(function (r) {
      if (!r.ok) throw new Error("API returned " + r.status);
      return r.json();
    })
    .then(function (data) {
      var body = document.getElementById("terminal-body");
      if (!body || !data.items || !data.items.length) return;
      body.innerHTML = "";
      data.items.slice(0, 10).forEach(function (item) {
        var d = renderNewsItem(item);
        var row = document.createElement("div");
        row.className = "terminal-row";
        row.innerHTML =
          '<span class="t-time">' + d.hh + ":" + d.mm + "</span>" +
          '<span class="t-bolt">' + (d.tradeable ? '<img src="./assets/lightneingClearBG.png" alt="">' : "") + "</span>" +
          '<span class="t-sentiment ' + d.label + '">' + (d.scoreText || d.label) + "</span>" +
          '<span class="t-source">' + d.source + "</span>" +
          '<span class="t-title">' + escapeHtml(d.title) + "</span>";
        body.appendChild(row);
      });
    })
    .catch(function (err) { console.warn("Terminal preview failed:", err); });
}

// ─── Live demo feed ─────────────────────────────────────────────
function loadDemoFeed() {
  fetch("/api/news?limit=20")
    .then(function (r) {
      if (!r.ok) throw new Error("API returned " + r.status);
      return r.json();
    })
    .then(function (data) {
      var rows = document.getElementById("demo-rows");
      if (!rows) return;
      if (!data.items || !data.items.length) {
        rows.innerHTML = '<div class="demo-loading"><span>No headlines available yet</span></div>';
        return;
      }
      rows.innerHTML = "";

      data.items.forEach(function (item) {
        var d = renderNewsItem(item);
        var row = document.createElement("div");
        row.className = "demo-row";
        row.innerHTML =
          '<span class="d-time">' + d.hh + ":" + d.mm + "</span>" +
          '<span class="d-signal">' + (d.tradeable ? '<img src="./assets/lightneingClearBG.png" alt="Tradeable">' : "") + "</span>" +
          '<span class="d-sentiment"><span class="' + d.label + '">' + (d.scoreText || d.label) + "</span></span>" +
          '<span class="d-source">' + d.source + "</span>" +
          '<span class="d-headline"><a href="' + escapeHtml(d.link) + '" target="_blank" rel="noopener">' + escapeHtml(d.title) + "</a></span>";
        rows.appendChild(row);
      });
    })
    .catch(function (err) {
      console.error("Live demo feed error:", err);
      var rows = document.getElementById("demo-rows");
      if (rows) rows.innerHTML = '<div class="demo-loading"><span>Unable to load live feed — check console for details</span></div>';
    });
}

// ─── Code tabs + copy button ─────────────────────────────────────
function initCodeTabs() {
  var tabs = document.querySelectorAll(".code-tab");
  var panels = document.querySelectorAll(".code-panel");

  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      var lang = tab.getAttribute("data-lang");
      tabs.forEach(function (t) { t.classList.remove("active"); });
      panels.forEach(function (p) { p.classList.remove("active"); });
      tab.classList.add("active");
      var target = document.querySelector('.code-panel[data-lang="' + lang + '"]');
      if (target) target.classList.add("active");
    });
  });

  // Copy button
  var copyBtn = document.getElementById("code-copy-btn");
  if (copyBtn) {
    copyBtn.addEventListener("click", function () {
      var activePanel = document.querySelector(".code-panel.active");
      if (!activePanel) return;
      var code = activePanel.textContent;
      navigator.clipboard.writeText(code).then(function () {
        copyBtn.classList.add("copied");
        copyBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg> Copied';
        setTimeout(function () {
          copyBtn.classList.remove("copied");
          copyBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>';
        }, 2000);
      });
    });
  }
}

// ─── Smooth scroll for anchor links ─────────────────────────────
document.querySelectorAll('a[href^="#"]').forEach(function (link) {
  link.addEventListener("click", function (e) {
    var target = document.querySelector(link.getAttribute("href"));
    if (target) {
      e.preventDefault();
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });
});

// ─── Utilities ──────────────────────────────────────────────────
function escapeHtml(str) {
  var el = document.createElement("span");
  el.textContent = str;
  return el.innerHTML;
}

// ─── Init ───────────────────────────────────────────────────────
initAuth();
initCodeTabs();
loadStats();
loadTerminalPreview();
loadDemoFeed();
loadPricing();
