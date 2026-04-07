/**
 * Account page — Overview, Usage, Plans, Billing, API Keys
 */
import './styles/base.css';
import './styles/terminal.css';
import './styles/landing.css';
import SignalAuth from './auth.js';
import { fetchPricing, renderPricingCards, buildTierLookup } from './pricing-renderer.js';
import { openCheckoutSidebar } from './checkout.js';

(function () {
  "use strict";

  var loadingEl = document.getElementById("loading-state");
  var contentEl = document.getElementById("account-content");

  // Cached data
  var _tierData = null;
  var _billingData = null;
  var _pricingData = null;  // from /api/pricing
  var _tierLookup = {};     // { tierKey: tierObj }
  var _userTier = "free";

  // ── Init ──────────────────────────────────────────────────────
  if (typeof SignalAuth !== "undefined") {
    SignalAuth.init();
  }

  SignalAuth.onAuthChange(function (user) {
    if (!user) {
      window.location.href = "/?signin=account";
      return;
    }
    populateProfile(user);
    fetchAccountData();
  });

  initTabs();

  // ── Tabs ──────────────────────────────────────────────────────
  function initTabs() {
    var tabs = document.querySelectorAll(".account-tab");
    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        tabs.forEach(function (t) { t.classList.remove("active"); });
        tab.classList.add("active");
        document.querySelectorAll(".tab-panel").forEach(function (p) { p.classList.remove("active"); });
        var panel = document.getElementById("panel-" + tab.dataset.tab);
        if (panel) panel.classList.add("active");
      });
    });
  }

  // ── Profile ───────────────────────────────────────────────────
  function populateProfile(user) {
    document.getElementById("profile-name").textContent = user.displayName || "User";
    document.getElementById("profile-email").textContent = user.email || "";
    var avatarContainer = document.getElementById("avatar-container");
    if (user.photoURL) {
      avatarContainer.innerHTML = '<img class="profile-avatar" src="' + escapeHtml(user.photoURL) + '" alt="Avatar" width="56" height="56">';
    } else {
      var initials = (user.displayName || user.email || "U").charAt(0).toUpperCase();
      avatarContainer.innerHTML = '<div class="profile-avatar-placeholder">' + escapeHtml(initials) + '</div>';
    }
  }

  // ── Fetch data ────────────────────────────────────────────────
  function fetchAccountData() {
    Promise.all([
      SignalAuth.fetch("/api/auth/tier").then(function (r) { return r.json(); }),
      SignalAuth.fetch("/api/billing/status").then(function (r) { return r.json(); }),
      SignalAuth.fetch("/api/auth/me").then(function (r) { return r.ok ? r.json() : null; }),
      SignalAuth.fetch("/api/billing/payment-method").then(function (r) { return r.ok ? r.json() : null; }),
      fetchPricing(),
    ])
      .then(function (results) {
        _tierData = results[0];
        _billingData = results[1];
        var meData = results[2];
        var pmData = results[3];
        _pricingData = results[4];
        _tierLookup = buildTierLookup(_pricingData);
        _userTier = (_tierData.tier || "free").toLowerCase();

        // Merge user profile data (for created_at)
        if (meData && meData.user) {
          _tierData.created_at = meData.user.created_at;
        }
        populateOverview();
        populateUsage();
        populatePlans();
        populateBilling(pmData);
        populateKeys();
        loadingEl.style.display = "none";
        contentEl.style.display = "block";
      })
      .catch(function (err) {
        console.error("Failed to load account data:", err);
        loadingEl.innerHTML = '<div style="color:var(--red)">Failed to load account details. Please refresh.</div>';
      });
  }

  // ── Overview tab ──────────────────────────────────────────────
  function populateOverview() {
    var sub = _billingData.subscription || {};

    // Profile details
    var createdEl = document.getElementById("profile-created");
    var uidEl = document.getElementById("profile-uid");
    if (_tierData.created_at) createdEl.textContent = formatDate(_tierData.created_at);
    var fbUser = SignalAuth.getUser();
    if (fbUser && fbUser.uid) uidEl.textContent = fbUser.uid;

    // Plan badge
    var badgeEl = document.getElementById("plan-badge");
    var statusEl = document.getElementById("plan-status");
    var infoEl = document.getElementById("plan-info");
    var actionsEl = document.getElementById("plan-actions");

    badgeEl.textContent = _userTier.toUpperCase();
    badgeEl.className = "plan-badge " + _userTier;

    var status = (sub.status && sub.status !== "inactive") ? sub.status : (_userTier !== "free" ? "active" : "—");
    statusEl.textContent = status;

    // Trial banner
    if (status === "trialing" && sub.trial_end) {
      var trialBanner = document.getElementById("trial-banner");
      var daysLeft = Math.max(0, Math.ceil((new Date(sub.trial_end) - new Date()) / 86400000));
      trialBanner.innerHTML = 'Free trial &mdash; <span class="trial-days">' + daysLeft + ' day' + (daysLeft !== 1 ? 's' : '') + ' remaining</span>.';
      trialBanner.style.display = "block";
    }

    // Plan info & actions
    if (_userTier === "free") {
      infoEl.innerHTML = 'Upgrade to unlock sentiment analysis, API access, and more.';
      actionsEl.innerHTML = '<button class="btn btn-primary" id="btn-change-plan">Upgrade Plan</button>';
    } else {
      if (sub.current_period_end && status !== "trialing") {
        infoEl.innerHTML = 'Renews on <span class="highlight">' + formatDate(sub.current_period_end) + '</span>.';
      } else {
        infoEl.innerHTML = '';
      }
      actionsEl.innerHTML = '<button class="btn btn-secondary" id="btn-change-plan">Change Plan</button>';
    }
    // Bind change plan to open plans overlay
    var changePlanBtn = document.getElementById("btn-change-plan");
    if (changePlanBtn) {
      changePlanBtn.addEventListener("click", function () { openPlansOverlay(); });
    }

    // Quick usage summary — real request counts
    var overviewUsage = document.getElementById("overview-usage");
    overviewUsage.innerHTML = '<div style="color:var(--text-muted);font-size:13px;padding:12px">Loading...</div>';
    SignalAuth.fetch("/api/usage")
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (usage) {
        if (usage) {
          overviewUsage.innerHTML =
            renderUsageItem("Today", usage.today, null, "requests") +
            renderUsageItem("Last 7 Days", usage.last_7_days, null, "requests") +
            renderUsageItem("This Month", usage.this_month, null, "requests") +
            renderUsageItem("All Time", usage.all_time, null, "requests");
        } else {
          overviewUsage.innerHTML = '<div style="color:var(--text-muted);font-size:13px;padding:12px">No usage data yet.</div>';
        }
      })
      .catch(function () {
        overviewUsage.innerHTML = '<div style="color:var(--text-muted);font-size:13px;padding:12px">Unable to load usage data.</div>';
      });
  }

  // ── Usage tab ─────────────────────────────────────────────────
  function populateUsage() {
    var limits = _tierData.limits || {};
    var ml = _pricingData ? _pricingData.max_limits : {};

    // Fetch real usage data
    SignalAuth.fetch("/api/usage")
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (usage) {
        var usageGrid = document.getElementById("usage-grid");
        if (usage) {
          usageGrid.innerHTML =
            renderUsageItem("Today", usage.today, null, "requests") +
            renderUsageItem("Last 7 Days", usage.last_7_days, null, "requests") +
            renderUsageItem("This Month", usage.this_month, null, "requests") +
            renderUsageItem("All Time", usage.all_time, null, "requests");
        } else {
          usageGrid.innerHTML = '<div style="color:var(--text-muted);font-size:13px;padding:12px">No usage data yet. Start making API requests to see stats here.</div>';
        }

        var limitsGrid = document.getElementById("limits-grid");
        limitsGrid.innerHTML =
          renderUsageItem("Items per Request", limits.max_items_per_request || 50, ml.max_items_per_request, "") +
          renderUsageItem("API Rate Limit", limits.api_rate_per_minute || 30, ml.api_rate_per_minute, "req/min") +
          renderUsageItem("History Window", limits.history_days || 7, ml.history_days, "days") +
          renderUsageItem("Refresh Interval", (limits.refresh_interval_min_ms || 30000) / 1000, null, "sec");
      })
      .catch(function () {
        document.getElementById("usage-grid").innerHTML =
          '<div style="color:var(--text-muted);font-size:13px;padding:12px">Unable to load usage data.</div>';
      });
  }

  // ── Plans tab + overlay ───────────────────────────────────────
  function populatePlans() {
    var planOpts = {
      userTier: _userTier,
      onSubscribe: function (tier) {
        var sub = _billingData.subscription || {};
        var tierOrder = _pricingData.tiers.map(function (t) { return t.key; });
        var currentIdx = tierOrder.indexOf(_userTier);
        var targetIdx = tierOrder.indexOf(tier);
        var isDowngrade = targetIdx < currentIdx;

        if (isDowngrade) {
          showDowngradeNotice(tier, sub);
        } else {
          handleSubscribe(tier);
        }
      },
      showDowngrade: true,
    };

    renderPricingCards("pricing-grid", planOpts);
    renderPricingCards("plans-overlay-grid", planOpts);

    // Overlay close
    var overlay = document.getElementById("plans-overlay");
    document.getElementById("plans-close").addEventListener("click", function () { overlay.classList.remove("open"); });
    overlay.addEventListener("click", function (e) { if (e.target === overlay) overlay.classList.remove("open"); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") overlay.classList.remove("open"); });
  }

  function openPlansOverlay() {
    document.getElementById("plans-overlay").classList.add("open");
  }

  // ── Billing tab ───────────────────────────────────────────────
  function populateBilling(pmData) {
    var sub = _billingData.subscription || {};
    var detailsEl = document.getElementById("billing-details");
    var actionsEl = document.getElementById("billing-actions");
    var invoicesCard = document.getElementById("billing-invoices-card");
    var cardSlot = document.getElementById("payment-card-slot");

    // Payment card visualization
    var pm = pmData && pmData.payment_method;
    if (pm) {
      var brandLogos = {
        visa: "VISA", mastercard: "MC", amex: "AMEX",
        discover: "DISC", diners: "DINERS", jcb: "JCB", unionpay: "UP",
      };
      var brandColors = {
        visa: "linear-gradient(135deg, #1a1f3a 0%, #2a3f6f 50%, #1a1f3a 100%)",
        mastercard: "linear-gradient(135deg, #1a1a2e 0%, #3a2041 50%, #1a1a2e 100%)",
        amex: "linear-gradient(135deg, #1a2e1a 0%, #2a5540 50%, #1a2e1a 100%)",
      };
      var bg = brandColors[pm.brand] || "linear-gradient(135deg, #1a1f2e 0%, #2d3548 50%, #1a1f2e 100%)";
      var logo = brandLogos[pm.brand] || pm.brand.toUpperCase();
      var holderName = SignalAuth.getUser() ? (SignalAuth.getUser().displayName || SignalAuth.getUser().email || "CARDHOLDER") : "CARDHOLDER";
      var expStr = String(pm.exp_month).padStart(2, "0") + " / " + String(pm.exp_year).slice(-2);

      cardSlot.innerHTML =
        '<div class="card-visual" style="background:' + bg + '">' +
          '<div class="card-brand-row">' +
            '<div class="card-brand-name">' + pm.funding + '</div>' +
            '<div class="card-brand-logo">' + logo + '</div>' +
          '</div>' +
          '<div class="card-chip"></div>' +
          '<div class="card-number">&bull;&bull;&bull;&bull; &bull;&bull;&bull;&bull; &bull;&bull;&bull;&bull; ' + pm.last4 + '</div>' +
          '<div class="card-bottom">' +
            '<div><div class="card-holder">Card Holder</div><div class="card-holder-name">' + escapeHtml(holderName.toUpperCase()) + '</div></div>' +
            '<div><div class="card-expiry-label">Expires</div><div class="card-expiry">' + expStr + '</div></div>' +
          '</div>' +
        '</div>';
    } else {
      cardSlot.innerHTML = '<div class="card-visual-empty">No payment method on file</div>';
    }

    var tl = _tierLookup[_userTier];
    var tierName = tl ? tl.name : _userTier;
    var priceText = tl ? tl.display.price + tl.display.price_period : "—";

    var billingStatus = sub.status_label || sub.status;
    if (!billingStatus || billingStatus === "inactive") {
      billingStatus = _userTier !== "free" ? "Active" : "—";
    }
    var nextBilling = sub.current_period_end ? formatDate(sub.current_period_end) : (_userTier !== "free" ? "Syncing..." : "—");

    detailsEl.innerHTML =
      '<div class="billing-detail"><div class="label">Current Plan</div><div class="value">' + tierName + '</div></div>' +
      '<div class="billing-detail"><div class="label">Monthly Cost</div><div class="value">' + (_userTier === "free" ? "Free" : priceText) + '</div></div>' +
      '<div class="billing-detail"><div class="label">Status</div><div class="value">' + billingStatus + '</div></div>' +
      '<div class="billing-detail"><div class="label">Next Billing Date</div><div class="value">' + nextBilling + '</div></div>';

    if (sub.stripe_customer_id) {
      actionsEl.innerHTML = '<button class="btn btn-secondary" id="btn-billing-portal">Manage in Stripe</button>';
      setupPortalButton("btn-billing-portal");
      invoicesCard.style.display = "block";
      setupPortalButton("btn-invoices");
    } else if (_userTier === "free") {
      actionsEl.innerHTML = '<button class="btn btn-primary" id="btn-billing-upgrade">Upgrade Plan</button>';
      document.getElementById("btn-billing-upgrade").addEventListener("click", function () {
        document.querySelector('[data-tab="plans"]').click();
      });
    } else {
      actionsEl.innerHTML = '<div class="card-desc">Billing details will be available once subscription sync completes.</div>';
    }
  }

  // ── API Keys tab ──────────────────────────────────────────────
  function populateKeys() {
    var keysContent = document.getElementById("keys-content");
    var keysDesc = document.getElementById("keys-desc");
    var hasApiAccess = _tierData.features && _tierData.features.api_access;

    if (!hasApiAccess) {
      keysDesc.innerHTML = 'API access is available on <span class="highlight">Pro</span> and <span class="highlight">Max</span> plans. Upgrade to get programmatic access to the InstNews API.';
      keysContent.innerHTML = '<button class="btn btn-primary" id="btn-keys-upgrade">Upgrade for API Access</button>';
      document.getElementById("btn-keys-upgrade").addEventListener("click", function () {
        document.querySelector('[data-tab="plans"]').click();
      });
      return;
    }

    keysDesc.textContent = "Create API keys for programmatic access. Keys are shown once on creation — store them securely.";
    loadKeysList();
  }

  function loadKeysList() {
    var keysContent = document.getElementById("keys-content");
    SignalAuth.fetch("/api/keys")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var keys = data.keys || [];
        var maxKeys = data.max_keys || 5;
        var html = '';

        // Create button
        if (keys.length < maxKeys) {
          html += '<div style="margin-bottom:16px;display:flex;gap:10px;align-items:center">' +
            '<input type="text" id="new-key-name" placeholder="Key name (e.g. Trading Bot)" ' +
            'style="flex:1;padding:8px 12px;background:var(--bg-surface-2);border:1px solid var(--border);border-radius:6px;color:var(--text-primary);font-size:13px;font-family:inherit;outline:none">' +
            '<button class="btn btn-primary" id="btn-create-key">Create Key</button>' +
          '</div>';
        }

        // Newly created key display (hidden by default)
        html += '<div id="new-key-display" style="display:none;margin-bottom:16px">' +
          '<div style="background:rgba(63,185,80,0.08);border:1px solid var(--green-border);border-radius:8px;padding:14px;margin-bottom:8px">' +
            '<div style="font-size:12px;color:var(--green);margin-bottom:6px;font-weight:600">New API Key Created — Copy it now, it won\'t be shown again!</div>' +
            '<div class="api-key-row"><span class="key-value" id="new-key-value" style="font-size:12px"></span>' +
            '<button class="btn-copy" id="btn-copy-new-key">Copy</button></div>' +
          '</div>' +
        '</div>';

        // Existing keys list
        if (keys.length === 0) {
          html += '<div style="color:var(--text-muted);font-size:13px;padding:12px 0">No API keys yet. Create one above.</div>';
        } else {
          keys.forEach(function (k) {
            html += '<div class="api-key-row" style="margin-bottom:8px">' +
              '<div style="flex:1">' +
                '<div style="font-size:13px;color:var(--text-primary);font-weight:500">' + escapeHtml(k.name) + '</div>' +
                '<div style="font-size:11px;color:var(--text-muted);margin-top:2px">' +
                  escapeHtml(k.key_prefix) + '...' +
                  ' &middot; Created ' + formatDate(k.created_at) +
                  (k.last_used_at ? ' &middot; Last used ' + formatDate(k.last_used_at) : ' &middot; Never used') +
                '</div>' +
              '</div>' +
              '<button class="btn-copy" data-revoke-id="' + k.id + '" style="color:var(--red);border-color:var(--red-border)">Revoke</button>' +
            '</div>';
          });
        }

        html += '<div class="api-key-note">' + keys.length + ' of ' + maxKeys + ' keys used. ' +
          'Use the <code style="background:var(--bg-surface-2);padding:2px 6px;border-radius:3px;font-size:11px">X-API-Key</code> header to authenticate.</div>';

        keysContent.innerHTML = html;

        // Bind create
        var createBtn = document.getElementById("btn-create-key");
        if (createBtn) {
          createBtn.addEventListener("click", function () { createApiKey(); });
          document.getElementById("new-key-name").addEventListener("keydown", function (e) {
            if (e.key === "Enter") createApiKey();
          });
        }

        // Bind revoke buttons using event delegation
        keysContent.addEventListener("click", function (e) {
          var revokeBtn = e.target.closest("[data-revoke-id]");
          if (!revokeBtn) return;

          var keyId = revokeBtn.getAttribute("data-revoke-id");
          var row = revokeBtn.closest(".api-key-row");
          var originalHTML = row.innerHTML;

          row.style.background = "rgba(248,81,73,0.06)";
          row.style.borderColor = "var(--red-border)";
          row.innerHTML =
            '<div style="flex:1;font-size:13px;color:var(--red)">Revoke this key? Integrations using it will stop working.</div>' +
            '<div style="display:flex;gap:6px">' +
              '<button class="btn-copy" data-confirm-revoke="' + keyId + '" style="color:var(--red);border-color:var(--red-border)">Revoke</button>' +
              '<button class="btn-copy" data-cancel-revoke="' + keyId + '">Cancel</button>' +
            '</div>';
        });

        keysContent.addEventListener("click", function (e) {
          var confirmBtn = e.target.closest("[data-confirm-revoke]");
          if (confirmBtn) {
            revokeApiKey(confirmBtn.getAttribute("data-confirm-revoke"));
            return;
          }
          var cancelBtn = e.target.closest("[data-cancel-revoke]");
          if (cancelBtn) {
            // Reload the full key list to restore clean state
            loadKeysList();
          }
        });
      })
      .catch(function () {
        keysContent.innerHTML = '<div style="color:var(--red);font-size:13px">Failed to load API keys.</div>';
      });
  }

  function createApiKey() {
    var nameInput = document.getElementById("new-key-name");
    var name = (nameInput ? nameInput.value.trim() : "") || "Untitled Key";
    var btn = document.getElementById("btn-create-key");
    if (btn) { btn.disabled = true; btn.textContent = "Creating..."; }

    SignalAuth.fetch("/api/keys", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name }),
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
      .then(function (result) {
        if (!result.ok) {
          alert(result.data.error || "Failed to create key.");
          if (btn) { btn.disabled = false; btn.textContent = "Create Key"; }
          return;
        }
        // Reload list and show the new key
        loadKeysList();
        setTimeout(function () {
          var display = document.getElementById("new-key-display");
          var valueEl = document.getElementById("new-key-value");
          if (display && valueEl) {
            valueEl.textContent = result.data.key;
            display.style.display = "block";
            var copyBtn = document.getElementById("btn-copy-new-key");
            if (copyBtn) {
              copyBtn.addEventListener("click", function () {
                navigator.clipboard.writeText(result.data.key).then(function () {
                  copyBtn.textContent = "Copied!";
                  setTimeout(function () { copyBtn.textContent = "Copy"; }, 2000);
                });
              });
            }
          }
        }, 100);
      })
      .catch(function () {
        alert("Network error. Please try again.");
        if (btn) { btn.disabled = false; btn.textContent = "Create Key"; }
      });
  }

  function revokeApiKey(keyId) {
    SignalAuth.fetch("/api/keys/" + keyId, { method: "DELETE" })
      .then(function (r) {
        if (r.ok) { loadKeysList(); }
        else { r.json().then(function (d) { alert(d.error || "Failed to revoke key."); }); }
      })
      .catch(function () { alert("Network error."); });
  }

  // ── Helpers ───────────────────────────────────────────────────

  function renderUsageItem(label, value, max, unit) {
    var pct = max ? Math.min(100, Math.round((value / max) * 100)) : null;
    var barClass = pct !== null ? (pct > 90 ? "critical" : pct > 70 ? "warn" : "") : "";
    var html = '<div class="usage-item">';
    html += '<div class="usage-label">' + label + '</div>';
    html += '<div class="usage-value">' + value + (unit ? ' <span class="usage-unit">' + unit + '</span>' : '') + '</div>';
    if (pct !== null) {
      html += '<div class="usage-bar-track"><div class="usage-bar-fill ' + barClass + '" style="width:' + pct + '%"></div></div>';
      html += '<div class="usage-detail">' + value + ' of ' + max + ' (' + pct + '% of max tier)</div>';
    }
    html += '</div>';
    return html;
  }

  function showDowngradeNotice(targetTier, sub) {
    var tl = _tierLookup[targetTier];
    var targetName = tl ? tl.name : targetTier;
    var effectiveDate = sub.current_period_end ? formatDate(sub.current_period_end) : "the end of your current billing period";

    // Remove existing notice if any
    var existing = document.getElementById("downgrade-notice");
    if (existing) existing.remove();

    var notice = document.createElement("div");
    notice.id = "downgrade-notice";
    notice.style.cssText = "background:rgba(248,81,73,0.08);border:1px solid var(--red-border);border-radius:10px;padding:16px 20px;margin-top:16px;color:var(--red);font-size:13px;line-height:1.6;";
    notice.innerHTML =
      '<strong>Downgrade to ' + targetName + '</strong><br>' +
      'Your account will be downgraded to the <strong>' + targetName + '</strong> plan effective <strong>' + effectiveDate + '</strong>. ' +
      'You will retain access to your current plan features until then.' +
      '<div style="margin-top:12px;display:flex;gap:8px">' +
        '<button class="btn btn-danger" id="btn-confirm-downgrade">Confirm Downgrade</button>' +
        '<button class="btn btn-outline" id="btn-cancel-downgrade">Cancel</button>' +
      '</div>';

    // Insert after the plans grid
    var plansGrid = document.getElementById("pricing-grid");
    if (plansGrid) {
      plansGrid.parentNode.insertBefore(notice, plansGrid.nextSibling);
    }
    // Also show in overlay
    var overlayGrid = document.getElementById("plans-overlay-grid");
    if (overlayGrid) {
      var overlayNotice = notice.cloneNode(true);
      overlayNotice.id = "downgrade-notice-overlay";
      overlayGrid.parentNode.insertBefore(overlayNotice, overlayGrid.nextSibling);
      overlayNotice.querySelector("#btn-confirm-downgrade").addEventListener("click", function () { confirmDowngrade(sub); });
      overlayNotice.querySelector("#btn-cancel-downgrade").addEventListener("click", function () { overlayNotice.remove(); });
    }

    document.getElementById("btn-confirm-downgrade").addEventListener("click", function () { confirmDowngrade(sub); });
    document.getElementById("btn-cancel-downgrade").addEventListener("click", function () {
      notice.remove();
      var on = document.getElementById("downgrade-notice-overlay");
      if (on) on.remove();
    });
  }

  function confirmDowngrade(sub) {
    if (sub.stripe_customer_id) {
      openPortal();
    } else {
      alert("To complete the downgrade, please contact support@instnews.net");
    }
  }

  function handleSubscribe(tier) {
    if (!SignalAuth.isSignedIn()) {
      SignalAuth.showAuthModal("signin", { type: "checkout", tier: tier });
      return;
    }
    doCheckout(tier);
  }

  function doCheckout(tier) {
    openCheckoutSidebar(tier);
  }

  function openPortal() {
    SignalAuth.fetch("/api/billing/portal", { method: "POST" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.url) window.location.href = data.url;
        else alert(data.error || "Unable to open billing portal.");
      })
      .catch(function () { alert("Network error. Please try again."); });
  }

  function setupPortalButton(elementId) {
    var btn = document.getElementById(elementId);
    if (!btn) return;
    btn.addEventListener("click", function () {
      btn.disabled = true;
      var originalText = btn.textContent;
      btn.textContent = "Redirecting...";
      SignalAuth.fetch("/api/billing/portal", { method: "POST" })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.url) { window.location.href = data.url; }
          else { alert(data.error || "Unable to open billing portal."); btn.disabled = false; btn.textContent = originalText; }
        })
        .catch(function () { alert("Network error."); btn.disabled = false; btn.textContent = originalText; });
    });
  }

  // Sign out
  var signoutBtn = document.getElementById("btn-signout");
  if (signoutBtn) {
    signoutBtn.addEventListener("click", function () {
      SignalAuth.signOut().then(function () { window.location.href = "/"; });
    });
  }

  function formatDate(isoStr) {
    if (!isoStr) return "--";
    try { return new Date(isoStr).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" }); }
    catch (e) { return isoStr.slice(0, 10); }
  }

  function escapeHtml(str) {
    var div = document.createElement("div");
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }
})();
