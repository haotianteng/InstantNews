/**
 * SIGNAL — Multi-Method Authentication Module
 *
 * Email/password → backend API (works globally, including China)
 * Google OAuth → Firebase popup (global regions only)
 * WeChat QR → redirect flow (CN only, pending approval)
 *
 * Firebase SDK loaded via CDN for Google OAuth only.
 */

// ---------------------------------------------------------------------------
// Firebase Config (for Google OAuth only)
// ---------------------------------------------------------------------------

const FIREBASE_CONFIG = {
  apiKey: "AIzaSyBJO7auN184dTKUf_1_hiSPMAJm3uYvTvI",
  authDomain: "www.instnews.net",
  projectId: "instantnews-d0a72",
  storageBucket: "instantnews-d0a72.firebasestorage.app",
  messagingSenderId: "1099024008707",
  appId: "1:1099024008707:web:47340e907671f7cce67036",
  measurementId: "G-2MJ3MD0WBQ",
};

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let _currentUser = null;
let _idToken = null;       // Firebase ID token (Google OAuth only)
let _appToken = null;      // App JWT (email/password + WeChat)
let _auth = null;          // Firebase auth instance
let _onAuthChangeCallbacks = [];
let _redirectResultHandled = false;
let _region = null;        // "global" or "cn"
let _initDone = false;
let _initPromise = null;
let _pendingResetToken = null;

// ---------------------------------------------------------------------------
// Region Detection
// ---------------------------------------------------------------------------

async function _detectRegion() {
  // URL override for testing: ?region=cn or ?region=global
  try {
    var urlParams = new URLSearchParams(window.location.search);
    var override = urlParams.get("region");
    if (override === "cn" || override === "global") {
      _cacheRegion(override);
      return override;
    }
  } catch (e) {}

  // Check cache
  try {
    var cached = localStorage.getItem("signal_auth_region");
    if (cached && (cached === "global" || cached === "cn")) {
      var cachedAt = parseInt(localStorage.getItem("signal_auth_region_ts") || "0", 10);
      if (Date.now() - cachedAt < 86400000) {
        return cached;
      }
    }
  } catch (e) {}

  // Try to reach Google (if reachable, not in China)
  try {
    var controller = new AbortController();
    var timeout = setTimeout(function() { controller.abort(); }, 3000);
    await fetch("https://www.googleapis.com/identitytoolkit/v3/relyingparty/getProjectConfig?key=test", {
      signal: controller.signal,
      mode: "no-cors",
    });
    clearTimeout(timeout);
    _cacheRegion("global");
    return "global";
  } catch (e) {}

  // Ask backend
  try {
    var resp = await fetch("/api/auth/region", { signal: AbortSignal.timeout(5000) });
    if (resp.ok) {
      var data = await resp.json();
      var region = data.region || "global";
      _cacheRegion(region);
      return region;
    }
  } catch (e) {}

  _cacheRegion("cn");
  return "cn";
}

function _cacheRegion(region) {
  try {
    localStorage.setItem("signal_auth_region", region);
    localStorage.setItem("signal_auth_region_ts", String(Date.now()));
  } catch (e) {}
}

// ---------------------------------------------------------------------------
// WeChat Token Handling
// ---------------------------------------------------------------------------

function _checkWeChatToken() {
  var params = new URLSearchParams(window.location.search);

  // Check for auth token in URL (from email verification or WeChat callback)
  var urlToken = params.get("token") || params.get("wechat_token");

  if (urlToken) {
    _appToken = urlToken;
    try { localStorage.setItem("signal_app_token", urlToken); } catch (e) {}
    params.delete("token");
    params.delete("wechat_token");
    params.delete("verified");
    var cleanUrl = window.location.pathname + (params.toString() ? "?" + params.toString() : "");
    history.replaceState(null, "", cleanUrl);
    return true;
  }

  // Check localStorage for existing app token (email/password or WeChat)
  try {
    var stored = localStorage.getItem("signal_app_token");
    if (stored) {
      _appToken = stored;
      return true;
    }
  } catch (e) {}

  return false;
}

