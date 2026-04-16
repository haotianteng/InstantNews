/**
 * Admin panel — Dashboard, User Management, Test Accounts, Audit Log
 */
import './styles/base.css';
import './styles/admin.css';
import SignalAuth from './auth.js';

// ── State ────────────────────────────────────────────────────────
var _currentUserId = null;
var _currentUserRole = null;
var _currentUserSelfId = null;
var _usersOffset = 0;
var _usersLimit = 50;

// ── Live Ops Clock ────────────────────────────────────────────────
(function startOpsClock() {
  var days = ["SUN","MON","TUE","WED","THU","FRI","SAT"];
  function tick() {
    var el = document.getElementById("ops-clock");
    if (!el) return;
    var n = new Date();
    var d = days[n.getUTCDay()];
    var hh = String(n.getUTCHours()).padStart(2,"0");
    var mm = String(n.getUTCMinutes()).padStart(2,"0");
    var ss = String(n.getUTCSeconds()).padStart(2,"0");
    el.textContent = d + " " + hh + ":" + mm + ":" + ss + " UTC";
  }
  tick();
  setInterval(tick, 1000);
})();

// ── Auth Init ────────────────────────────────────────────────────
SignalAuth.init();
SignalAuth.onAuthChange(function (user) {
  if (user) {
    document.getElementById("admin-auth").style.display = "none";
    document.getElementById("admin-app").style.display = "flex";
    document.getElementById("sidebar-email").textContent = user.email;
    // Fetch current admin's role before loading dashboard
    SignalAuth.fetch("/api/auth/me").then(function(r) { return r.json(); }).then(function(d) {
      if (d.user) {
        _currentUserRole = d.user.role || "user";
        _currentUserSelfId = d.user.id;
      }
      loadDashboard();
    }).catch(function() {
      loadDashboard();
    });
  } else {
    document.getElementById("admin-auth").style.display = "flex";
    document.getElementById("admin-app").style.display = "none";
  }
});

document.getElementById("admin-signin").addEventListener("click", function () {
  SignalAuth.signInWithGoogle();
});
document.getElementById("admin-signout").addEventListener("click", function () {
  SignalAuth.signOut();
});

// ── Navigation ───────────────────────────────────────────────────
document.querySelectorAll(".nav-item").forEach(function (item) {
  item.addEventListener("click", function (e) {
    e.preventDefault();
    navigateTo(item.dataset.page);
  });
});

function navigateTo(page) {
  // Hide all pages
  document.querySelectorAll(".page").forEach(function (p) { p.style.display = "none"; });

  // Update nav active state (only for nav items, not sub-pages)
  var navItem = document.querySelector('[data-page="' + page + '"]');
  if (navItem) {
    document.querySelectorAll(".nav-item").forEach(function (i) { i.classList.remove("active"); });
    navItem.classList.add("active");
  }

  // Show target page
  var target = document.getElementById("page-" + page);
  if (target) target.style.display = "block";

  if (page === "dashboard") loadDashboard();
  else if (page === "users") { _usersOffset = 0; loadUsers(); }
  else if (page === "audit") loadAuditLog();
}

// ── API Helper ───────────────────────────────────────────────────
function api(path, options) {
  options = options || {};
  options.headers = options.headers || {};
  var token = SignalAuth.getToken();
  if (token) options.headers["Authorization"] = "Bearer " + token;
  return fetch("/admin/api" + path, options);
}

// ── Dashboard ────────────────────────────────────────────────────
// Refresh dashboard button
document.getElementById("btn-refresh-dash").addEventListener("click", function () { loadDashboard(); });

