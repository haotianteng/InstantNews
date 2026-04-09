# Multi-Provider Authentication Setup Guide

This document describes how to set up a multi-provider authentication system supporting email/password (own bcrypt), Google OAuth (Firebase), and WeChat QR login (China). The architecture is designed for a SaaS application deployed on AWS ECS with a Flask backend and Vite-built frontend.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Prerequisites](#2-prerequisites)
3. [Google Cloud / Firebase Setup](#3-google-cloud--firebase-setup)
4. [Gmail API Setup for Transactional Emails](#4-gmail-api-setup-for-transactional-emails)
5. [Database Schema](#5-database-schema)
6. [Environment Variables](#6-environment-variables)
7. [Backend Auth Flow](#7-backend-auth-flow)
8. [Frontend Auth Flow](#8-frontend-auth-flow)
9. [WeChat Open Platform Setup](#9-wechat-open-platform-setup)
10. [Production Deployment](#10-production-deployment)
11. [Local Development](#11-local-development)
12. [Security Considerations](#12-security-considerations)

---

## 1. Architecture Overview

The system supports three authentication methods:

| Method | Provider | Scope | Token Type | Works in China |
|---|---|---|---|---|
| Email/Password | Own backend (bcrypt) | Global | App JWT (HS256) | Yes |
| Google OAuth | Firebase Auth (popup) | Global (except China) | Firebase ID token | No |
| WeChat QR | WeChat Open Platform | China only | App JWT (HS256) | Yes |

### Design Principles

- **Backend-first for email/password**: Signup, signin, verification, and password reset all go through our API (`/api/auth/*`). No client-side auth SDK is involved. This ensures the flow works in regions where third-party SDKs are blocked.
- **Firebase only for Google OAuth**: The Firebase JS SDK is loaded on the frontend solely for `signInWithPopup`. The backend verifies Firebase ID tokens using the Firebase Admin SDK.
- **Region detection determines UI**: The frontend detects whether the user is in China (by testing Google reachability + a backend geo endpoint). In China, the WeChat button is shown. Elsewhere, the Google button is shown. Email/password is always available.
- **Unified user table**: All auth methods write to a single `users` table. The `auth_method` column (`email`, `google`, `wechat`) tracks how the user registered. One email can only be associated with one auth method.
- **Two token types**: Google OAuth users authenticate with Firebase ID tokens (verified by Firebase Admin SDK). Email/password and WeChat users authenticate with app-issued JWTs (signed with `APP_JWT_SECRET`, HS256). The middleware tries both.

### Auth Middleware Dispatch Order

When a request arrives with credentials, the middleware (`app/auth/middleware.py`) checks in this order:

1. `X-API-Key` header -- look up hashed key in `api_keys` table
2. `Authorization: Bearer <token>` -- try decoding as app JWT (HS256)
3. If app JWT fails, try verifying as Firebase ID token
4. If all fail, request is anonymous (`g.current_user = None`)

---

## 2. Prerequisites

Before starting, you need:

- **AWS account** with ECS, RDS PostgreSQL, Route 53, and Secrets Manager access
- **Google Cloud project** (Firebase is part of Google Cloud)
- **Google Workspace** (formerly G Suite) -- required for Gmail API domain-wide delegation to send transactional emails from a custom domain
- **Domain name** with DNS control (e.g., via Route 53 or Cloudflare)
- **WeChat Open Platform account** (optional, only for China social login) -- requires a Chinese business entity

### Software Requirements

```
Python 3.11+
Node.js 18+ (for Vite frontend build)
PostgreSQL 14+ (production) or SQLite (development)
```

### Python Dependencies

```
# Auth-related packages in requirements.txt
bcrypt>=4.0.0
PyJWT>=2.8.0
firebase-admin>=6.0.0
google-api-python-client>=2.0.0
google-auth>=2.0.0
```

---

## 3. Google Cloud / Firebase Setup

### Step 1: Create a Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Click **Add project**
3. Enter a project name (e.g., `myapp-prod`)
4. Optionally enable Google Analytics
5. Click **Create project**

### Step 2: Enable Google Sign-In Provider

1. In Firebase Console, go to **Authentication > Sign-in method**
2. Click **Google** under "Additional providers"
3. Toggle **Enable**
4. Set a public-facing name (shown on the consent screen)
5. Enter a support email
6. Click **Save**

### Step 3: Register a Web App

1. In Firebase Console, go to **Project settings > General**
2. Under "Your apps", click the web icon (`</>`)
3. Register the app with a nickname (e.g., `web`)
4. Copy the Firebase config object:

```javascript
const FIREBASE_CONFIG = {
  apiKey: "AIzaSy...",
  authDomain: "your-project.firebaseapp.com",
  projectId: "your-project-id",
  storageBucket: "your-project.firebasestorage.app",
  messagingSenderId: "1234567890",
  appId: "1:1234567890:web:abcdef",
};
```

Save this -- it goes into your frontend code (`frontend/src/auth.js`).

### Step 4: Download Service Account JSON

1. In Firebase Console, go to **Project settings > Service accounts**
2. Click **Generate new private key**
3. Save the JSON file securely (e.g., `firebase-service-account.json`)
4. This file is used by:
   - Firebase Admin SDK (backend token verification)
   - Gmail API (transactional email sending via domain-wide delegation)

> **Security**: Never commit this file to git. Store it in AWS Secrets Manager for production.

### Step 5: Add Authorized Domains

1. In Firebase Console, go to **Authentication > Settings > Authorized domains**
2. Add your production domain (e.g., `www.yourdomain.com`)
3. Add `localhost` for development

### Step 6 (Optional): Configure Custom authDomain

By default, Firebase shows `your-project.firebaseapp.com` in the Google consent screen URL. To use your own domain:

1. In Firebase Console, go to **Authentication > Settings**
2. Under "Custom domain", follow the steps to verify your domain
3. Add a CNAME record: `auth.yourdomain.com` -> `your-project.firebaseapp.com`
4. Update the frontend config:

```javascript
authDomain: "www.yourdomain.com",  // or auth.yourdomain.com
```

> This makes the Google OAuth consent screen show your domain instead of firebaseapp.com. Users see `www.yourdomain.com` in the browser bar during the popup flow.

---

## 4. Gmail API Setup for Transactional Emails

The email service (`app/services/email.py`) sends verification emails, password reset links, and provider conflict notifications using the Gmail API. It reuses the Firebase service account with domain-wide delegation -- no additional credentials needed.

### Why Gmail API Instead of SES/SendGrid

- Reuses the Firebase service account (no extra secrets)
- High deliverability for transactional emails from a Google Workspace domain
- Free for low-volume transactional email (< 2,000/day)

### Step 1: Enable Gmail API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select the same project as your Firebase project
3. Navigate to **APIs & Services > Library**
4. Search for **Gmail API**
5. Click **Enable**

### Step 2: Enable Domain-Wide Delegation on the Service Account

1. Go to **IAM & Admin > Service Accounts**
2. Find the Firebase service account (usually named `firebase-adminsdk-xxxxx@your-project.iam.gserviceaccount.com`)
3. Click on the service account, then **Details**
4. Check **Enable Google Workspace Domain-Wide Delegation** (under "Show Domain-Wide Delegation")
5. Click **Save**
6. Note the **Client ID** (a numeric value like `117...`) -- you need this for the next step

### Step 3: Authorize the Scope in Google Workspace Admin

1. Sign in to [Google Workspace Admin Console](https://admin.google.com/) as a super admin
2. Go to **Security > Access and data control > API controls**
3. Click **Manage Domain Wide Delegation**
4. Click **Add new**
5. Enter:
   - **Client ID**: the numeric ID from Step 2
   - **OAuth scopes**: `https://www.googleapis.com/auth/gmail.send`
6. Click **Authorize**

### Step 4: Set Up "Send As" Alias for noreply@ Address

The Gmail API sends email as the delegated user. To send from `noreply@yourdomain.com` instead of the admin's personal address:

1. Sign in to Gmail as the workspace admin account
2. Go to **Settings** (gear icon) > **See all settings**
3. Go to the **Accounts** tab
4. Under "Send mail as", click **Add another email address**
5. Enter:
   - **Name**: Your App Name (e.g., "InstNews")
   - **Email**: `noreply@yourdomain.com`
6. Uncheck "Treat as an alias" if you want strict separation, or leave it checked
7. If your domain has email routing configured (Google Workspace), the verification email will arrive. Click the link to verify.
8. Set `noreply@yourdomain.com` as the default "Send mail as" address

> **Alternative**: If you use Google Workspace with a catch-all or routing rule, you can create `noreply@yourdomain.com` as a group address that receives no mail. The "Send As" alias allows sending from it without a full mailbox.

### Step 5: Configure the Environment Variable

```bash
# The email address the Gmail API sends from
GMAIL_SENDER=noreply@yourdomain.com
```

The code in `app/services/email.py` delegates to this address:

```python
delegated = credentials.with_subject(SENDER_EMAIL)
service = build("gmail", "v1", credentials=delegated, cache_discovery=False)
```

### How It Works in Code

The email service (`app/services/email.py`):

1. Loads the same service account credentials used by Firebase (`FIREBASE_CREDENTIALS` or `FIREBASE_CREDENTIALS_JSON`)
2. Creates delegated credentials with `gmail.send` scope, impersonating the `GMAIL_SENDER` address
3. Builds a Gmail API client and sends HTML emails via `users().messages().send()`
4. Falls back to logging emails to stdout if credentials are not available (local dev)

Three email types are supported:

| Email | Trigger | Expiry |
|---|---|---|
| Verification | Signup | 24 hours |
| Password Reset | Forgot password | 1 hour |
| Provider Conflict | Signup with email already used by Google/WeChat | N/A |

---

## 5. Database Schema

### User Model

All auth methods share a single `users` table. Key fields:

```
Column              Type        Nullable  Purpose
─────────────────── ─────────── ───────── ────────────────────────────────────
id                  Integer     No        Primary key (auto-increment)
firebase_uid        String      Yes       Firebase UID (Google OAuth users only)
email               String      Yes       Unique; NULL for WeChat-only users
display_name        String      Yes       User's display name
photo_url           String      Yes       Profile photo URL
tier                String      No        Subscription tier (free/pro/max)
role                String      No        user, admin, superadmin
auth_method         String      No        "email", "google", or "wechat"
password_hash       String      Yes       bcrypt hash (email auth only)
email_verified      Boolean     No        Must be true before email signin
wechat_openid       String      Yes       Unique; WeChat Open ID
wechat_unionid      String      Yes       WeChat Union ID (cross-app)
is_test_account     Boolean     No        Flag for QA test accounts
test_tier_override  String      Yes       Override tier for test accounts
disabled            Boolean     No        Account disabled flag
last_login_at       String      Yes       ISO 8601 timestamp
created_at          String      No        ISO 8601 timestamp
updated_at          String      No        ISO 8601 timestamp
```

Key constraints:
- `email` has a unique index (but is nullable for WeChat users)
- `firebase_uid` has a unique index
- `wechat_openid` has a unique index

### Migration Files

Two Alembic migrations add the multi-auth fields:

**Migration 010** (`migrations/versions/010_add_multi_auth_fields.py`):
- Adds `wechat_openid`, `wechat_unionid` columns
- Makes `firebase_uid` and `email` nullable (for WeChat users who may not have email)
- Creates unique indexes on `wechat_openid`

**Migration 011** (`migrations/versions/011_own_auth_fields.py`):
- Adds `password_hash`, `email_verified` columns
- Renames `auth_provider` to `auth_method`
- Sets `auth_method='google'` for existing Firebase users
- Marks existing Google users as `email_verified=true`

Run migrations:

```bash
alembic upgrade head
```

---

## 6. Environment Variables

### Auth-Related Variables

| Variable | Secret? | Required | Default | Description |
|---|---|---|---|---|
| `APP_JWT_SECRET` | Yes | Yes | `""` | HMAC key for signing app JWTs and verification/reset tokens. Generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `APP_JWT_EXPIRY_DAYS` | No | No | `7` | How many days app JWTs are valid |
| `FIREBASE_CREDENTIALS` | Yes | Dev only | `""` | File path to Firebase service account JSON (local dev) |
| `FIREBASE_CREDENTIALS_JSON` | Yes | Prod only | `""` | Inline JSON string of Firebase service account (containers/CI) |
| `GMAIL_SENDER` | No | No | `noreply@instnews.net` | Email address for transactional emails |
| `BASE_URL` | No | No | `https://www.instnews.net` | Base URL for email links (verification, reset) |
| `WECHAT_APP_ID` | No | No | `""` | WeChat Open Platform App ID (empty disables WeChat) |
| `WECHAT_APP_SECRET` | Yes | No | `""` | WeChat Open Platform App Secret |
| `WECHAT_REDIRECT_URI` | No | No | `https://www.instnews.net/api/auth/wechat/callback` | WeChat OAuth callback URL |

### Example `.env` File (Local Development)

```bash
# App JWT
APP_JWT_SECRET=your-random-64-char-hex-string-here
APP_JWT_EXPIRY_DAYS=7

# Firebase (local dev uses file path)
FIREBASE_CREDENTIALS=./firebase-service-account.json

# Email (leave unset to log emails to console)
GMAIL_SENDER=noreply@yourdomain.com
BASE_URL=http://localhost:8000

# WeChat (optional, leave empty to disable)
WECHAT_APP_ID=
WECHAT_APP_SECRET=
WECHAT_REDIRECT_URI=http://localhost:8000/api/auth/wechat/callback
```

### Production Secrets (AWS Secrets Manager)

Store all secrets under a single Secrets Manager entry (e.g., `myapp/app`):

```json
{
  "APP_JWT_SECRET": "a]f9...(64 hex chars)",
  "FIREBASE_CREDENTIALS_JSON": "{\"type\":\"service_account\",...}",
  "WECHAT_APP_SECRET": "wx...",
  "STRIPE_SECRET_KEY": "sk_live_...",
  "STRIPE_WEBHOOK_SECRET": "whsec_..."
}
```

Non-secret config is set as plain environment variables in the ECS task definition.

---

## 7. Backend Auth Flow

### Email/Password Signup

```
POST /api/auth/signup { email, password }
```

1. Validate email format (regex) and password strength (>= 8 chars)
2. Check for existing user with same email:
   - If exists with `auth_method="email"` -- return 409 "already exists"
   - If exists with different method (e.g., `google`) -- send a "provider conflict" email explaining which method they used, return 409
3. Hash password with `bcrypt.hashpw()` (auto-generates salt)
4. Create user row: `auth_method="email"`, `email_verified=False`
5. Generate HMAC-signed verification token: `{user_id}:{timestamp}:{signature}`
6. Send verification email with link to `/api/auth/verify-email?token=...`
7. Return 201 with message to check email

### Email Verification

```
GET /api/auth/verify-email?token=...
```

1. Parse token into `user_id`, `timestamp`, `signature`
2. Check token is not expired (24-hour window)
3. Verify HMAC signature using `APP_JWT_SECRET`
4. Set `email_verified=True` on the user
5. Redirect to `/?verified=true`

### Email/Password Signin

```
POST /api/auth/signin { email, password }
```

1. Look up user by email
2. If not found -- return 401 "Invalid email or password"
3. If `auth_method != "email"` -- return 401 with message to use the correct method
4. If `email_verified == False` -- return 403 with code `email_not_verified`
5. If `disabled == True` -- return 403
6. Verify password with `bcrypt.checkpw()`
7. If wrong -- return 401 "Invalid email or password"
8. Issue app JWT (`HS256`, signed with `APP_JWT_SECRET`):
   ```json
   {
     "sub": "123",
     "provider": "email",
     "display_name": "user",
     "iat": 1712345678,
     "exp": 1712950478
   }
   ```
9. Return token + user profile

### Password Reset

```
POST /api/auth/forgot-password { email }
```

1. Always returns 200 with generic message (prevents email enumeration)
2. If user exists with `auth_method="email"` -- generate 1-hour HMAC reset token, send reset email
3. If user exists with different auth method -- send provider conflict email instead
4. If user does not exist -- do nothing (same response)

```
POST /api/auth/reset-password { token, password }
```

1. Verify HMAC token (1-hour expiry)
2. Validate new password strength
3. Update `password_hash` with new bcrypt hash

### Google OAuth (Firebase)

The Google OAuth flow is handled entirely on the frontend via Firebase:

1. Frontend calls `firebase.auth().signInWithPopup(googleProvider)`
2. Google consent screen opens in a popup
3. User authorizes; popup closes
4. Firebase JS SDK returns a `user` object with `.getIdToken()`
5. Frontend sends the Firebase ID token in `Authorization: Bearer <token>` on API calls
6. Backend middleware (`_try_firebase_token`) verifies via `firebase_admin.auth.verify_id_token()`
7. If no user row exists, auto-create one with `auth_method="google"`, `email_verified=True`
8. If user exists, update `display_name`, `photo_url`, `last_login_at`

### WeChat QR Login

```
GET /api/auth/wechat/login
```

1. Generate HMAC-signed CSRF state: `{timestamp}:{nonce}:{signature}` (5-minute expiry)
2. Redirect to WeChat authorization URL:
   ```
   https://open.weixin.qq.com/connect/qrconnect
     ?appid=WECHAT_APP_ID
     &redirect_uri=WECHAT_REDIRECT_URI
     &response_type=code
     &scope=snsapi_login
     &state={state}
     #wechat_redirect
   ```
3. User scans QR code with WeChat phone app

```
GET /api/auth/wechat/callback?code=...&state=...
```

4. Verify CSRF state (HMAC + expiry check)
5. Exchange code for access token: `POST https://api.weixin.qq.com/sns/oauth2/access_token`
6. Fetch user profile: `GET https://api.weixin.qq.com/sns/userinfo`
7. Look up user by `wechat_openid`:
   - If exists -- update profile, set `last_login_at`
   - If new -- create user with `auth_method="wechat"`, `email_verified=True` (WeChat verifies via phone)
8. Issue app JWT
9. Redirect to `/terminal?wechat_token={jwt}` (frontend picks up the token from URL)

### Token Refresh

```
POST /api/auth/refresh  (requires auth)
```

Available for `email` and `wechat` users only (Google OAuth users refresh via Firebase SDK). Issues a fresh app JWT with the same claims.

---

## 8. Frontend Auth Flow

The frontend auth module (`frontend/src/auth.js`) is exposed as `window.SignalAuth`.

### Initialization Sequence

```javascript
SignalAuth.init()
```

1. Check URL for `?wechat_token=...` (WeChat callback token) or localStorage for existing app token
2. If token found, call `/api/auth/me` to validate and load user profile
3. Detect region (see below)
4. If region is `global`, load Firebase JS SDK and initialize
5. Inject the auth modal (sign in / sign up UI)

### Region Detection

The frontend determines the user's region to decide which social login button to show:

```
1. URL override: ?region=cn or ?region=global (for testing)
2. Cached result in localStorage (24-hour TTL)
3. Google reachability test: fetch googleapis.com with 3-second timeout
   - If reachable -> "global"
   - If blocked/timeout -> continue
4. Backend endpoint: GET /api/auth/region
   - Uses CloudFront-Viewer-Country or X-Country-Code header
5. Default: "cn" (if all detection fails, assume restricted network)
```

The backend `/api/auth/region` endpoint checks:
- `CloudFront-Viewer-Country` header (set by AWS CloudFront)
- `X-Country-Code` header (set by custom proxy/CDN)
- URL query parameter override (`?region=cn`)

### Token Storage and Management

| Auth Method | Token Type | Storage | Refresh |
|---|---|---|---|
| Email/Password | App JWT | `localStorage` (`signal_app_token`) | `POST /api/auth/refresh` |
| WeChat | App JWT | `localStorage` (`signal_app_token`) | `POST /api/auth/refresh` |
| Google OAuth | Firebase ID token | In-memory only | `user.getIdToken()` (Firebase SDK auto-refreshes) |

### API Calls with Auth

The frontend's `getToken()` function returns whichever token is active:

```javascript
SignalAuth.getToken()
// Returns: Firebase ID token (if Google) OR app JWT (if email/WeChat) OR null
```

Used in fetch calls:

```javascript
fetch("/api/news", {
  headers: { "Authorization": "Bearer " + SignalAuth.getToken() }
})
```

### Email/Password Flow (Frontend)

**Signup:**
```javascript
SignalAuth.signUp(email, password)
// -> POST /api/auth/signup
// -> Returns message to check email
```

**Signin:**
```javascript
SignalAuth.signInWithEmail(email, password)
// -> POST /api/auth/signin
// -> Returns { token, user }
// -> Stores token in localStorage
// -> Triggers auth state change callbacks
```

**Forgot password:**
```javascript
SignalAuth.forgotPassword(email)
// -> POST /api/auth/forgot-password
// -> Returns generic success message
```

### Google OAuth Flow (Frontend)

```javascript
SignalAuth.signInWithGoogle()
// -> firebase.auth().signInWithPopup(GoogleAuthProvider)
// -> On success: stores Firebase ID token in memory
// -> Triggers auth state change callbacks
```

### WeChat Flow (Frontend)

```javascript
SignalAuth.signInWithWeChat()
// -> window.location.href = "/api/auth/wechat/login"
// -> Full page redirect to WeChat QR page
// -> After QR scan: redirect back to /terminal?wechat_token=JWT
// -> SignalAuth.init() picks up token from URL, strips it, stores in localStorage
```

---

## 9. WeChat Open Platform Setup

> WeChat login requires a Chinese business entity and takes approximately 1 week for approval. This is optional and only needed if you serve users in mainland China.

### Step 1: Register on WeChat Open Platform

1. Go to [open.weixin.qq.com](https://open.weixin.qq.com/)
2. Click "Register" and create an account
3. Complete identity verification (requires Chinese business license, organization code, legal representative ID)

### Step 2: Create a Website Application

1. After login, go to **Management Center > Website Application**
2. Click **Create Website Application**
3. Fill in:
   - **Application name**: Your app name (in Chinese)
   - **Application description**: Brief description
   - **Application website**: Your production URL (e.g., `https://www.yourdomain.com`)
   - **Authorization callback domain**: `www.yourdomain.com` (no path, just domain)
4. Upload application icon (108x108 px)
5. Submit for review

### Step 3: Domain Verification

WeChat requires you to prove domain ownership:

1. Download the verification file provided by WeChat
2. Place it at the root of your website (e.g., `https://www.yourdomain.com/MP_verify_xxxx.txt`)
3. WeChat will HTTP GET this URL during review

### Step 4: Wait for Approval

- Review takes 1-7 business days
- Once approved, you get:
  - **AppID**: `wx` + 16 hex characters (e.g., `wxd930ea5d5a258f4f`)
  - **AppSecret**: 32 hex characters

### Step 5: Configure Callback URL

The callback URL is set per-application in the WeChat Open Platform console:

```
https://www.yourdomain.com/api/auth/wechat/callback
```

This must exactly match the `WECHAT_REDIRECT_URI` environment variable.

### Step 6: Set Environment Variables

```bash
WECHAT_APP_ID=wxd930ea5d5a258f4f
WECHAT_APP_SECRET=your-32-char-hex-secret
WECHAT_REDIRECT_URI=https://www.yourdomain.com/api/auth/wechat/callback
```

### How the QR Login Works

1. User clicks "Sign in with WeChat" on your site
2. Browser redirects to `https://open.weixin.qq.com/connect/qrconnect?appid=...`
3. WeChat displays a QR code
4. User opens WeChat on their phone and scans the QR code
5. User taps "Confirm" on their phone
6. WeChat redirects browser to your callback URL with `?code=XXXXX&state=XXXXX`
7. Your backend exchanges the code for an access token and fetches the user profile

---

## 10. Production Deployment

### AWS Secrets Manager

Store all auth secrets in a single Secrets Manager entry:

```bash
aws secretsmanager create-secret \
  --name myapp/app \
  --secret-string '{
    "APP_JWT_SECRET": "'"$(python -c 'import secrets; print(secrets.token_hex(32))')"'",
    "FIREBASE_CREDENTIALS_JSON": "{\"type\":\"service_account\",\"project_id\":\"...\"}",
    "WECHAT_APP_SECRET": "your-wechat-secret"
  }'
```

### ECS Task Definition Environment

Non-secret environment variables are set directly in the task definition or CDK stack:

```python
# In infra/stack.py (CDK)
container.add_environment("APP_JWT_EXPIRY_DAYS", "7")
container.add_environment("GMAIL_SENDER", "noreply@yourdomain.com")
container.add_environment("BASE_URL", "https://www.yourdomain.com")
container.add_environment("WECHAT_APP_ID", "wxd930ea5d5a258f4f")
container.add_environment("WECHAT_REDIRECT_URI", "https://www.yourdomain.com/api/auth/wechat/callback")
```

Secrets are injected from Secrets Manager:

```python
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_secretsmanager as sm

secret = sm.Secret.from_secret_name_v2(self, "AppSecret", "myapp/app")

container.add_secret("APP_JWT_SECRET", ecs.Secret.from_secrets_manager(secret, "APP_JWT_SECRET"))
container.add_secret("FIREBASE_CREDENTIALS_JSON", ecs.Secret.from_secrets_manager(secret, "FIREBASE_CREDENTIALS_JSON"))
container.add_secret("WECHAT_APP_SECRET", ecs.Secret.from_secrets_manager(secret, "WECHAT_APP_SECRET"))
```

### Database Migrations

Run Alembic migrations before the first deployment:

```bash
alembic upgrade head
```

This applies migrations 010 (multi-auth fields) and 011 (own auth fields) to add:
- `wechat_openid`, `wechat_unionid` columns
- `password_hash`, `email_verified` columns
- `auth_method` column (replacing `auth_provider`)

### Required DNS Records

| Record | Type | Value | Purpose |
|---|---|---|---|
| `www.yourdomain.com` | A/CNAME | ALB endpoint | Main application |
| `auth.yourdomain.com` | CNAME | `your-project.firebaseapp.com` | Firebase custom authDomain (optional) |

---

## 11. Local Development

### Minimal .env Setup

Create a `.env` file in the project root:

```bash
# Required for email/password auth
APP_JWT_SECRET=dev-secret-change-in-production-abc123def456

# Required for Google OAuth (download from Firebase console)
FIREBASE_CREDENTIALS=./firebase-service-account.json

# Email links point to local dev server
BASE_URL=http://localhost:8000

# Optional: database (defaults to SQLite)
# DATABASE_URL=postgresql://user:pass@localhost/myapp
```

### Running the Dev Environment

Terminal 1 -- Backend:
```bash
python server.py
# Flask runs on :8000, loads .env via python-dotenv
```

Terminal 2 -- Frontend (with HMR):
```bash
cd frontend && npx vite dev
# Vite runs on :5173, proxies /api to :8000
```

Open `http://localhost:5173` in your browser.

### Testing Email (Without Gmail API)

When `FIREBASE_CREDENTIALS` is not set or the Gmail API service fails to initialize, the email service falls back to logging. You will see emails in the backend console output:

```
INFO signal.email: Email (dev mode - Gmail API not configured) {"to": "user@example.com", "subject": "Verify your InstNews account"}
INFO signal.email:   Welcome to InstNews
INFO signal.email:   Please verify your email address to activate your account.
INFO signal.email:   http://localhost:8000/api/auth/verify-email?token=123:1712345678:abcdef...
```

Copy the verification URL from the console and open it in your browser.

### Testing Region Override

To test the WeChat flow or CN-specific UI without being in China:

```
http://localhost:5173/terminal?region=cn
```

This forces the frontend to show the WeChat login button instead of Google.

### Testing WeChat Locally

WeChat OAuth requires a public callback URL. For local testing:

1. Use a tunnel (e.g., ngrok): `ngrok http 8000`
2. Set `WECHAT_REDIRECT_URI=https://your-tunnel.ngrok.io/api/auth/wechat/callback`
3. Note: WeChat only allows registered callback domains, so you may need to use a test app ID from WeChat's sandbox environment

---

## 12. Security Considerations

### Password Hashing

- Passwords are hashed with **bcrypt** (`bcrypt.hashpw` with auto-generated salt)
- bcrypt internally uses a cost factor of 12 (default), making brute-force expensive
- Only `auth_method="email"` users have a `password_hash`; the column is NULL for Google/WeChat users

### Token Security

**HMAC verification/reset tokens:**
- Format: `{user_id}:{timestamp}:{hmac_signature}`
- Signed with `APP_JWT_SECRET` using HMAC-SHA256 (truncated to 32 hex chars)
- Verification tokens expire in 24 hours
- Reset tokens expire in 1 hour
- Comparison uses `hmac.compare_digest()` (constant-time) to prevent timing attacks

**App JWTs (email/password + WeChat):**
- Signed with HS256 using `APP_JWT_SECRET`
- Default expiry: 7 days (configurable via `APP_JWT_EXPIRY_DAYS`)
- Claims include: `sub` (user ID), `provider`, `display_name`, `iat`, `exp`
- Verified using PyJWT's `jwt.decode()` which checks expiry automatically

**Firebase ID tokens (Google OAuth):**
- Signed by Google (RS256)
- Verified by Firebase Admin SDK (fetches Google's public keys)
- Short-lived (1 hour), auto-refreshed by the Firebase JS SDK on the frontend

### CSRF Protection

- WeChat OAuth uses an HMAC-signed `state` parameter: `{timestamp}:{nonce}:{signature}`
- State expires after 5 minutes
- Prevents attackers from initiating OAuth flows and hijacking callbacks
- Google OAuth is handled by Firebase's popup flow, which has built-in CSRF protection

### Email Enumeration Prevention

- `POST /api/auth/forgot-password` always returns a generic success message regardless of whether the email exists
- `POST /api/auth/resend-verification` always returns a generic success message
- `POST /api/auth/signup` does reveal if an email is taken (409 response), which is a common UX trade-off

### Provider Conflict Handling

When a user tries to sign up with email/password but their email is already registered via Google or WeChat:
- The signup endpoint returns a 409 error
- A "provider conflict" email is sent explaining which method they originally used
- This prevents account takeover (an attacker cannot create a password for a Google-authenticated email)

### Rate Limiting

Auth endpoints should be rate-limited to prevent brute-force attacks. The application uses Flask-Limiter with per-tier limits. Recommended limits for auth endpoints:

- `/api/auth/signin`: 10 requests/minute per IP
- `/api/auth/signup`: 5 requests/minute per IP
- `/api/auth/forgot-password`: 3 requests/minute per IP

### Additional Hardening

- `disabled` flag on users allows immediate account lockout without deleting data
- Test account detection via email patterns (e.g., `+test@`, `+qa@`) prevents test accounts from being used in production billing
- App JWT secret should be at least 32 bytes (64 hex characters) for HS256 security
- Firebase service account JSON should never be exposed to the frontend or committed to version control

---

## API Endpoint Reference

| Method | Endpoint | Auth Required | Description |
|---|---|---|---|
| `POST` | `/api/auth/signup` | No | Create account with email/password |
| `POST` | `/api/auth/signin` | No | Sign in, returns app JWT |
| `GET` | `/api/auth/verify-email` | No | Verify email via token link |
| `POST` | `/api/auth/forgot-password` | No | Send password reset email |
| `POST` | `/api/auth/reset-password` | No | Reset password with token |
| `POST` | `/api/auth/resend-verification` | No | Resend verification email |
| `POST` | `/api/auth/refresh` | Yes | Refresh app JWT (email/WeChat only) |
| `GET` | `/api/auth/me` | Yes | Get current user profile |
| `GET` | `/api/auth/tier` | No | Get user's tier and features |
| `GET` | `/api/auth/region` | No | Get region detection result |
| `GET` | `/api/auth/wechat/login` | No | Redirect to WeChat QR page |
| `GET` | `/api/auth/wechat/callback` | No | WeChat OAuth callback |
| `GET` | `/api/pricing` | No | Get all tier definitions |