function _loadUserFromTokenAsync() {
  var token = _appToken;
  if (!token) return Promise.resolve();

  return fetch("/api/auth/me", {
    headers: { "Authorization": "Bearer " + token },
  })
    .then(function(resp) {
      if (!resp.ok) {
        _appToken = null;
        try { localStorage.removeItem("signal_app_token"); } catch (e) {}
        _currentUser = null;
        _notifyAuthChange();
        return;
      }
      return resp.json();
    })
    .then(function(data) {
      if (data && data.user) {
        _currentUser = {
          uid: null,
          email: data.user.email,
          displayName: data.user.display_name,
          photoURL: data.user.photo_url,
        };
        _notifyAuthChange();
        _hideModal();
        _runPendingAction();
      }
    })
    .catch(function(err) {
      console.warn("User load failed:", err);
      _appToken = null;
      try { localStorage.removeItem("signal_app_token"); } catch (e) {}
    });
}

// ---------------------------------------------------------------------------
// Init Implementation
// ---------------------------------------------------------------------------

async function _doInit() {
  // 1. Check for existing app token (email/password or WeChat)
  var hasToken = _checkWeChatToken();

  // 2. Wait for token validation to complete before proceeding
  if (hasToken && _appToken) {
    await _loadUserFromTokenAsync();
  }

  // 3. Detect region
  _region = await _detectRegion();

  // 4. Init Firebase for Google OAuth (global only)
  if (_region !== "cn") {
    _initFirebase();
  }

  // 5. Inject auth modal
  _injectAuthModal();

  // 6. Check for reset_token in URL → show reset password form
  try {
    var params = new URLSearchParams(window.location.search);
    var resetToken = params.get("reset_token");
    if (resetToken) {
      _pendingResetToken = resetToken;
      params.delete("reset_token");
      var cleanUrl = window.location.pathname + (params.toString() ? "?" + params.toString() : "");
      history.replaceState(null, "", cleanUrl);
      _showModal("reset");
    }
  } catch (e) {}

  // 7. Mark init as complete
  _initDone = true;
}

// ---------------------------------------------------------------------------
// Public API (exposed as window.SignalAuth)
// ---------------------------------------------------------------------------

const SignalAuth = {
  init: function () {
    _initPromise = _doInit();
    return _initPromise;
  },

  getRegion: function () {
    return _region;
  },

  signInWithGoogle: function () {
    if (!_auth) return Promise.reject(new Error("Firebase not initialized"));
    var provider = new firebase.auth.GoogleAuthProvider();
    return _auth.signInWithPopup(provider).then(async function (result) {
      if (result && result.user) {
        _currentUser = result.user;
        _idToken = await result.user.getIdToken();
        _notifyAuthChange();
        _runPendingAction();
      }
    });
  },

  signInWithWeChat: function () {
    window.location.href = "/api/auth/wechat/login";
  },

  signIn: function () {
    SignalAuth.showAuthModal("signin");
  },

  showAuthModal: function (tab, pendingAction) {
    if (pendingAction) {
      SignalAuth.setPendingAction(pendingAction);
    }
    _showModal(tab || "signin");
  },

  hideAuthModal: function () {
    _hideModal();
  },

  /** Sign up via backend email/password auth. */
  signUp: function (email, password) {
    return fetch("/api/auth/signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email, password: password }),
    }).then(function(resp) {
      return resp.json().then(function(data) {
        if (!resp.ok) throw data;
        return data;
      });
    });
  },

  /** Sign in via backend email/password auth. */
  signInWithEmail: function (email, password) {
    return fetch("/api/auth/signin", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email, password: password }),
    }).then(function(resp) {
      return resp.json().then(function(data) {
        if (!resp.ok) throw data;
        // Store token and set user
        _appToken = data.token;
        try { localStorage.setItem("signal_app_token", data.token); } catch (e) {}
        _currentUser = {
          uid: null,
          email: data.user.email,
          displayName: data.user.display_name,
          photoURL: data.user.photo_url,
        };
        _notifyAuthChange();
        return data;
      });
    });
  },

  /** Request password reset email via backend. */
  resetPassword: function (email) {
    return fetch("/api/auth/forgot-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email }),
    }).then(function(resp) {
      return resp.json().then(function(data) {
        if (!resp.ok) throw data;
        return data;
      });
    });
  },

  /** Resend email verification link. */
  resendVerification: function (email) {
    return fetch("/api/auth/resend-verification", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email }),
    }).then(function(resp) {
      return resp.json();
    });
  },

  signOut: function () {
    sessionStorage.removeItem("signalauth_pending");
    _appToken = null;
    try { localStorage.removeItem("signal_app_token"); } catch (e) {}

    if (_auth) {
      _auth.signOut();
    }

    _currentUser = null;
    _idToken = null;
    _notifyAuthChange();
  },

  getToken: function () {
    return _appToken || _idToken;
  },

  getUser: function () {
    if (!_currentUser) return null;
    return {
      uid: _currentUser.uid,
      email: _currentUser.email,
      displayName: _currentUser.displayName,
      photoURL: _currentUser.photoURL,
    };
  },

  isSignedIn: function () {
    return _currentUser !== null;
  },

  onAuthChange: function (callback) {
    _onAuthChangeCallbacks.push(callback);
  },

  setPendingAction: function (action) {
    try {
      sessionStorage.setItem("signalauth_pending", JSON.stringify(action));
    } catch (e) {}
  },

  getPendingAction: function () {
    try {
      var raw = sessionStorage.getItem("signalauth_pending");
      if (raw) {
        sessionStorage.removeItem("signalauth_pending");
        return JSON.parse(raw);
      }
    } catch (e) {}
    return null;
  },

  fetch: function (url, options) {
    options = options || {};
    options.headers = options.headers || {};
    var token = _appToken || _idToken;
    if (token) {
      options.headers["Authorization"] = "Bearer " + token;
    }
    return fetch(url, options);
  },
};