function loadDashboard() {
  var now = new Date();
  var updEl = document.getElementById("dash-updated");
  if (updEl) updEl.textContent = "REFRESHED " + now.toISOString().slice(11,19) + "Z";

  api("/stats").then(function (r) { return r.json(); }).then(function (d) {
    if (d.error) { showAccessDenied(); return; }

    var u = d.users;
    document.getElementById("s-total").textContent = fmt(u.total);
    document.getElementById("s-total-sub").textContent = u.test + " test accounts";
    document.getElementById("s-active").textContent = fmt(u.active_today);
    document.getElementById("s-new").textContent = fmt(u.new_this_month);
    document.getElementById("s-mrr").textContent = "$" + fmt(Math.round(d.mrr));
    document.getElementById("s-news").textContent = fmt(d.news.total);
    document.getElementById("s-ai").textContent = fmt(d.news.ai_analyzed);
    document.getElementById("s-keys").textContent = fmt(d.api_keys);
    document.getElementById("s-test").textContent = fmt(u.test);

    renderTierChart(u.by_tier, u.total);
  }).catch(function () { showAccessDenied(); });

  api("/stats/signups?days=30").then(function (r) { return r.json(); }).then(function (d) {
    if (d.signups) renderSignupChart(d.signups);
  });

  // System health card
  loadSystemHealth();

  // Recent admin activity
  api("/audit-log?limit=5").then(function (r) { return r.json(); }).then(function (d) {
    var el = document.getElementById("recent-activity");
    if (!el) return;
    if (!d.log || d.log.length === 0) {
      el.innerHTML = '<div style="color:var(--text-muted);font-size:13px">No admin actions yet.</div>';
      return;
    }
    el.innerHTML = d.log.map(function (row) {
      return '<div class="activity-item" style="margin-bottom:6px">' +
        '<span class="action-badge">' + esc(row.action) + '</span>' +
        '<span class="activity-meta" style="margin-left:6px">' + esc(row.admin.split("@")[0]) + ' · ' + timeAgo(row.at) + '</span>' +
      '</div>';
    }).join("");
  });

  // Background sync health check
  api("/sync/check").then(function (r) { return r.json(); }).then(function (d) {
    var banner = document.getElementById("sync-banner");
    if (!banner) return;
    if (!d.healthy && d.orphaned_count > 0) {
      banner.innerHTML = '<div class="sync-alert sync-alert--red">⚠ ' + d.orphaned_count + ' orphaned DB records found. <a href="#" id="goto-sync" style="color:var(--red);font-weight:700;text-decoration:underline">Users → Sync Check</a></div>';
      banner.style.display = "block";
      document.getElementById("goto-sync").addEventListener("click", function (e) {
        e.preventDefault();
        navigateTo("users");
        setTimeout(function () { document.getElementById("btn-sync-check").click(); }, 100);
      });
    } else if (d.test_skipped > 0) {
      banner.innerHTML = '<div class="sync-alert">⚠ ' + d.test_skipped + ' test accounts have legacy fake UIDs. <a href="#" id="goto-sync2" style="color:var(--amber);font-weight:700;text-decoration:underline">Run Sync Repair</a></div>';
      banner.style.display = "block";
      document.getElementById("goto-sync2").addEventListener("click", function (e) {
        e.preventDefault();
        navigateTo("users");
        setTimeout(function () { document.getElementById("btn-sync-check").click(); }, 100);
      });
    }
  }).catch(function () {});
}

function showAccessDenied() {
  document.getElementById("page-dashboard").innerHTML =
    '<div style="padding:60px;text-align:center;color:var(--red)">Access denied. Your account does not have admin privileges.</div>';
}

function renderTierChart(tiers, total) {
  var el = document.getElementById("tier-chart");
  var items = [
    { label: "Free", key: "free", color: "var(--text-muted)" },
    { label: "Pro", key: "pro", color: "var(--green)" },
    { label: "Max", key: "max", color: "var(--cyan)" },
  ];
  el.innerHTML = items.map(function (item) {
    var count = tiers[item.key] || 0;
    var pct = total > 0 ? Math.round((count / total) * 100) : 0;
    var barPct = total > 0 ? Math.max(2, Math.round((count / total) * 100)) : 0;
    return '<div class="tier-row">' +
      '<span class="tier-row-label">' + item.label + '</span>' +
      '<div class="tier-bar-track"><div class="tier-bar-fill" style="width:' + barPct + '%;background:' + item.color + '"></div></div>' +
      '<span class="tier-row-count">' + fmt(count) + ' (' + pct + '%)</span>' +
    '</div>';
  }).join("");
}

