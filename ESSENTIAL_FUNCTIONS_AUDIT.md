# Essential Functions Audit -- InstNews (SIGNAL)

**Date:** 2026-04-02
**Auditor:** Automated codebase analysis
**Scope:** Pre-launch SaaS readiness check

---

## Auth & Account

| Function | Status | Priority | Notes |
|----------|--------|----------|-------|
| Email/password sign-up | MISSING | P0 | Being built by another agent. Currently only Google OAuth exists (`auth.js` uses `signInWithRedirect` with `GoogleAuthProvider` exclusively). |
| Email/password sign-in | MISSING | P0 | Being built by another agent. No `EmailAuthProvider` usage anywhere in the codebase. |
| Password reset flow | MISSING | P0 | Required if email/password auth is added. Firebase provides `sendPasswordResetEmail()` but it is not wired up anywhere. |
| Email verification after sign-up | MISSING | P1 | Firebase provides `sendEmailVerification()` but not used. Backend does not check `email_verified` claim in token. `middleware.py` line 62 creates user regardless of verification status. |
| Google OAuth sign-in | EXISTS | -- | Working via Firebase redirect flow (`auth.js` lines 95-99). |
| Sign out | EXISTS | -- | Working. `SignalAuth.signOut()` at `auth.js` line 102. Terminal UI has sign-out button in user dropdown (`index.html` line 133). |
| Session persistence | EXISTS | -- | Firebase SDK handles token persistence and auto-refresh every 50 minutes (`auth.js` lines 191-201). |
| Account deletion / data export (GDPR) | MISSING | P0 | No API endpoint for account deletion. No data export endpoint. Privacy policy (section 4, 7) promises users can request deletion, but there is no self-service mechanism. The `User` model has no soft-delete field. No cascade delete logic for user data (news items are shared, but `Subscription` has `CASCADE` on user FK). |
| Terms of Service acceptance on sign-up | MISSING | P1 | No ToS checkbox or acceptance tracking on sign-up. The sign-in flow (`auth.js`) goes directly to Google OAuth with no intermediate acceptance step. No `tos_accepted_at` field on the `User` model. |

## User Experience

| Function | Status | Priority | Notes |
|----------|--------|----------|-------|
| User profile/account page | MISSING | P0 | Being built by another agent. Currently the terminal only shows name/avatar/tier in the header dropdown (`index.html` lines 120-134). No dedicated account settings page. |
| Onboarding flow for new users | MISSING | P2 | No first-time user experience, tutorial, or welcome modal. New users land on the terminal with no guidance. |
| Error pages: 404, 500, 403 | MISSING | P1 | No custom error handlers registered in `app/__init__.py`. Only a 429 handler exists (in `rate_limit.py` line 64). Flask will serve its default ugly HTML error pages for 404/500/403. |
| Loading states / skeleton screens | PARTIAL | P2 | The terminal has a "CONNECTING" status (`index.html` line 63) and the landing page has a spinner for the demo feed (`landing.html` line 227). But no skeleton screens for the main news table. |
| Offline/error handling in the UI | PARTIAL | P2 | Landing page catches fetch errors silently (`landing.js` lines 130, 170, 205-208). The terminal `app.js` has a connection status indicator but would need review for comprehensive offline handling. |
| Mobile responsiveness on ALL pages | PARTIAL | P1 | Landing page has hamburger menu (`landing.html` line 48, `landing.js` line 28). Terminal has mobile sidebar (`index.html` lines 33-39, 141). Pricing page has a media query for mobile grid (`pricing.html` line 74). However, `privacy.html` and `terms.html` have NO responsive testing indicators -- they use simple max-width containers which should be fine. `docs.html` needs verification. |
| Favicon and meta tags on ALL pages | PARTIAL | P1 | Favicon: present on `landing.html`, `index.html`, `pricing.html`, `docs.html` (all use inline SVG data URI). MISSING on `privacy.html` and `terms.html`. OG tags: only on `landing.html` (lines 8-11). Missing on `index.html`, `pricing.html`, `docs.html`, `privacy.html`, `terms.html`. |