window.SignalAuth = SignalAuth;
export default SignalAuth;

// ---------------------------------------------------------------------------
// Firebase Init (Google OAuth only — global region)
// ---------------------------------------------------------------------------

function _initFirebase() {
  if (typeof firebase === "undefined") {
    console.warn("Firebase SDK not loaded");
    return;
  }

  if (!firebase.apps.length) {
    firebase.initializeApp(FIREBASE_CONFIG);
  }
  _auth = firebase.auth();

  _auth
    .getRedirectResult()
    .then(function (result) {
      _redirectResultHandled = true;
      if (result && result.user) {
        _runPendingAction();
      }
    })
    .catch(function (err) {
      _redirectResultHandled = true;
      sessionStorage.removeItem("signalauth_pending");
    });

  _auth.onAuthStateChanged(async function (user) {
    if (user) {
      _currentUser = user;
      _idToken = await user.getIdToken();
      _startTokenRefresh(user);
      _hideModal();
    } else {
      // Only clear if no app token (email/password user)
      if (!_appToken) {
        _currentUser = null;
        _idToken = null;
      }
    }
    _notifyAuthChange();
  });
}

// ---------------------------------------------------------------------------
// Internal
// ---------------------------------------------------------------------------

function _notifyAuthChange() {
  for (var i = 0; i < _onAuthChangeCallbacks.length; i++) {
    try {
      _onAuthChangeCallbacks[i](SignalAuth.getUser());
    } catch (e) {
      console.error("Auth change callback error:", e);
    }
  }
}

var _refreshTimer = null;

function _startTokenRefresh(user) {
  if (_refreshTimer) clearInterval(_refreshTimer);
  _refreshTimer = setInterval(async function () {
    try {
      _idToken = await user.getIdToken(true);
    } catch (e) {
      console.warn("Token refresh failed:", e);
    }
  }, 50 * 60 * 1000);
}

function _runPendingAction() {
  var action = SignalAuth.getPendingAction();
  if (!action) return;

  if (action.type === "checkout" && action.tier) {
    setTimeout(function () {
      if (typeof window.doCheckout === "function") {
        window.doCheckout(action.tier);
      } else if (typeof window.handleSubscribe === "function") {
        window.handleSubscribe(action.tier);
      }
    }, 500);
  } else if (action.type === "navigate" && action.url) {
    window.location.href = action.url;
  }
}

// ---------------------------------------------------------------------------
// Auth Modal
// ---------------------------------------------------------------------------

var _modalEl = null;

