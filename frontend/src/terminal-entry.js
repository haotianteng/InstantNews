/**
 * Terminal page entry point
 * Imports styles and initializes the terminal app
 */
import './styles/base.css';
import './styles/terminal.css';
import './auth.js';
import './terminal-app.js';

// Auth gate logic (extracted from index.html inline script)
document.addEventListener('DOMContentLoaded', function() {
  var gate = document.getElementById('auth-gate');
  var btn = document.getElementById('auth-gate-signin');

  function checkAuth() {
    if (typeof SignalAuth !== 'undefined' && SignalAuth.isSignedIn()) {
      gate.classList.add('hidden');
    } else {
      gate.classList.remove('hidden');
    }
  }

  if (btn) {
    btn.addEventListener('click', function() {
      if (typeof SignalAuth !== 'undefined') {
        SignalAuth.showAuthModal('signin');
      }
    });
  }

  if (typeof SignalAuth !== 'undefined') {
    SignalAuth.onAuthChange(checkAuth);
  }

  setTimeout(function() {
    if (typeof SignalAuth !== 'undefined') {
      SignalAuth.onAuthChange(checkAuth);
      checkAuth();
    }
  }, 500);
});