function renderSignupChart(signups) {
  var el = document.getElementById("signup-chart");
  if (!signups || signups.length === 0) {
    el.innerHTML = '<div style="color:var(--text-muted);font-size:13px;padding:20px 0">No signup data yet.</div>';
    return;
  }
  var max = Math.max.apply(null, signups.map(function (s) { return s.count; })) || 1;

  // Show last 30 days, fill missing with 0
  var dataMap = {};
  signups.forEach(function (s) { dataMap[s.date] = s.count; });

  var bars = [];
  for (var i = 29; i >= 0; i--) {
    var d = new Date();
    d.setDate(d.getDate() - i);
    var dateStr = d.toISOString().slice(0, 10);
    var count = dataMap[dateStr] || 0;
    var h = Math.max(2, Math.round((count / max) * 60));
    var label = d.getDate() === 1 || i === 0 ? d.toLocaleDateString("en-US", {month:"short", day:"numeric"}) : "";
    bars.push('<div class="bar-col" title="' + dateStr + ': ' + count + ' signups">' +
      '<div class="bar-fill" style="height:' + h + 'px"></div>' +
      '<div class="bar-label">' + label + '</div>' +
    '</div>');
  }
  el.innerHTML = '<div class="bar-chart">' + bars.join("") + '</div>';
}

function loadSystemHealth() {
  var el = document.getElementById("system-health");
  if (!el) return;

  // Fetch news stats for feed freshness
  Promise.all([
    fetch("/api/stats").then(function (r) { return r.json(); }),
    api("/stats").then(function (r) { return r.json(); }),
  ]).then(function (results) {
    var newsStats = results[0];
    var adminStats = results[1];
    var lastRefresh = newsStats.last_refresh;
    var freshness = lastRefresh ? timeSince(lastRefresh) : "Unknown";
    var isFresh = lastRefresh && (Date.now() - new Date(lastRefresh).getTime()) < 120000; // < 2 min

    var aiPct = adminStats.news && adminStats.news.total > 0
      ? Math.round((adminStats.news.ai_analyzed / adminStats.news.total) * 100) : 0;

    el.innerHTML =
      healthRow("News Feed", isFresh ? "green" : "yellow", "Last refresh: " + freshness) +
      healthRow("AI Analysis", aiPct > 50 ? "green" : "yellow", aiPct + "% of articles analyzed") +
      healthRow("Database", "green", adminStats.users.total + " users, " + (adminStats.news.total || 0) + " articles") +
      healthRow("Auth", "green", "Firebase SDK active");
  }).catch(function () {
    el.innerHTML = healthRow("Status", "yellow", "Could not fetch health data");
  });
}

function healthRow(label, status, detail) {
  var dotClass = { green: "status-dot--green", yellow: "status-dot--amber", red: "status-dot--red" }[status] || "status-dot--amber";
  var lblClass  = { green: "health-status-label--green", yellow: "health-status-label--amber", red: "health-status-label--red" }[status] || "health-status-label--amber";
  var statusTxt = { green: "NOMINAL", yellow: "DEGRADED", red: "FAULT" }[status] || "UNKNOWN";
  return '<div class="health-row">' +
    '<span class="status-dot ' + dotClass + '"></span>' +
    '<span class="health-system-name">' + esc(label) + '</span>' +
    '<span class="health-detail">' + esc(detail) + '</span>' +
    '<span class="health-status-label ' + lblClass + '">' + statusTxt + '</span>' +
  '</div>';
}

function timeSince(iso) {
  var diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return Math.floor(diff) + "s ago";
  if (diff < 3600) return Math.floor(diff / 60) + "m ago";
  return Math.floor(diff / 3600) + "h ago";
}