function _injectAuthModal() {
  if (document.getElementById("signal-auth-modal")) return;

  var style = document.createElement("style");
  style.textContent =
    '#signal-auth-overlay{position:fixed;inset:0;z-index:99999;display:none;align-items:center;justify-content:center;background:rgba(1,4,9,0.85);backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px)}' +
    '#signal-auth-overlay.open{display:flex}' +
    '#signal-auth-modal{background:#161b22;border:1px solid #30363d;border-radius:12px;width:100%;max-width:400px;padding:32px;position:relative;box-shadow:0 16px 48px rgba(0,0,0,0.4);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;color:#e6edf3}' +
    '#signal-auth-modal *{box-sizing:border-box}' +
    '.sa-close{position:absolute;top:12px;right:12px;background:none;border:none;color:#8b949e;font-size:20px;cursor:pointer;padding:4px 8px;line-height:1;border-radius:4px}' +
    '.sa-close:hover{color:#e6edf3;background:#21262d}' +
    '.sa-title{text-align:center;margin:0 0 20px;font-size:20px;font-weight:600;color:#e6edf3}' +
    '.sa-tabs{display:flex;gap:0;margin-bottom:24px;border-bottom:1px solid #30363d}' +
    '.sa-tab{flex:1;padding:10px 0;text-align:center;background:none;border:none;color:#8b949e;font-size:14px;font-weight:500;cursor:pointer;border-bottom:2px solid transparent;transition:color 0.15s,border-color 0.15s}' +
    '.sa-tab:hover{color:#e6edf3}' +
    '.sa-tab.active{color:#3fb950;border-bottom-color:#3fb950}' +
    '.sa-panel{display:none}' +
    '.sa-panel.active{display:block}' +
    '.sa-field{margin-bottom:14px}' +
    '.sa-field label{display:block;font-size:12px;font-weight:500;color:#8b949e;margin-bottom:6px;text-transform:uppercase;letter-spacing:0.5px}' +
    '.sa-field input{width:100%;padding:10px 12px;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#e6edf3;font-size:14px;outline:none;transition:border-color 0.15s}' +
    '.sa-field input:focus{border-color:#3fb950}' +
    '.sa-field input::placeholder{color:#484f58}' +
    '.sa-btn{width:100%;padding:10px 16px;border-radius:6px;font-size:14px;font-weight:600;cursor:pointer;border:none;transition:background 0.15s,opacity 0.15s}' +
    '.sa-btn:disabled{opacity:0.6;cursor:not-allowed}' +
    '.sa-btn-primary{background:#238636;color:#fff}' +
    '.sa-btn-primary:hover:not(:disabled){background:#2ea043}' +
    '.sa-btn-google{background:#21262d;color:#e6edf3;border:1px solid #30363d;display:flex;align-items:center;justify-content:center;gap:8px;margin-top:8px}' +
    '.sa-btn-google:hover:not(:disabled){background:#30363d}' +
    '.sa-btn-google svg{flex-shrink:0}' +
    '.sa-btn-wechat{background:#07C160;color:#fff;display:flex;align-items:center;justify-content:center;gap:8px;margin-top:8px}' +
    '.sa-btn-wechat:hover:not(:disabled){background:#06AD56}' +
    '.sa-btn-wechat svg{flex-shrink:0}' +
    '.sa-divider{display:flex;align-items:center;gap:12px;margin:18px 0;color:#484f58;font-size:12px}' +
    '.sa-divider::before,.sa-divider::after{content:"";flex:1;height:1px;background:#30363d}' +
    '.sa-forgot{display:inline-block;margin-top:4px;color:#58a6ff;font-size:13px;cursor:pointer;background:none;border:none;padding:0;text-decoration:none}' +
    '.sa-forgot:hover{text-decoration:underline}' +
    '.sa-error{background:rgba(248,81,73,0.1);border:1px solid rgba(248,81,73,0.4);color:#f85149;padding:10px 12px;border-radius:6px;font-size:13px;margin-bottom:14px;display:none}' +
    '.sa-error.visible{display:block}' +
    '.sa-success{background:rgba(63,185,80,0.1);border:1px solid rgba(63,185,80,0.4);color:#3fb950;padding:10px 12px;border-radius:6px;font-size:13px;margin-bottom:14px;display:none}' +
    '.sa-success.visible{display:block}' +
    '.sa-back{display:inline-flex;align-items:center;gap:4px;color:#58a6ff;font-size:13px;cursor:pointer;background:none;border:none;padding:0;margin-bottom:16px}' +
    '.sa-back:hover{text-decoration:underline}' +
    '.sa-footer{text-align:center;margin-top:16px;font-size:13px;color:#8b949e}' +
    '.sa-footer a,.sa-footer button{color:#58a6ff;cursor:pointer;background:none;border:none;padding:0;font-size:13px;text-decoration:none}' +
    '.sa-footer a:hover,.sa-footer button:hover{text-decoration:underline}' +
    '@media(max-width:480px){#signal-auth-modal{margin:16px;padding:24px;max-width:calc(100% - 32px)}}';
  document.head.appendChild(style);

  // Social button based on region
  var socialBtnSignin = _region === "cn" ? _wechatButtonHtml("sa-wechat-signin") : _googleButtonHtml("sa-google-signin");
  var socialBtnSignup = _region === "cn" ? _wechatButtonHtml("sa-wechat-signup") : _googleButtonHtml("sa-google-signup");

  var overlay = document.createElement("div");
  overlay.id = "signal-auth-overlay";
  overlay.innerHTML =
    '<div id="signal-auth-modal">' +
      '<button class="sa-close" id="sa-close" title="Close">&times;</button>' +
      '<h2 class="sa-title">Welcome to SIGNAL</h2>' +
      '<div class="sa-tabs" id="sa-tabs">' +
        '<button class="sa-tab active" data-tab="signin">Sign In</button>' +
        '<button class="sa-tab" data-tab="signup">Sign Up</button>' +
      '</div>' +
      '<div id="sa-error" class="sa-error"></div>' +
      '<div id="sa-success" class="sa-success"></div>' +

      // Sign In panel
      '<div class="sa-panel active" id="sa-panel-signin">' +
        '<form id="sa-form-signin" autocomplete="on">' +
          '<div class="sa-field"><label for="sa-signin-email">Email</label><input id="sa-signin-email" type="email" placeholder="you@example.com" autocomplete="email" required></div>' +
          '<div class="sa-field"><label for="sa-signin-password">Password</label><input id="sa-signin-password" type="password" placeholder="Enter password" autocomplete="current-password" required></div>' +
          '<button type="submit" class="sa-btn sa-btn-primary" id="sa-btn-signin">Sign In</button>' +
          '<div style="text-align:right"><button type="button" class="sa-forgot" id="sa-show-forgot">Forgot password?</button></div>' +
        '</form>' +
        '<div class="sa-divider">or</div>' +
        socialBtnSignin +
      '</div>' +

      // Sign Up panel
      '<div class="sa-panel" id="sa-panel-signup">' +
        '<form id="sa-form-signup" autocomplete="on">' +
          '<div class="sa-field"><label for="sa-signup-email">Email</label><input id="sa-signup-email" type="email" placeholder="you@example.com" autocomplete="email" required></div>' +
          '<div class="sa-field"><label for="sa-signup-password">Password</label><input id="sa-signup-password" type="password" placeholder="Min 8 characters" autocomplete="new-password" required minlength="8"></div>' +
          '<div class="sa-field"><label for="sa-signup-confirm">Confirm Password</label><input id="sa-signup-confirm" type="password" placeholder="Confirm password" autocomplete="new-password" required minlength="8"></div>' +
          '<button type="submit" class="sa-btn sa-btn-primary" id="sa-btn-signup">Create Account</button>' +
        '</form>' +
        '<div class="sa-divider">or</div>' +
        socialBtnSignup +
      '</div>' +

      // Forgot Password panel
      '<div class="sa-panel" id="sa-panel-forgot">' +
        '<button class="sa-back" id="sa-back-forgot">&larr; Back to Sign In</button>' +
        '<p style="color:#8b949e;font-size:14px;margin:0 0 16px">Enter your email and we\'ll send you a link to reset your password.</p>' +
        '<form id="sa-form-forgot">' +
          '<div class="sa-field"><label for="sa-forgot-email">Email</label><input id="sa-forgot-email" type="email" placeholder="you@example.com" autocomplete="email" required></div>' +
          '<button type="submit" class="sa-btn sa-btn-primary" id="sa-btn-forgot">Send Reset Email</button>' +
        '</form>' +
      '</div>' +

      // Reset Password panel (shown when clicking reset link from email)
      '<div class="sa-panel" id="sa-panel-reset">' +
        '<h3 style="color:#e6edf3;margin:0 0 16px;font-size:16px;text-align:center">Set New Password</h3>' +
        '<form id="sa-form-reset">' +
          '<div class="sa-field"><label for="sa-reset-password">New Password</label><input id="sa-reset-password" type="password" placeholder="Min 8 characters" autocomplete="new-password" required minlength="8"></div>' +
          '<div class="sa-field"><label for="sa-reset-confirm">Confirm Password</label><input id="sa-reset-confirm" type="password" placeholder="Confirm password" autocomplete="new-password" required minlength="8"></div>' +
          '<button type="submit" class="sa-btn sa-btn-primary" id="sa-btn-reset">Reset Password</button>' +
        '</form>' +
      '</div>' +

      '<div class="sa-footer" id="sa-footer-signin">Don\'t have an account? <button id="sa-switch-to-signup">Sign up</button></div>' +
      '<div class="sa-footer" id="sa-footer-signup" style="display:none">Already have an account? <button id="sa-switch-to-signin">Sign in</button></div>' +
    '</div>';

  document.body.appendChild(overlay);
  _modalEl = overlay;
  _bindModalEvents();
}

