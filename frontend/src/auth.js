/**
 * SIGNAL — Firebase Authentication Module
 * Handles Google sign-in, token management, and auth state.
 *
 * Uses signInWithRedirect (not popup) for production reliability.
 * Popups fail silently when COOP headers, third-party cookie
 * restrictions, or unauthorized domains block them.
 *
 * Firebase SDK is loaded via CDN <script> tags in each HTML page
 * (compat mode). This module expects the global `firebase` object.
 */

// ---------------------------------------------------------------------------
// Firebase Config
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
let _idToken = null;
let _auth = null;
let _onAuthChangeCallbacks = [];
let _redirectResultHandled = false;

// ---------------------------------------------------------------------------
// Public API (exposed as window.SignalAuth)
// ---------------------------------------------------------------------------

const SignalAuth = {
  /** Initialize Firebase and set up auth state listener. */
  init: function () {
    // firebase/app and firebase/auth are loaded via CDN (compat mode)
    if (typeof firebase === "undefined") {
      console.warn("Firebase SDK not loaded");
      return;
    }

    if (!firebase.apps.length) {
      firebase.initializeApp(FIREBASE_CONFIG);
    }
    _auth = firebase.auth();

    // Inject auth modal into the page
    _injectAuthModal();

    // Handle redirect result (fires after user returns from Google sign-in)
    _auth
      .getRedirectResult()
      .then(function (result) {
        _redirectResultHandled = true;
        if (result && result.user) {
          // User just signed in via redirect — run any pending action
          _runPendingAction();
        }
      })
      .catch(function (err) {
        _redirectResultHandled = true;
        console.warn("Redirect sign-in error:", err);
        sessionStorage.removeItem("signalauth_pending");
      });

    // Listen for auth state changes (login, logout, token refresh)
    _auth.onAuthStateChanged(async function (user) {
      if (user) {
        _currentUser = user;
        _idToken = await user.getIdToken();
        // Refresh token automatically before expiry
        _startTokenRefresh(user);
        // Close auth modal if open (user just signed in)
        _hideModal();
      } else {
        _currentUser = null;
        _idToken = null;
      }
      _notifyAuthChange();
    });
  },

  signInWithGoogle: function () {
    if (!_auth) return Promise.reject(new Error("Auth not initialized"));
    var provider = new firebase.auth.GoogleAuthProvider();
    // Use popup everywhere — redirect fails due to third-party cookie blocking
    // in modern browsers (Chrome, Firefox, Safari)
    return _auth.signInWithPopup(provider).then(async function (result) {
      if (result && result.user) {
        _currentUser = result.user;
        _idToken = await result.user.getIdToken();
        _notifyAuthChange();
        _runPendingAction();
      }
    });
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

  signUp: function (email, password) {
    if (!_auth) return Promise.reject(new Error("Auth not initialized"));
    return _auth.createUserWithEmailAndPassword(email, password);
  },

  signInWithEmail: function (email, password) {
    if (!_auth) return Promise.reject(new Error("Auth not initialized"));
    return _auth.signInWithEmailAndPassword(email, password);
  },

  resetPassword: function (email) {
    if (!_auth) return Promise.reject(new Error("Auth not initialized"));
    return _auth.sendPasswordResetEmail(email);
  },

  signOut: function () {
    if (!_auth) return;
    sessionStorage.removeItem("signalauth_pending");
    return _auth.signOut();
  },

  getToken: function () {
    return _idToken;
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
    } catch (e) {
      // sessionStorage may be unavailable in some contexts
    }
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
    if (_idToken) {
      options.headers["Authorization"] = "Bearer " + _idToken;
    }
    return fetch(url, options);
  },
};

// Expose globally for cross-module access and inline scripts
window.SignalAuth = SignalAuth;