// ── Users ─────────────────────────────────────────────────────────
function loadUsers() {
  var search = document.getElementById("user-search").value;
  var tier = document.getElementById("filter-tier").value;
  var status = document.getElementById("filter-status").value;
  var testOnly = document.getElementById("filter-test").checked;

  var params = "?limit=" + _usersLimit + "&offset=" + _usersOffset;
  if (search) params += "&q=" + encodeURIComponent(search);
  if (tier) params += "&tier=" + tier;
  if (status) params += "&status=" + status;
  if (testOnly) params += "&test=true";

  api("/users" + params).then(function (r) { return r.json(); }).then(function (data) {
    var tbody = document.getElementById("users-tbody");
    if (!data.users || data.users.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="table-empty">No users found</td></tr>';
      document.getElementById("users-pagination").innerHTML = "";
      return;
    }
    tbody.innerHTML = data.users.map(function (u) {
      var status = u.disabled ? '<span class="badge badge-red">Disabled</span>'
        : u.is_test_account ? '<span class="badge badge-yellow">Test</span>'
        : '<span class="badge badge-green">Active</span>';
      var lastLogin = u.last_login_at ? timeAgo(u.last_login_at) : "Never";
      return '<tr class="user-row" data-uid="' + u.id + '">' +
        '<td><span class="user-email">' + esc(u.email) + '</span></td>' +
        '<td><span class="tier-pill tier-' + u.tier + '">' + u.tier.toUpperCase() + '</span></td>' +
        '<td><span class="role-pill role-' + (u.role || "user") + '">' + (u.role || "user").toUpperCase() + '</span></td>' +
        '<td>' + status + '</td>' +
        '<td>' + fmtDate(u.created_at) + '</td>' +
        '<td>' + lastLogin + '</td>' +
        '<td><button class="btn-view" data-uid="' + u.id + '">View →</button></td>' +
      '</tr>';
    }).join("");

    // Pagination
    var total = data.total;
    var currentPage = Math.floor(_usersOffset / _usersLimit) + 1;
    var totalPages = Math.ceil(total / _usersLimit);
    document.getElementById("users-pagination").innerHTML =
      '<span class="pagination-info">' + total + ' users</span>' +
      (currentPage > 1 ? '<button class="btn btn-sm btn-outline" id="page-prev">← Prev</button>' : '') +
      '<span class="pagination-page">Page ' + currentPage + ' / ' + totalPages + '</span>' +
      (currentPage < totalPages ? '<button class="btn btn-sm btn-outline" id="page-next">Next →</button>' : '');

    if (document.getElementById("page-prev")) {
      document.getElementById("page-prev").addEventListener("click", function () { _usersOffset -= _usersLimit; loadUsers(); });
    }
    if (document.getElementById("page-next")) {
      document.getElementById("page-next").addEventListener("click", function () { _usersOffset += _usersLimit; loadUsers(); });
    }
  });
}

// View user detail
document.getElementById("users-table").addEventListener("click", function (e) {
  var btn = e.target.closest("[data-uid]");
  if (btn) openUserDetail(parseInt(btn.getAttribute("data-uid")));
});

// Filters
var _searchTimer;
document.getElementById("user-search").addEventListener("input", function () {
  clearTimeout(_searchTimer); _searchTimer = setTimeout(function () { _usersOffset = 0; loadUsers(); }, 300);
});
["filter-tier", "filter-status", "filter-test"].forEach(function (id) {
  document.getElementById(id).addEventListener("change", function () { _usersOffset = 0; loadUsers(); });
});

