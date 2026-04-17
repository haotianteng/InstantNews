# Development Workflow

Read this first when starting a new session. Everything you need to resume work is here.

## Project State (as of 2026-04-17)

**Production**: `https://www.instnews.net` — live on AWS (ECS Fargate + RDS PostgreSQL)
**Main branch**: `main` — deploys automatically via GitHub Actions
**Working branch pattern**: feature branches like `ralph/terminal-evolution`, merge into `main` to ship

## Local Dev Environment

### Stack
- **Backend**: Flask, runs in Docker Compose (port 8000)
- **Frontend**: Vite dev server (port 5173) with HMR
- **Database**: SQLite at `data/news_terminal.db` (prod uses PostgreSQL)
- **Python**: use `base` conda env (`/home/haotiant/conda/bin/python`) — the `instnews` conda env is missing the `anthropic` package, backfill script fails there

### Start local servers

```bash
# Backend (Docker Compose — loads .env automatically via docker-compose.override.yml)
docker compose down && docker compose up -d

# Frontend (Vite — use --host 0.0.0.0 so it's reachable from any IP)
cd frontend && npx vite --host 0.0.0.0 &
```

Test: `curl http://localhost:8000/api/stats` (200) and `curl http://localhost:5173/` (200).

### Rebuild after Python code changes
Docker container caches the app code — after editing Python, rebuild:

```bash
docker build -t instantnews-signal . && docker compose down && docker compose up -d
```

Frontend changes: Vite HMR picks them up automatically, no rebuild needed.

### Rebuild static assets for the Docker path
If testing on port 8000 (Docker serves built assets from `static/`), rebuild:

```bash
cd frontend && npm run build   # outputs to ../static/
```

### Test accounts

Create test accounts via the admin console OR directly in the DB. To make a test account usable for email/password login, it needs `password_hash` AND `email_verified=True`. The admin `create_test_account` endpoint now sets both (fixed in commit `5ce1d3a` era).

Known working test account for Playwright:
- Email: `playwright-pro@test.com`
- Password: `test1234`
- Tier: max (via test_tier_override + is_test_account=True)

## Deployment

Two paths — use the right one:

### App code changes → GitHub Actions
```
push to main → tests → Docker build → ECR → ECS rolling deploy
```

**Required**: classic GitHub PAT with `repo` + `workflow` scopes for pushing `.github/workflows/*.yml`. Fine-grained tokens don't support workflow pushes.

Token location: `~/.git-credentials` (global) or `.git/instnews-credentials` (local). Currently the global one is used.

### Infrastructure changes → CDK
```bash
cd infra
npx cdk diff         # review
npx cdk deploy --require-approval never
```

**When to use CDK**:
- Adding/removing env vars or secret bindings in `stack.py`
- Changing ECS task sizes, scaling, IAM, security groups
- Route 53, ACM, VPC, RDS changes

**Important**: GitHub Actions `ecs update-service` only refreshes the Docker image — it uses the **existing task definition**. New secrets/env vars require `cdk deploy` first.

See `docs/deployment.md` for full details.

## Mandatory Playwright Tests (before merge)

Before marking any UI/billing feature complete, run the checklist in `CLAUDE.md` → "Mandatory Playwright Tests". Summary:

1. **Auth flows** — Google OAuth popup opens, email/password signin returns token
2. **Subscription** — Subscribe opens Stripe sidebar with Payment Element; test accounts show instant upgrade
3. **Company panel** — stock shows 5 tabs, futures shows Overview only with contract specs, currency shows Overview with forex data
4. **Column locking** — Pro user sees lock icon + MAX badge on ticker/confidence/risk columns
5. **No JS console errors** on page loads (429s acceptable, JS exceptions not)
6. **All pages return 200**: `/`, `/terminal`, `/pricing`, `/account`, `/docs`

Use Playwright MCP tools: `browser_navigate`, `browser_evaluate`, `browser_click`, `browser_take_screenshot`.

## Key Files to Know

### Backend
- `app/__init__.py` — Flask app factory, registers routes, starts background worker
- `app/models.py` — SQLAlchemy models (News, User, Subscription, CompanyDataCache, etc.)
- `app/database.py` — session factory, primary + replica
- `app/services/market_data.py` — Polygon client (uses **v3 universal snapshot** now)
- `app/services/cache_manager.py` — L2 DB cache for company data
- `app/services/feed_refresh.py` — RSS fetch + AI analysis + cache warm-up
- `app/services/bedrock_analysis.py` — MiniMax → Claude → Bedrock fallback chain
- `app/billing/routes.py` — Stripe checkout, downgrade, webhook
- `app/billing/stripe_client.py` — uses `ui_mode: "elements"` for sidebar checkout
- `app/admin/routes.py` — admin-only endpoints (includes cache inspection)
- `app/auth/middleware.py` — auth via API key, app JWT, or Firebase token
- `deploy/entrypoint.sh` — runs `alembic upgrade head` on container start