## Billing & Subscription

| Function | Status | Priority | Notes |
|----------|--------|----------|-------|
| Checkout flow | EXISTS | -- | Stripe Checkout integration via `/api/billing/checkout` endpoint (`billing/routes.py` lines 37-85). Includes trial period support. |
| Subscription status display | EXISTS | -- | `/api/billing/status` endpoint (`billing/routes.py` lines 117-132) returns subscription status with human-readable labels. Pricing page shows success/cancel alerts. |
| Cancel/downgrade flow | EXISTS | -- | Via Stripe Customer Portal (`/api/billing/portal`, `billing/routes.py` lines 88-114). Webhook handles `customer.subscription.deleted` (line 273) and `cancel_at_period_end` tracking. |
| Upgrade flow | EXISTS | -- | Checkout endpoint supports upgrading. Stripe Customer Portal handles plan changes. |
| Invoice history | PARTIAL | P2 | Handled by Stripe Customer Portal (users redirect there). No in-app invoice view. Acceptable for launch. |
| Payment method update | PARTIAL | P2 | Handled by Stripe Customer Portal. No in-app UI. Acceptable for launch. |
| Failed payment handling / grace period | EXISTS | -- | `invoice.payment_failed` webhook handler marks subscription as `past_due` (`billing/routes.py` lines 293-306). Stripe's built-in retry logic handles grace period. |
| Proration on plan changes | PARTIAL | P2 | Only one paid tier (Pro) currently visible, so proration is not relevant yet. When Max tier launches, Stripe handles proration by default. |
| Subscription status visible in UI | MISSING | P1 | The terminal dropdown shows tier badge (`index.html` line 125), but there is no way for users to see their subscription end date, trial status, or manage billing from the terminal. The pricing page button says "Current Plan" statically -- it does not dynamically reflect the user's actual subscription status. |

## Communication

| Function | Status | Priority | Notes |
|----------|--------|----------|-------|
| Transactional emails (welcome, confirmation, cancellation, trial ending) | MISSING | P1 | No email sending infrastructure. `_handle_trial_will_end` (`billing/routes.py` line 309) has a comment "Future: send email notification" but no implementation. Stripe can send receipt emails natively (enable in Stripe Dashboard), but welcome emails and trial-ending warnings need custom implementation. |
| Contact/support channel | PARTIAL | P1 | Email addresses listed: `support@instnews.net` (in terms.html) and `privacy@instnews.net` (in privacy.html). Pricing page has "Contact us" mailto link. But no chat widget, no support form, no help center. Need to verify these email addresses actually work (mailbox configured). |
| Changelog / what's new | MISSING | P2 | No changelog page. Not a launch blocker but useful for retention. |

## Legal & Compliance

| Function | Status | Priority | Notes |
|----------|--------|----------|-------|
| Privacy Policy page | EXISTS | -- | Full privacy policy at `/privacy` (`privacy.html`). Covers data collection, sharing, retention, security, cookies, user rights. Dated April 2, 2026. |
| Terms of Service page | EXISTS | -- | Full ToS at `/terms` (`terms.html`). Covers subscriptions, acceptable use, IP, disclaimer, limitation of liability. Dated April 2, 2026. |
| Cookie consent banner | MISSING | P1 | No cookie consent banner anywhere. Privacy policy (section 6) states "We use essential cookies for authentication" but EU GDPR/ePrivacy still requires informed consent. Firebase Auth uses cookies/localStorage. The `measurementId: "G-2MJ3MD0WBQ"` in Firebase config suggests Google Analytics measurement is configured, which would require consent. |
| GDPR data deletion request handling | MISSING | P0 | Privacy policy promises data deletion (sections 4, 7) but no mechanism exists. No `/api/account/delete` endpoint. No admin tool for processing deletion requests. |