// ── User Detail ──────────────────────────────────────────────────
function openUserDetail(userId) {
  _currentUserId = userId;
  navigateTo("user-detail");

  api("/users/" + userId).then(function (r) { return r.json(); }).then(function (u) {
    // Header
    document.getElementById("detail-email").textContent = u.email;

    // Copy email button
    document.getElementById("copy-email").onclick = function () {
      copyText(u.email, this);
    };

    // Copy UID button
    document.getElementById("copy-uid").onclick = function () {
      copyText(u.firebase_uid, this);
    };

    // Core fields
    document.getElementById("detail-status").innerHTML = u.disabled
      ? '<span class="badge badge-red">Disabled</span>'
      : '<span class="badge badge-green">Active</span>';
    document.getElementById("detail-tier-select").value = u.tier;
    document.getElementById("detail-role").innerHTML = '<span class="role-pill role-' + (u.role || "user") + '">' + (u.role || "user").toUpperCase() + '</span>';
    document.getElementById("detail-created").textContent = fmtDateTime(u.created_at);
    document.getElementById("detail-last-login").textContent = u.last_login_at ? fmtDateTime(u.last_login_at) : "Never";
    document.getElementById("detail-uid").textContent = u.firebase_uid;
    document.getElementById("detail-test-badge").innerHTML = u.is_test_account
      ? '<span class="badge badge-yellow">Test Account</span>' + (u.expires_at ? ' <span style="font-size:11px;color:var(--text-muted)">Expires ' + fmtDate(u.expires_at) + '</span>' : '')
      : '<span style="color:var(--text-muted);font-size:13px">No</span>';
    document.getElementById("detail-notes").value = u.notes || "";

    // Disable/Delete buttons
    var disableBtn = document.getElementById("detail-disable");
    disableBtn.textContent = u.disabled ? "Enable Account" : "Disable Account";
    disableBtn.className = u.disabled ? "btn btn-primary btn-block" : "btn btn-outline btn-block";
    document.getElementById("detail-delete").style.display = u.is_test_account ? "block" : "none";
    // Show permanent delete for superadmins (not for self)
    var permDeleteBtn = document.getElementById("detail-permanent-delete");
    if (permDeleteBtn) {
      var isSuperadmin = _currentUserRole === "superadmin";
      var isSelf = u.id === _currentUserSelfId;
      permDeleteBtn.style.display = (isSuperadmin && !isSelf) ? "block" : "none";
      permDeleteBtn.dataset.email = u.email || u.display_name || u.id;
    }

    // API Keys
    var keysEl = document.getElementById("detail-api-keys");
    var keysCount = document.getElementById("detail-keys-count");
    if (u.api_keys && u.api_keys.length > 0) {
      keysCount.textContent = "(" + u.api_keys.length + ")";
      keysEl.innerHTML = u.api_keys.map(function (k) {
        return '<div class="key-row">' +
          '<div class="key-info">' +
            '<span class="key-name">' + esc(k.name) + '</span>' +
            '<span class="key-prefix mono">' + esc(k.key_prefix) + '...</span>' +
          '</div>' +
          '<div class="key-meta">' +
            '<span>Created ' + fmtDate(k.created_at) + '</span>' +
            '<span>' + (k.last_used_at ? 'Last used ' + timeAgo(k.last_used_at) : 'Never used') + '</span>' +
          '</div>' +
        '</div>';
      }).join("");
    } else {
      keysCount.textContent = "(0)";
      keysEl.innerHTML = '<div style="color:var(--text-muted);font-size:13px">No API keys created.</div>';
    }

    // Usage stats
    var usageEl = document.getElementById("detail-usage-info");
    usageEl.innerHTML =
      '<div class="detail-row"><span class="detail-label">Total Requests</span><span>' + fmt(u.total_api_requests) + '</span></div>';

    // Activity log
    var activity = document.getElementById("detail-activity");
    if (u.activity && u.activity.length > 0) {
      activity.innerHTML = u.activity.map(function (a) {
        var details = "";
        try { var dd = JSON.parse(a.details || "{}"); details = Object.entries(dd).map(function(e) { return e[0] + ': ' + e[1]; }).join(', '); } catch(e2) {}
        return '<div class="activity-item"><span class="activity-action">' + esc(a.action) + '</span>' +
          '<span class="activity-meta"> by ' + esc((a.admin || "").split("@")[0]) + ' · ' + timeAgo(a.at) + '</span>' +
          (details ? '<span class="activity-details">' + esc(details) + '</span>' : '') + '</div>';
      }).join("");
    } else {
      activity.innerHTML = '<div style="color:var(--text-muted);font-size:13px">No activity recorded yet.</div>';
    }

    // Subscription
    var subCard = document.getElementById("detail-sub-card");
    if (u.subscription) {
      subCard.style.display = "block";
      var s = u.subscription;
      document.getElementById("detail-sub-info").innerHTML =
        '<div class="detail-row"><span class="detail-label">Status</span><span>' + (s.status_label || s.status) + '</span></div>' +
        '<div class="detail-row"><span class="detail-label">Tier</span><span>' + s.tier + '</span></div>' +
        (s.current_period_end ? '<div class="detail-row"><span class="detail-label">Renews</span><span>' + fmtDate(s.current_period_end) + '</span></div>' : '') +
        (s.cancel_at_period_end ? '<div class="detail-row"><span class="detail-label">Canceling</span><span>Yes</span></div>' : '');
    } else {
      subCard.style.display = "none";
    }
  });
}

document.getElementById("back-to-users").addEventListener("click", function () {
  navigateTo("users");
});

document.getElementById("detail-save-tier").addEventListener("click", function () {
  var tier = document.getElementById("detail-tier-select").value;
  api("/users/" + _currentUserId + "/tier", {
    method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify({tier: tier})
  }).then(function (r) { return r.json(); }).then(function (d) {
    if (d.user) { showToast("Tier updated to " + tier); openUserDetail(_currentUserId); }
    else alert(d.error || "Failed");
  });
});

document.getElementById("detail-save-notes").addEventListener("click", function () {
  var notes = document.getElementById("detail-notes").value;
  api("/users/" + _currentUserId + "/notes", {
    method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify({notes: notes})
  }).then(function () { showToast("Notes saved"); });
});

document.getElementById("detail-disable").addEventListener("click", function () {
  var btn = this;
  var isCurrentlyDisabled = btn.textContent.trim().startsWith("Enable");
  var disable = !isCurrentlyDisabled;
  api("/users/" + _currentUserId + "/disable", {
    method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify({disabled: disable})
  }).then(function (r) { return r.json(); }).then(function (d) {
    if (d.user) { showToast(disable ? "Account disabled" : "Account enabled"); openUserDetail(_currentUserId); }
    else alert(d.error || "Failed");
  });
});

