/**
 * SIGNAL — Firebase Authentication Module
 * Handles Google sign-in, token management, and auth state.
 */

(function () {
  "use strict";

  // ---------------------------------------------------------------------------
  // Firebase Config
  // ---------------------------------------------------------------------------

  const FIREBASE_CONFIG = {
    apiKey: "AIzaSyBJO7auN184dTKUf_1_hiSPMAJm3uYvTvI",
    authDomain: "instantnews-d0a72.firebaseapp.com",
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

  // ---------------------------------------------------------------------------
  // Public API (exposed as window.SignalAuth)
  // ---------------------------------------------------------------------------

  window.SignalAuth = {
    /** Initialize Firebase and set up auth state listener. */
    init: function () {
      // firebase/app and firebase/auth are loaded via CDN (compat mode)
      if (typeof firebase === "undefined") {
        console.warn("Firebase SDK not loaded");
        return;
      }

      firebase.initializeApp(FIREBASE_CONFIG);
      _auth = firebase.auth();

      // Listen for auth state changes (login, logout, token refresh)
      _auth.onAuthStateChanged(async function (user) {
        if (user) {
          _currentUser = user;
          _idToken = await user.getIdToken();
          // Refresh token automatically before expiry
          _startTokenRefresh(user);
        } else {
          _currentUser = null;
          _idToken = null;
        }
        _notifyAuthChange();
      });
    },

    /** Sign in with Google popup. */
    signIn: function () {
      if (!_auth) return;
      var provider = new firebase.auth.GoogleAuthProvider();
      return _auth.signInWithPopup(provider);
    },

    /** Sign out. */
    signOut: function () {
      if (!_auth) return;
      return _auth.signOut();
    },

    /** Get the current Firebase ID token (or null if not signed in). */
    getToken: function () {
      return _idToken;
    },

    /** Get current user info (or null). */
    getUser: function () {
      if (!_currentUser) return null;
      return {
        uid: _currentUser.uid,
        email: _currentUser.email,
        displayName: _currentUser.displayName,
        photoURL: _currentUser.photoURL,
      };
    },

    /** Whether a user is currently signed in. */
    isSignedIn: function () {
      return _currentUser !== null;
    },

    /** Register a callback for auth state changes. */
    onAuthChange: function (callback) {
      _onAuthChangeCallbacks.push(callback);
    },

    /**
     * Make an authenticated fetch request.
     * Automatically attaches Authorization header if signed in.
     */
    fetch: function (url, options) {
      options = options || {};
      options.headers = options.headers || {};
      if (_idToken) {
        options.headers["Authorization"] = "Bearer " + _idToken;
      }
      return fetch(url, options);
    },
  };

  // ---------------------------------------------------------------------------
  // Internal
  // ---------------------------------------------------------------------------

  function _notifyAuthChange() {
    for (var i = 0; i < _onAuthChangeCallbacks.length; i++) {
      try {
        _onAuthChangeCallbacks[i](window.SignalAuth.getUser());
      } catch (e) {
        console.error("Auth change callback error:", e);
      }
    }
  }

  var _refreshTimer = null;

  function _startTokenRefresh(user) {
    // Firebase tokens expire in 1 hour; refresh every 50 minutes
    if (_refreshTimer) clearInterval(_refreshTimer);
    _refreshTimer = setInterval(async function () {
      try {
        _idToken = await user.getIdToken(true);
      } catch (e) {
        // Token refresh failed — user may have been deleted
        console.warn("Token refresh failed:", e);
      }
    }, 50 * 60 * 1000);
  }
})();