export default SignalAuth;

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
// Auth Modal — HTML/CSS injection and UI logic
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
      '<div class="sa-panel active" id="sa-panel-signin">' +
        '<form id="sa-form-signin" autocomplete="on">' +
          '<div class="sa-field"><label for="sa-signin-email">Email</label><input id="sa-signin-email" type="email" placeholder="you@example.com" autocomplete="email" required></div>' +
          '<div class="sa-field"><label for="sa-signin-password">Password</label><input id="sa-signin-password" type="password" placeholder="Enter password" autocomplete="current-password" required></div>' +
          '<button type="submit" class="sa-btn sa-btn-primary" id="sa-btn-signin">Sign In</button>' +
          '<div style="text-align:right"><button type="button" class="sa-forgot" id="sa-show-forgot">Forgot password?</button></div>' +
        '</form>' +
        '<div class="sa-divider">or</div>' +
        '<button class="sa-btn sa-btn-google" id="sa-google-signin"><svg width="18" height="18" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59A14.5 14.5 0 019.5 24c0-1.59.28-3.14.76-4.59l-7.98-6.19A23.9 23.9 0 000 24c0 3.77.9 7.34 2.44 10.51l8.09-5.92z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg> Sign in with Google</button>' +
      '</div>' +
      '<div class="sa-panel" id="sa-panel-signup">' +
        '<form id="sa-form-signup" autocomplete="on">' +
          '<div class="sa-field"><label for="sa-signup-email">Email</label><input id="sa-signup-email" type="email" placeholder="you@example.com" autocomplete="email" required></div>' +
          '<div class="sa-field"><label for="sa-signup-password">Password</label><input id="sa-signup-password" type="password" placeholder="Min 8 characters" autocomplete="new-password" required minlength="8"></div>' +
          '<div class="sa-field"><label for="sa-signup-confirm">Confirm Password</label><input id="sa-signup-confirm" type="password" placeholder="Confirm password" autocomplete="new-password" required minlength="8"></div>' +
          '<button type="submit" class="sa-btn sa-btn-primary" id="sa-btn-signup">Create Account</button>' +
        '</form>' +
        '<div class="sa-divider">or</div>' +
        '<button class="sa-btn sa-btn-google" id="sa-google-signup"><svg width="18" height="18" viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59A14.5 14.5 0 019.5 24c0-1.59.28-3.14.76-4.59l-7.98-6.19A23.9 23.9 0 000 24c0 3.77.9 7.34 2.44 10.51l8.09-5.92z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg> Sign up with Google</button>' +
      '</div>' +
      '<div class="sa-panel" id="sa-panel-forgot">' +
        '<button class="sa-back" id="sa-back-forgot">&larr; Back to Sign In</button>' +
        '<p style="color:#8b949e;font-size:14px;margin:0 0 16px">Enter your email and we\'ll send you a link to reset your password.</p>' +
        '<form id="sa-form-forgot">' +
          '<div class="sa-field"><label for="sa-forgot-email">Email</label><input id="sa-forgot-email" type="email" placeholder="you@example.com" autocomplete="email" required></div>' +
          '<button type="submit" class="sa-btn sa-btn-primary" id="sa-btn-forgot">Send Reset Email</button>' +
        '</form>' +
      '</div>' +
      '<div class="sa-footer" id="sa-footer-signin">Don\'t have an account? <button id="sa-switch-to-signup">Sign up</button></div>' +
      '<div class="sa-footer" id="sa-footer-signup" style="display:none">Already have an account? <button id="sa-switch-to-signin">Sign in</button></div>' +
    '</div>';

  document.body.appendChild(overlay);
  _modalEl = overlay;
  _bindModalEvents();
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
    tab.addEventListener("click", function () {
      _switchTab(tab.dataset.tab);
    });
  });

  document.getElementById("sa-switch-to-signup").addEventListener("click", function () { _switchTab("signup"); });
  document.getElementById("sa-switch-to-signin").addEventListener("click", function () { _switchTab("signin"); });
  document.getElementById("sa-show-forgot").addEventListener("click", function () { _switchTab("forgot"); });
  document.getElementById("sa-back-forgot").addEventListener("click", function () { _switchTab("signin"); });

  // Sign In form
  document.getElementById("sa-form-signin").addEventListener("submit", function (e) {
    e.preventDefault();
    _clearMessages();
    var email = document.getElementById("sa-signin-email").value.trim();
    var password = document.getElementById("sa-signin-password").value;

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
        _showError(_friendlyError(err));
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
      .then(function (userCredential) {
        // Send verification email
        if (userCredential && userCredential.user && !userCredential.user.emailVerified) {
          userCredential.user.sendEmailVerification({
            url: window.location.origin + "/terminal",
          });
        }
        _hideModal();
        _runPendingAction();
      })
      .catch(function (err) {
        _showError(_friendlyError(err));
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
      .then(function () {
        _showSuccess("Password reset email sent! Check your inbox.");
        document.getElementById("sa-form-forgot").reset();
      })
      .catch(function (err) {
        _showError(_friendlyError(err));
      })
      .finally(function () {
        btn.disabled = false;
        btn.textContent = "Send Reset Email";
      });
  });

  // Google sign-in buttons
  document.getElementById("sa-google-signin").addEventListener("click", function () {
    SignalAuth.signInWithGoogle();
  });
  document.getElementById("sa-google-signup").addEventListener("click", function () {
    SignalAuth.signInWithGoogle();
  });

  // Real-time password match validation
  var confirmInput = document.getElementById("sa-signup-confirm");
  var passwordInput = document.getElementById("sa-signup-password");
  function _checkPasswordMatch() {
    var pw = passwordInput.value;
    var cf = confirmInput.value;
    if (!cf) {
      confirmInput.style.borderColor = "";
      return;
    }
    if (pw !== cf) {
      confirmInput.style.borderColor = "#f85149";
    } else {
      confirmInput.style.borderColor = "#3fb950";
    }
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
    if (panel) {
      var input = panel.querySelector("input");
      if (input) input.focus();
    }
  }, 50);
}

function _hideModal() {
  var overlay = document.getElementById("signal-auth-overlay");
  if (overlay) overlay.classList.remove("open");
  _clearMessages();
}

function _switchTab(tab) {
  var tabs = document.querySelectorAll("#sa-tabs .sa-tab");
  tabs.forEach(function (t) {
    t.classList.toggle("active", t.dataset.tab === tab);
  });

  var tabsBar = document.getElementById("sa-tabs");
  var panels = document.querySelectorAll(".sa-panel");
  panels.forEach(function (p) { p.classList.remove("active"); });

  if (tab === "forgot") {
    tabsBar.style.display = "none";
    document.getElementById("sa-panel-forgot").classList.add("active");
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

function _friendlyError(err) {
  var code = err && err.code ? err.code : "";
  var map = {
    "auth/invalid-email": "Invalid email address.",
    "auth/user-disabled": "This account has been disabled.",
    "auth/user-not-found": "No account found with this email.",
    "auth/wrong-password": "Incorrect password.",
    "auth/invalid-credential": "Invalid email or password.",
    "auth/email-already-in-use": "An account with this email already exists.",
    "auth/weak-password": "Password is too weak. Use at least 8 characters.",
    "auth/too-many-requests": "Too many attempts. Please try again later.",
    "auth/network-request-failed": "Network error. Check your connection and try again.",
    "auth/popup-closed-by-user": "Sign-in was cancelled.",
    "auth/operation-not-allowed": "This sign-in method is not enabled.",
  };
  return map[code] || (err && err.message ? err.message : "An unexpected error occurred. Please try again.");
}