document.getElementById("detail-delete").addEventListener("click", function () {
  if (!confirm("Delete this test account? This cannot be undone.")) return;
  api("/users/" + _currentUserId, {method: "DELETE"}).then(function (r) { return r.json(); }).then(function (d) {
    if (d.status === "deleted") { showToast("Account deleted"); navigateTo("users"); }
    else alert(d.error || "Failed");
  });
});

// Permanent delete (superadmin only) — requires typed confirmation
document.getElementById("detail-permanent-delete").addEventListener("click", function () {
  var emailOrName = this.dataset.email || "";
  var expected = "DELETE ACCOUNT " + emailOrName;
  var input = prompt(
    "This will PERMANENTLY delete this account and all associated data.\n\n" +
    "To confirm, type exactly:\n" + expected
  );
  if (!input || input.trim() !== expected) {
    if (input !== null) alert("Confirmation did not match. Account was NOT deleted.");
    return;
  }
  api("/users/" + _currentUserId + "/delete", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({confirmation: expected}),
  }).then(function (r) { return r.json(); }).then(function (d) {
    if (d.status === "deleted") { showToast("Account permanently deleted: " + d.email); navigateTo("users"); }
    else alert(d.error || "Failed to delete account");
  });
});

// ── Create Test Account Modal ────────────────────────────────────
document.getElementById("btn-open-create-test").addEventListener("click", function () {
  document.getElementById("create-test-modal").style.display = "flex";
  document.getElementById("ct-result").style.display = "none";
});

["close-create-test", "ct-cancel"].forEach(function (id) {
  document.getElementById(id).addEventListener("click", function () {
    document.getElementById("create-test-modal").style.display = "none";
  });
});

document.getElementById("ct-expire-check").addEventListener("change", function () {
  document.getElementById("ct-expire-days").disabled = !this.checked;
});

document.getElementById("ct-submit").addEventListener("click", function () {
  var btn = this;
  var username = document.getElementById("ct-username").value.trim() || "dev";
  var tier = document.querySelector('input[name="ct-tier"]:checked').value;
  var displayName = document.getElementById("ct-display-name").value.trim();
  var password = document.getElementById("ct-password").value;
  var notes = document.getElementById("ct-notes").value.trim();
  var expireCheck = document.getElementById("ct-expire-check").checked;
  var expireDays = expireCheck ? parseInt(document.getElementById("ct-expire-days").value) : 0;

  btn.disabled = true; btn.textContent = "Creating...";

  api("/test-accounts", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      username: username, tier: tier,
      display_name: displayName || "Test " + tier.charAt(0).toUpperCase() + tier.slice(1),
      password: password || null,
      notes: notes, expire_days: expireDays,
    }),
  }).then(function (r) { return r.json(); }).then(function (d) {
    var result = document.getElementById("ct-result");
    if (d.user) {
      result.innerHTML = '<div class="create-success">✓ Created: <strong>' + esc(d.user.email) + '</strong> (Tier: ' + d.user.tier + ')' +
        (d.password ? '<br>Password: <code style="font-family:monospace;background:rgba(63,185,80,0.1);padding:2px 6px;border-radius:4px">' + esc(d.password) + '</code>' : '') +
        '</div>';
      result.style.display = "block";
      document.getElementById("ct-password").value = "";
      loadUsers();
    } else {
      result.innerHTML = '<div class="create-error">' + esc(d.error || "Failed") + '</div>';
      result.style.display = "block";
    }
  }).finally(function () { btn.disabled = false; btn.textContent = "Create Account"; });
});