## SEO & Marketing

| Function | Status | Priority | Notes |
|----------|--------|----------|-------|
| robots.txt | MISSING | P1 | No `robots.txt` file in `static/`. No route serving it. Search engines will crawl everything including `/terminal` and `/api/*` endpoints. |
| sitemap.xml | MISSING | P2 | No `sitemap.xml` file. Should list `/`, `/pricing`, `/docs`, `/privacy`, `/terms`. |
| Open Graph meta tags on all pages | PARTIAL | P1 | Only `landing.html` has OG tags (og:title, og:description, og:type, og:url). Missing `og:image`. All other pages (`index.html`, `pricing.html`, `docs.html`, `privacy.html`, `terms.html`) lack OG tags entirely. |
| Analytics | PARTIAL | P2 | Firebase config includes `measurementId: "G-2MJ3MD0WBQ"` but no Google Analytics gtag.js or Firebase Analytics SDK is loaded. The measurement ID is configured but not active -- no analytics data is being collected. |

## Security

| Function | Status | Priority | Notes |
|----------|--------|----------|-------|
| HTTPS enforced | EXISTS | -- | ALB configured with `redirect_http=True` in CDK stack (`stack.py` line 198). ACM certificate for domain + www subdomain. |
| CSRF protection on forms | MISSING | P1 | No CSRF protection. Flask does not include CSRF by default. All state-changing API endpoints (`/api/billing/checkout`, `/api/billing/portal`, `/api/refresh`) use JSON POST with Bearer token auth, which provides some CSRF resistance (browser-native forms cannot set custom headers). The webhook endpoint uses Stripe signature verification. Risk is LOW but should be documented or explicitly mitigated. |
| Content Security Policy headers | MISSING | P1 | No CSP headers in `nginx.conf` or Flask app. No `X-Frame-Options`, `X-Content-Type-Options`, or `Referrer-Policy` headers set anywhere. The nginx config (`deploy/nginx.conf`) only sets proxy headers and caching -- no security headers. |
| Rate limiting on auth endpoints | PARTIAL | P1 | Global rate limiting exists via Flask-Limiter on all `/api/*` endpoints (10/min for free, 60/min for pro). However, there is no specific stricter limit on auth-related actions. Firebase handles its own rate limiting on the authentication side. The backend `load_current_user` middleware runs on every request but just verifies tokens (not a login endpoint itself). |
| Brute force protection on login | PARTIAL | P1 | Firebase handles brute force protection for Google OAuth. When email/password auth is added, Firebase also provides account lockout. However, the backend has no awareness of failed attempts -- it silently treats invalid tokens as anonymous (`middleware.py` line 52). |
| Firebase API key exposed in frontend | EXISTS (by design) | P2 | The Firebase API key (`AIzaSyBJO7au...`) is in `auth.js` line 18. This is normal for Firebase client-side apps -- the key is restricted by Firebase Security Rules and domain allowlists. Verify that the Firebase project has proper domain restrictions configured in the Firebase Console. |

## Operations

| Function | Status | Priority | Notes |
|----------|--------|----------|-------|
| Health check endpoint | EXISTS | -- | Nginx proxies `/health` to `/api/stats` (`nginx.conf` line 40). ECS task has container health check using `curl -f http://localhost:8000/api/stats` (`stack.py` line 176). ALB target group checks `/api/stats` (`stack.py` line 203). |
| Logging (structured logs) | PARTIAL | P1 | CloudWatch log groups configured for web and worker (`stack.py` lines 137, 239). Gunicorn access logs enabled (`Dockerfile` line 23, `--access-logfile -`). However, application code uses no structured logging -- errors are silently caught with bare `except` and `pass` in multiple places (`__init__.py` lines 78, 94; `middleware.py` line 98). No JSON logging format. |
| Error tracking (Sentry, etc.) | MISSING | P1 | No Sentry, Bugsnag, or any error tracking service integrated. Errors in webhook handlers (`billing/routes.py` line 186) are re-raised but not reported. Multiple bare `except: pass` blocks silently swallow errors. |
| Uptime monitoring | MISSING | P2 | No external uptime monitoring configured (no Pingdom, UptimeRobot, or CloudWatch Synthetics). Health checks exist on ALB/ECS level but no external alerting. |
| Backup strategy for database | EXISTS | -- | RDS configured with 7-day backup retention (`stack.py` line 103). `RemovalPolicy.SNAPSHOT` ensures snapshot on stack deletion. Multi-AZ is disabled (noted as cost optimization). |