function _googleButtonHtml(id) {
  return '<button class="sa-btn sa-btn-google" id="' + id + '"><svg width="18" height="18" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59A14.5 14.5 0 019.5 24c0-1.59.28-3.14.76-4.59l-7.98-6.19A23.9 23.9 0 000 24c0 3.77.9 7.34 2.44 10.51l8.09-5.92z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg> Sign in with Google</button>';
}

function _wechatButtonHtml(id) {
  return '<button class="sa-btn sa-btn-wechat" id="' + id + '"><svg width="20" height="20" viewBox="0 0 24 24" fill="white"><path d="M8.691 2.188C3.891 2.188 0 5.476 0 9.53c0 2.212 1.17 4.203 3.002 5.55a.59.59 0 01.213.665l-.39 1.48c-.019.07-.048.141-.048.213 0 .163.13.295.29.295a.326.326 0 00.167-.054l1.903-1.114a.864.864 0 01.717-.098 10.16 10.16 0 002.837.403c.276 0 .543-.027.811-.05a6.29 6.29 0 01-.261-1.782c0-3.69 3.344-6.678 7.466-6.678.244 0 .484.015.72.036C16.82 4.592 13.121 2.188 8.691 2.188zm-2.6 4.408c.56 0 1.016.455 1.016 1.016 0 .56-.456 1.016-1.016 1.016a1.017 1.017 0 110-2.032zm5.22 0c.56 0 1.015.455 1.015 1.016 0 .56-.456 1.016-1.016 1.016a1.017 1.017 0 110-2.032zM16.707 9.5c-3.578 0-6.482 2.588-6.482 5.776 0 3.19 2.904 5.777 6.482 5.777a7.88 7.88 0 002.165-.306.67.67 0 01.556.076l1.47.86a.253.253 0 00.13.042.227.227 0 00.224-.228c0-.056-.022-.11-.037-.165l-.301-1.14a.457.457 0 01.165-.514C22.615 18.8 23.19 17.107 23.19 15.276c0-3.188-2.905-5.776-6.483-5.776zm-2.003 3.392c.434 0 .786.352.786.786a.786.786 0 11-.786-.786zm4.006 0c.434 0 .786.352.786.786a.786.786 0 11-.786-.786z"/></svg> Sign in with WeChat</button>';
}