// ── Sync Check ───────────────────────────────────────────────────
document.getElementById("btn-sync-check").addEventListener("click", function () {
  var btn = this;
  var result = document.getElementById("users-sync-result");
  btn.disabled = true; btn.textContent = "Checking...";

  api("/sync/check").then(function (r) { return r.json(); }).then(function (d) {
    if (d.error) { result.innerHTML = '<div class="create-error">' + esc(d.error) + '</div>'; result.style.display = "block"; return; }

    var healthy = d.healthy;
    var alertClass = healthy ? '' : (d.orphaned_count > 0 ? ' sync-alert--red' : '');
    var html = '<div class="sync-alert' + alertClass + '">' +
      '<strong>' + (healthy ? '✓ FIREBASE ↔ DB SYNC: NOMINAL' : '⚠ SYNC ISSUES DETECTED') + '</strong><br>' +
      'Checked: ' + d.sample_checked + ' · Synced: ' + d.synced + ' · Legacy test UIDs: ' + d.test_skipped + ' · Orphaned: ' + d.orphaned_count;

    if (d.orphaned_db && d.orphaned_db.length > 0) {
      html += '<div style="margin-top:10px"><strong>Orphaned DB records (in DB, not in Firebase):</strong><ul style="margin:6px 0 0;padding-left:20px">' +
        d.orphaned_db.map(function (u) {
          return '<li style="margin:2px 0">' + esc(u.email) + ' (id=' + u.id + ', test=' + u.is_test_account + ')</li>';
        }).join("") + '</ul>';
      if (d.test_skipped > 0) {
        html += '<div style="margin-top:8px"><button class="btn btn-sm btn-danger" id="btn-repair-sync">Remove ' + d.test_skipped + ' orphaned test accounts (fake UIDs)</button></div>';
      }
      html += '</div>';
    }
    html += '</div>';
    result.innerHTML = html;
    result.style.display = "block";

    if (document.getElementById("btn-repair-sync")) {
      document.getElementById("btn-repair-sync").addEventListener("click", function () {
        if (!confirm("Delete all test accounts with fake Firebase UIDs from the DB? This cannot be undone.")) return;
        api("/sync/repair", {
          method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({confirm: true}),
        }).then(function (r) { return r.json(); }).then(function (d) {
          showToast(d.message || "Repair complete");
          document.getElementById("btn-sync-check").click();
          loadUsers();
        });
      });
    }
  }).finally(function () { btn.disabled = false; btn.textContent = "🔍 Sync Check"; });
});

// ── Audit Log ────────────────────────────────────────────────────
function loadAuditLog() {
  api("/audit-log?limit=100").then(function (r) { return r.json(); }).then(function (d) {
    var tbody = document.getElementById("audit-tbody");
    if (!d.log || d.log.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="table-empty">No audit entries yet.</td></tr>';
      return;
    }
    tbody.innerHTML = d.log.map(function (row) {
      var details = "";
      try { var dd = JSON.parse(row.details || "{}"); details = JSON.stringify(dd); } catch(e) {}
      return '<tr>' +
        '<td class="mono-sm">' + esc(row.admin) + '</td>' +
        '<td><span class="action-badge">' + esc(row.action) + '</span></td>' +
        '<td>' + (row.target_user_id || "—") + '</td>' +
        '<td class="mono-sm">' + esc(details) + '</td>' +
        '<td class="mono-sm">' + esc(row.ip || "—") + '</td>' +
        '<td>' + timeAgo(row.at) + '</td>' +
      '</tr>';
    }).join("");
  });
}

// ── Toast ────────────────────────────────────────────────────────
function showToast(msg) {
  var t = document.createElement("div");
  t.className = "toast";
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(function () { t.classList.add("toast-show"); }, 10);
  setTimeout(function () { t.classList.remove("toast-show"); setTimeout(function () { t.remove(); }, 300); }, 2500);
}

// ── Utilities ─────────────────────────────────────────────────────
function copyText(text, btn) {
  navigator.clipboard.writeText(text).then(function () {
    if (btn) {
      var orig = btn.innerHTML;
      btn.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--green)" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>';
      setTimeout(function () { btn.innerHTML = orig; }, 1500);
    }
    showToast("Copied!");
  });
}

function fmt(n) {
  if (n == null) return "—";
  return Number(n).toLocaleString();
}

function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {month:"short", day:"numeric", year:"numeric"});
}

function fmtDateTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-US", {month:"short", day:"numeric", hour:"2-digit", minute:"2-digit"});
}

function timeAgo(iso) {
  if (!iso) return "—";
  var diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "Just now";
  if (diff < 3600) return Math.floor(diff / 60) + "m ago";
  if (diff < 86400) return Math.floor(diff / 3600) + "h ago";
  if (diff < 604800) return Math.floor(diff / 86400) + "d ago";
  return fmtDate(iso);
}

function esc(str) {
  if (!str) return "";
  var d = document.createElement("div");
  d.textContent = str;
  return d.innerHTML;
}
