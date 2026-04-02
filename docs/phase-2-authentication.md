# Phase 2: Authentication (Firebase Auth + Google OAuth)

**Status:** Complete
**Goal:** Add user registration/login via Google OAuth using Firebase Auth. Anonymous users default to Free tier.

## What Was Built

### Backend
- **`app/auth/firebase.py`** — Firebase Admin SDK initialization + `verify_id_token()`. Supports credentials via file path (`FIREBASE_CREDENTIALS`) or JSON string (`FIREBASE_CREDENTIALS_JSON`).
- **`app/auth/middleware.py`** — `before_request` hook that:
  1. Extracts Bearer token from `Authorization` header
  2. Verifies token with Firebase Admin SDK
  3. Creates user record on first login (auto-registration)
  4. Updates display_name/photo_url if changed
  5. Sets `g.current_user` as a detached `CurrentUser` object (avoids SQLAlchemy `DetachedInstanceError`)
- **`app/auth/routes.py`** — Auth endpoints:
  - `GET /api/auth/me` — requires auth, returns user profile
  - `GET /api/auth/tier` — returns tier + feature flags (works for anon too)
  - `GET /api/pricing` — returns all tier definitions for pricing page

### Frontend
- **`static/auth.js`** — `SignalAuth` module exposing:
  - `init()` — initializes Firebase, sets up `onAuthStateChanged` listener
  - `signIn()` — triggers Google popup sign-in
  - `signOut()` — signs out
  - `fetch(url, options)` — wrapper that auto-attaches `Authorization: Bearer <token>`
  - `onAuthChange(callback)` — register auth state change listeners
  - Auto-refreshes tokens every 50 minutes (Firebase tokens expire in 1 hour)
- **`static/index.html`** — Added:
  - Firebase SDK via CDN (`firebase-app-compat.js`, `firebase-auth-compat.js`)
  - Sign In button (shown when logged out)
  - User menu with avatar, name, tier badge, dropdown (shown when logged in)
  - Dropdown contains: email, tier label, Upgrade Plan link, Sign Out button
- **`static/app.js`** — All `fetch()` calls replaced with `SignalAuth.fetch()` to attach auth tokens

### Database
- **`User` model** added to `app/models.py`: firebase_uid, email, display_name, photo_url, tier, created_at, updated_at
- **Migration `002_add_users_table.py`**

### Firebase Config
```
Project ID: instantnews-d0a72
Auth Domain: instantnews-d0a72.firebaseapp.com
```

## Setup Required for Production

1. **Download service account key:** Firebase Console → Project Settings → Service Accounts → Generate new private key
2. **Set environment variable:**
   - `FIREBASE_CREDENTIALS=/path/to/serviceAccountKey.json` or
   - `FIREBASE_CREDENTIALS_JSON='{"type":"service_account",...}'`
3. **Add authorized domains:** Firebase Console → Authentication → Settings → Authorized domains:
   - `instnews.net`
   - `www.instnews.net`
   - `localhost` (for dev)

## Auth Flow
```
User clicks "Sign In"
  → Firebase JS SDK opens Google popup
  → User authenticates with Google
  → Firebase returns ID token to frontend
  → Frontend stores token, attaches to all API requests via Authorization header
  → Backend middleware verifies token with Firebase Admin SDK
  → Creates/updates user record in database
  → Sets g.current_user for the request
  → Route handlers can check user/tier
```

## Test Coverage
9 auth tests covering: anonymous access, user creation, profile updates, invalid tokens, tier endpoint.