function _bindModalEvents() {
  var overlay = document.getElementById("signal-auth-overlay");

  overlay.addEventListener("click", function (e) {
    if (e.target === overlay) _hideModal();
  });

  document.getElementById("sa-close").addEventListener("click", _hideModal);

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && overlay.classList.contains("open")) {
      _hideModal();
    }
  });

  var tabs = document.querySelectorAll("#sa-tabs .sa-tab");
  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () { _switchTab(tab.dataset.tab); });
  });

  document.getElementById("sa-switch-to-signup").addEventListener("click", function () { _switchTab("signup"); });
  document.getElementById("sa-switch-to-signin").addEventListener("click", function () { _switchTab("signin"); });
  document.getElementById("sa-show-forgot").addEventListener("click", function () { _switchTab("forgot"); });
  document.getElementById("sa-back-forgot").addEventListener("click", function () { _switchTab("signin"); });

  // Sign In form
  var _lastSigninEmail = "";
  document.getElementById("sa-form-signin").addEventListener("submit", function (e) {
    e.preventDefault();
    _clearMessages();
    var email = document.getElementById("sa-signin-email").value.trim();
    var password = document.getElementById("sa-signin-password").value;
    _lastSigninEmail = email;

    if (!_validateEmail(email)) { _showError("Please enter a valid email address."); return; }
    if (!password) { _showError("Please enter your password."); return; }

    var btn = document.getElementById("sa-btn-signin");
    btn.disabled = true;
    btn.textContent = "Signing in...";

    SignalAuth.signInWithEmail(email, password)
      .then(function () {
        _hideModal();
        _runPendingAction();
      })
      .catch(function (err) {
        var msg = (err && err.error) || "Sign in failed.";
        _showError(msg);
      })
      .finally(function () {
        btn.disabled = false;
        btn.textContent = "Sign In";
      });
  });


  // Sign Up form
  document.getElementById("sa-form-signup").addEventListener("submit", function (e) {
    e.preventDefault();
    _clearMessages();
    var email = document.getElementById("sa-signup-email").value.trim();
    var password = document.getElementById("sa-signup-password").value;
    var confirm = document.getElementById("sa-signup-confirm").value;

    if (!_validateEmail(email)) { _showError("Please enter a valid email address."); return; }
    if (password.length < 8) { _showError("Password must be at least 8 characters."); return; }
    if (password !== confirm) { _showError("Passwords do not match."); return; }

    var btn = document.getElementById("sa-btn-signup");
    btn.disabled = true;
    btn.textContent = "Creating account...";

    SignalAuth.signUp(email, password)
      .then(function (data) {
        _showSuccess(data.message || "Account created! Check your email to verify.");
        // Don't auto-sign-in — require email verification
        document.getElementById("sa-form-signup").reset();
      })
      .catch(function (err) {
        _showError((err && err.error) || "Sign up failed.");
      })
      .finally(function () {
        btn.disabled = false;
        btn.textContent = "Create Account";
      });
  });

  // Forgot Password form
  document.getElementById("sa-form-forgot").addEventListener("submit", function (e) {
    e.preventDefault();
    _clearMessages();
    var email = document.getElementById("sa-forgot-email").value.trim();

    if (!_validateEmail(email)) { _showError("Please enter a valid email address."); return; }

    var btn = document.getElementById("sa-btn-forgot");
    btn.disabled = true;
    btn.textContent = "Sending...";

    SignalAuth.resetPassword(email)
      .then(function (data) {
        _showSuccess(data.message || "If an account exists, reset email sent.");
        document.getElementById("sa-form-forgot").reset();
      })
      .catch(function (err) {
        _showError((err && err.error) || "Failed to send reset email.");
      })
      .finally(function () {
        btn.disabled = false;
        btn.textContent = "Send Reset Email";
      });
  });

  // Reset Password form (from email link)
  document.getElementById("sa-form-reset").addEventListener("submit", function (e) {
    e.preventDefault();
    _clearMessages();
    var password = document.getElementById("sa-reset-password").value;
    var confirm = document.getElementById("sa-reset-confirm").value;

    if (password.length < 8) { _showError("Password must be at least 8 characters."); return; }
    if (password !== confirm) { _showError("Passwords do not match."); return; }
    if (!_pendingResetToken) { _showError("Invalid reset link. Please request a new one."); return; }

    var btn = document.getElementById("sa-btn-reset");
    btn.disabled = true;
    btn.textContent = "Resetting...";

    fetch("/api/auth/reset-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: _pendingResetToken, password: password }),
    })
      .then(function (resp) { return resp.json().then(function (d) { return { ok: resp.ok, data: d }; }); })
      .then(function (result) {
        if (result.ok) {
          _showSuccess(result.data.message || "Password updated! You can now sign in.");
          _pendingResetToken = null;
          document.getElementById("sa-form-reset").reset();
          setTimeout(function () { _switchTab("signin"); }, 2000);
        } else {
          _showError(result.data.error || "Reset failed.");
        }
      })
      .catch(function () {
        _showError("An error occurred. Please try again.");
      })
      .finally(function () {
        btn.disabled = false;
        btn.textContent = "Reset Password";
      });
  });

  // Reset password confirm match validation
  var resetConfirm = document.getElementById("sa-reset-confirm");
  var resetPassword = document.getElementById("sa-reset-password");
  function _checkResetMatch() {
    var pw = resetPassword.value;
    var cf = resetConfirm.value;
    if (!cf) { resetConfirm.style.borderColor = ""; return; }
    resetConfirm.style.borderColor = pw !== cf ? "#f85149" : "#3fb950";
  }
  resetConfirm.addEventListener("input", _checkResetMatch);
  resetPassword.addEventListener("input", _checkResetMatch);

  // Social sign-in buttons
  var googleSignin = document.getElementById("sa-google-signin");
  var googleSignup = document.getElementById("sa-google-signup");
  if (googleSignin) googleSignin.addEventListener("click", function () { SignalAuth.signInWithGoogle(); });
  if (googleSignup) googleSignup.addEventListener("click", function () { SignalAuth.signInWithGoogle(); });

  var wechatSignin = document.getElementById("sa-wechat-signin");
  var wechatSignup = document.getElementById("sa-wechat-signup");
  if (wechatSignin) wechatSignin.addEventListener("click", function () { SignalAuth.signInWithWeChat(); });
  if (wechatSignup) wechatSignup.addEventListener("click", function () { SignalAuth.signInWithWeChat(); });

  // Password match validation
  var confirmInput = document.getElementById("sa-signup-confirm");
  var passwordInput = document.getElementById("sa-signup-password");
  function _checkPasswordMatch() {
    var pw = passwordInput.value;
    var cf = confirmInput.value;
    if (!cf) { confirmInput.style.borderColor = ""; return; }
    confirmInput.style.borderColor = pw !== cf ? "#f85149" : "#3fb950";
  }
  confirmInput.addEventListener("input", _checkPasswordMatch);
  passwordInput.addEventListener("input", _checkPasswordMatch);
}