---

## Priority Summary

### P0 -- Launch Blockers (must fix before accepting payments)

1. **Account deletion (GDPR)** -- Privacy policy promises it, no mechanism exists. Legal liability.
2. **Password reset flow** -- Required once email/password auth ships. Cannot have email login without password reset.
3. **GDPR data deletion endpoint** -- Same as item 1; need at minimum a manual process and ideally a self-service API.
4. **Email/password sign-up/sign-in** -- Being built by another agent.
5. **User profile/account page** -- Being built by another agent.

### P1 -- Should Fix for Launch

6. **Error pages (404, 500, 403)** -- Users hitting wrong URLs get ugly Flask default pages.
7. **robots.txt** -- Prevent search engines from indexing API endpoints and terminal.
8. **Content Security Policy headers** -- Missing all security headers in nginx.
9. **Cookie consent banner** -- Required for EU users, especially with Firebase/analytics.
10. **Email verification after sign-up** -- Prevent fake accounts, verify ownership.
11. **ToS acceptance tracking** -- Legal protection for the service.
12. **Subscription status visible in UI** -- Users need to see their trial end date and billing status.
13. **Transactional emails** -- At minimum enable Stripe receipt emails. Trial-ending warnings needed.
14. **Contact/support channel** -- Verify `support@instnews.net` mailbox works. Consider adding a support form.
15. **OG meta tags on all pages** -- Social sharing will look broken on most pages.
16. **Favicon on privacy/terms pages** -- Minor but looks unprofessional.
17. **Structured logging** -- Silent `except: pass` blocks make debugging production issues impossible.
18. **Error tracking (Sentry)** -- Cannot debug production errors without it.
19. **CSRF documentation** -- Explicitly document that JSON + Bearer token mitigates CSRF.

### P2 -- Post-Launch OK

20. **Onboarding flow** -- Nice to have for conversion but not blocking.
21. **Loading states / skeleton screens** -- Cosmetic improvement.
22. **sitemap.xml** -- SEO improvement, not blocking.
23. **Analytics** -- Measurement ID configured but not active. Wire up or remove.
24. **Changelog** -- Retention feature, not blocking.
25. **Invoice history in-app** -- Stripe Portal covers this.
26. **Uptime monitoring** -- Set up external monitoring after launch.
27. **Firebase domain restrictions** -- Verify in Firebase Console that API key is locked to production domain.

---

## Critical Code Issues Found During Audit

1. **Silent error swallowing** -- Multiple `except: pass` blocks:
   - `app/__init__.py` line 78 (Firebase init failure)
   - `app/__init__.py` line 94 (feed refresh errors)
   - `app/auth/middleware.py` line 98 (user creation/lookup errors)
   These should at minimum log the error.

2. **No structured error responses** -- API endpoints return Flask defaults for unhandled exceptions. No global error handler registered except for 429.

3. **SQL injection risk is LOW** -- Using SQLAlchemy ORM throughout, but the keyword search (`news.py` line 46) uses `.like(f"%{query}%")` which is safe because SQLAlchemy parameterizes it. Confirmed safe.

4. **Firebase config hardcoded** -- `auth.js` has Firebase config inline (lines 17-25). This is normal for client-side Firebase but should be verified that the Firebase project has proper domain restrictions.