### Frontend
- `frontend/src/terminal-app.js` — main terminal UI
- `frontend/src/checkout.js` — Stripe Custom Checkout sidebar (uses Basil SDK)
- `frontend/src/auth.js` — Firebase + email/password + WeChat auth
- `frontend/src/account.js` — account page with plans/billing/api keys
- `frontend/public/assets/icons/` — configurable SVG icons per asset type
- `frontend/terminal.html` — slide-out panel markup (`<aside class="cp-panel">`)

### Infra
- `infra/stack.py` — CDK stack (VPC, RDS, ECS, ALB, Route 53, VPN)
- `Dockerfile.prod` — production image (Nginx + Gunicorn via Supervisor)
- `.github/workflows/deploy.yml` — CI/CD pipeline

## Database

### Schema changes
Write migration in `migrations/versions/NNN_xxx.py`, commit, push. The ECS entrypoint runs `alembic upgrade head` on every container start.

```bash
alembic revision -m "description"   # creates NNN_xxx.py
# Edit upgrade() and downgrade()
alembic upgrade head                  # test locally against SQLite
```

See `docs/database-migrations.md` for patterns.

### Production DB access
RDS is in a **private VPC** — no direct public access.

Two ways to inspect production data:
1. **Admin API cache endpoints** (recommended): `/admin/api/cache/stats`, `/admin/api/cache/<symbol>`, `/admin/api/cache/<symbol>/<data_type>` — requires admin role + VPN to `admin.instnews.net`
2. **CloudWatch logs**: `/ecs/instantnews-web`, `/ecs/instantnews-worker`, `/ecs/instantnews-admin`

See `docs/terminal-features.md` section 8 for the cache API.

## Current Feature State

See `docs/terminal-features.md` for the full reference. TL;DR of what shipped:
- Slide-out company profile panel (stock/futures/currency branching)
- Configurable asset type icons (`assets/icons/*.svg`)
- Polygon v3 universal snapshot (extended hours + 24h futures prices)
- Two-tier cache (L1 in-memory + L2 `company_data_cache` table)
- Proactive cache warm-up after AI analysis
- Stripe Custom Checkout sidebar (Basil SDK, `ui_mode: "elements"`)
- Downgrade flow with `pending_tier` column
- Max upgrade prompt for Pro users clicking locked columns
- Admin cache inspection API

## Open Backlog

In `tasks/`:
- `todo-yearly-pricing.md` — monthly/yearly toggle with strikethrough, Save % badge, yearly Stripe price IDs
- `todo-instrument-icons.md` — design custom SVG icons for asset classes
- `plan-company-data-cache.md` — reference for the L2 cache system
- `prd-terminal-evolution.md` — terminal feature PRD
- `prd-source-acquisition.md`, `live-source-prd.md` — news source PRDs

## Gotchas (Learned the Hard Way)

1. **Polygon v2 snapshot returns 0 when market is closed.** Always use `/v3/snapshot` — it includes `previous_close` and extended hours prices. Already fixed in `market_data.py`.

2. **Stripe `ui_mode` names keep changing**: v2-era was `embedded`, v15 SDK uses `embedded_page` for full-page or `elements` for sidebar. We use `elements` + Basil JS SDK.

3. **Fine-grained GitHub tokens can't push workflow files**. Use classic PAT with `workflow` scope. See `docs/deployment.md`.

4. **GitHub Actions only updates Docker image, not task definition.** Adding a new secret binding requires `cdk deploy` first. The POLYGON_API_KEY incident is the canonical example.

5. **`anthropic` package missing in the `instnews` conda env.** Use `base` conda (`/home/haotiant/conda/bin/python`) for any script that does AI analysis.

6. **Test accounts need both `password_hash` AND `email_verified=True`** to sign in via email/password. Admin `create_test_account` now sets both.

7. **Auth race condition**: on page load, `fetchNews()` fires before Firebase auth resolves → gets anonymous data. `fetchTier()` re-fetches after auth resolves to populate tier-gated fields. Don't re-introduce this bug.

8. **ECS stability wait after deploy takes 5-10 min** even after the service is actually healthy. Don't assume the deploy is stuck just because GitHub Actions shows "in_progress" for a while.

9. **The production DB replica is in a private subnet** — VPN doesn't reach it, and CloudFormation can't move an RDS instance to a different subnet group in-place. Use the admin API instead.

10. **CDK rollback on subnet group changes**: if you try to modify a DB subnet group that's in use, CFN will roll back. Create a new subnet group with a new logical ID and replace the RDS instance in two phases.