function _showModal(tab) {
  var overlay = document.getElementById("signal-auth-overlay");
  if (!overlay) return;
  _clearMessages();
  _switchTab(tab || "signin");
  overlay.classList.add("open");
  setTimeout(function () {
    var panel = document.querySelector(".sa-panel.active");
    if (panel) { var input = panel.querySelector("input"); if (input) input.focus(); }
  }, 50);
}

function _hideModal() {
  var overlay = document.getElementById("signal-auth-overlay");
  if (overlay) overlay.classList.remove("open");
  _clearMessages();
}

function _switchTab(tab) {
  var tabs = document.querySelectorAll("#sa-tabs .sa-tab");
  tabs.forEach(function (t) { t.classList.toggle("active", t.dataset.tab === tab); });

  var tabsBar = document.getElementById("sa-tabs");
  var panels = document.querySelectorAll(".sa-panel");
  panels.forEach(function (p) { p.classList.remove("active"); });

  if (tab === "forgot" || tab === "reset") {
    tabsBar.style.display = "none";
    document.getElementById("sa-panel-" + tab).classList.add("active");
    document.getElementById("sa-footer-signin").style.display = "none";
    document.getElementById("sa-footer-signup").style.display = "none";
  } else {
    tabsBar.style.display = "flex";
    document.getElementById("sa-panel-" + tab).classList.add("active");
    document.getElementById("sa-footer-signin").style.display = tab === "signin" ? "block" : "none";
    document.getElementById("sa-footer-signup").style.display = tab === "signup" ? "block" : "none";
  }
  _clearMessages();
}

function _clearMessages() {
  var errEl = document.getElementById("sa-error");
  var sucEl = document.getElementById("sa-success");
  if (errEl) { errEl.textContent = ""; errEl.classList.remove("visible"); }
  if (sucEl) { sucEl.textContent = ""; sucEl.classList.remove("visible"); }
}

function _showError(msg) {
  var el = document.getElementById("sa-error");
  if (el) { el.textContent = msg; el.classList.add("visible"); }
}

function _showSuccess(msg) {
  var el = document.getElementById("sa-success");
  if (el) { el.textContent = msg; el.classList.add("visible"); }
}

function _validateEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}
