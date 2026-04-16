# Load Test Report -- SIGNAL (InstantNews)

## 1. Load Test Scripts

### Files

| File | Purpose |
|------|---------|
| `tests/load/locustfile.py` | Main Locust test suite with all endpoint tasks |
| `tests/load/config.py` | Profile definitions (100, 500, 1000 users) and thresholds |
| `tests/load/run_load_tests.py` | CLI helper to run profiles with CSV/HTML output |

### How to Run

```bash
# Install dependencies
pip install -r requirements-dev.txt

# Quick local test (100 users)
locust -f tests/load/locustfile.py --host http://localhost:8000 \
       --users 100 --spawn-rate 10 --run-time 5m --headless

# Target threshold test (500 users against production)
locust -f tests/load/locustfile.py --host https://www.instnews.net \
       --users 500 --spawn-rate 50 --run-time 10m --headless

# Stress test (1000 users)
locust -f tests/load/locustfile.py --host https://www.instnews.net \
       --users 1000 --spawn-rate 100 --run-time 10m --headless

# Web UI mode (interactive)
locust -f tests/load/locustfile.py --host https://www.instnews.net

# Run all profiles sequentially with output
python tests/load/run_load_tests.py --all --host https://www.instnews.net

# With authentication (for testing authed endpoints)
export LOAD_TEST_AUTH_TOKEN="<firebase-id-token>"
locust -f tests/load/locustfile.py --host https://www.instnews.net \
       --users 500 --spawn-rate 50 --run-time 10m --headless
```

### Endpoint Coverage

| Endpoint | Task Class | Auth Required |
|----------|------------|---------------|
| `GET /` (landing) | LandingPageTasks | No |
| `GET /pricing` | LandingPageTasks | No |
| `GET /docs` | LandingPageTasks | No |
| `GET /terminal` | LandingPageTasks | No |
| `GET /terms`, `GET /privacy` | LandingPageTasks | No |
| `GET /api/news` (default) | NewsFeedTasks | No |
| `GET /api/news?limit=N` | NewsFeedTasks | No |
| `GET /api/news?source=X` | NewsFeedTasks | No |
| `GET /api/news?q=keyword` | NewsFeedTasks | No |
| `GET /api/news?sentiment=X` | NewsFeedTasks | No |
| `GET /api/news` (combined filters) | NewsFeedTasks | No |
| `GET /api/stats` | StatsAndSourcesTasks | No |
| `GET /api/sources` | StatsAndSourcesTasks | No |
| `GET /api/docs` | StatsAndSourcesTasks | No |
| `GET /api/pricing` | StatsAndSourcesTasks | No |
| `GET /api/auth/me` | AuthenticatedTasks | Yes |
| `GET /api/auth/tier` | AuthenticatedTasks | Yes |
| `GET /api/billing/status` | AuthenticatedTasks | Yes |
| `POST /api/billing/checkout` | CheckoutTasks | Yes |

### User Profiles (Traffic Distribution)

| User Type | Weight | Wait Time | Simulates |
|-----------|--------|-----------|-----------|
| AnonymousVisitor | 60% | 1-5s | Browsing marketing pages + public API |
| AuthenticatedUser | 30% | 0.5-3s | Terminal power users querying news |
| PayingCustomer | 10% | 2-8s | Paying users with occasional billing actions |

### Metrics Collected

For each endpoint, Locust automatically measures:
- **Response time**: min, max, median, average, p95, p99
- **Error rate**: count and percentage of failures
- **Throughput**: requests/sec and total requests
- **Time to first byte**: included in response time measurement

Results are output as CSV files and HTML reports when using `--csv` and `--html` flags.

---

## 2. Infrastructure Review

### 2.1 CDK Stack Analysis (`infra/stack.py`)

**ECS Web Service:**
- Task size: 0.5 vCPU / 1 GB RAM
- Desired count: 2 tasks
- Auto-scaling: 2-10 tasks, 60% CPU target
- Request-based scaling: 500 req/target triggers scale-out

**ECS Worker:**
- Task size: 0.5 vCPU / 2 GB RAM (for embedding model)
- Single instance, no scaling

**RDS PostgreSQL:**
- Instance type: `db.t3.micro`
- Single-AZ, 20 GB storage (auto-extends to 100 GB)
- 7-day backup retention

**Networking:**
- VPC with 2 AZs, 1 NAT gateway
- ALB with HTTPS (ACM certificate)
- Health check: `GET /api/stats` every 30s

### 2.2 Nginx Config (`deploy/nginx.conf`)

- Static assets served directly with `expires 1h` and `Cache-Control: public, immutable`
- API proxy timeout: 30s read, 5s connect
- Gzip enabled for text/css/json/js/xml
- Proxies to Gunicorn on port 8001

### 2.3 Database Connection Pool (`app/database.py`)

- PostgreSQL pool: `pool_size=2`, `max_overflow=3` (5 connections max per process)
- `pool_pre_ping=True` (validates connections before use)
- `pool_recycle=300` (5 min connection recycling)

### 2.4 Application Architecture

- Flask app factory pattern with SQLAlchemy sessions
- Sessions created per-request and closed in `finally` blocks
- `maybe_refresh()` called on every `/api/news`, `/api/stats`, `/api/sources` request
- No application-level rate limiting implemented (only defined in tier config)
- No response caching layer

---

## 3. Identified Bottlenecks and Remediation

### CRITICAL: Database Connection Pool Exhaustion

**Finding:** `pool_size=2` with `max_overflow=3` gives only 5 connections per Gunicorn worker. With 4 workers (production gunicorn command), that is 20 total connections. `db.t3.micro` has a max of ~87 connections (based on `LEAST(DBInstanceClassMemory/9531392, 5000)`), but the pool is severely undersized for the task count.

**Impact:** At 500+ concurrent users, connection pool will saturate. Requests will queue waiting for a connection, causing p95 latency spikes and timeouts.

**Remediation:**
```python
# In app/database.py, increase pool for PostgreSQL:
kwargs["pool_size"] = 5
kwargs["max_overflow"] = 10
```
With 2 ECS tasks x 4 Gunicorn workers x 15 connections = 120 max. Since `db.t3.micro` caps at ~87, either:
1. Increase to `db.t3.small` (172 max connections), or
2. Add PgBouncer as a connection pooler sidecar, or
3. Keep pool_size=5, max_overflow=5 (80 max, fits within t3.micro limits)

**Priority:** P0 -- will cause failures under load

---

### CRITICAL: `maybe_refresh()` Called on Every Read Request

**Finding:** The `/api/news`, `/api/stats`, and `/api/sources` endpoints all call `maybe_refresh()` which checks staleness and may trigger a full feed refresh (15 parallel HTTP calls + embedding computation). Under load, multiple concurrent requests could trigger simultaneous refreshes.

**Impact:** Feed refresh holds a database session and makes external HTTP calls. Under 500 concurrent users, if staleness threshold (30s) is hit, dozens of requests could attempt refresh simultaneously, exhausting connections and CPU.

**Remediation:**
1. Move feed refresh entirely to the worker process (already deployed separately via ECS)
2. Remove `maybe_refresh()` calls from read endpoints
3. If in-process refresh is needed, add a lock to prevent concurrent refreshes:
```python
import threading
_refresh_lock = threading.Lock()

def maybe_refresh(session_factory, config):
    if not _refresh_lock.acquire(blocking=False):
        return  # Another thread is already refreshing
    try:
        # ... existing refresh logic
    finally:
        _refresh_lock.release()
```

**Priority:** P0 -- causes cascading failures under load

---

### HIGH: ECS Task Memory Too Low for Web Service

**Finding:** Web tasks have 1 GB RAM. The sentence-transformers model (~500 MB) loads lazily on first feed refresh. If `maybe_refresh()` triggers in the web container (WORKER_ENABLED=false, but `maybe_refresh` still runs inline), the container will OOM.

**Impact:** With WORKER_ENABLED=false in the web task, the inline `maybe_refresh` path still exists and will load the embedding model into web container memory, leaving little room for request handling.

**Remediation:**
1. Ensure `maybe_refresh()` in web containers only reads from DB, never triggers actual feed fetching
2. Or increase web task memory to 2 GB if in-process refresh is needed
3. Best approach: remove `maybe_refresh()` from endpoints entirely and rely on the worker

**Priority:** P1

---

### HIGH: No Application-Level Response Caching

**Finding:** `/api/stats` and `/api/sources` run aggregate SQL queries on every request (COUNT, GROUP BY, AVG). These are the health check endpoints too (ALB checks `/api/stats` every 30s per target).

**Impact:** Under 500 concurrent users, identical aggregate queries will hit the database repeatedly. Stats data changes only every 30s (feed refresh interval), so most queries return identical results.

**Remediation:**
1. Add in-memory caching (e.g., Flask-Caching or simple TTL dict):
```python
from functools import lru_cache
from time import time

_stats_cache = {"data": None, "expires": 0}

def get_cached_stats(session_factory, config):
    if time() < _stats_cache["expires"]:
        return _stats_cache["data"]
    # ... compute stats
    _stats_cache["data"] = result
    _stats_cache["expires"] = time() + 10  # 10s TTL
    return result
```
2. For production, consider Redis as a shared cache across ECS tasks

**Priority:** P1

---

### HIGH: Single NAT Gateway

**Finding:** CDK stack uses `nat_gateways=1`. All egress traffic (worker fetching RSS feeds, outbound API calls) routes through a single NAT gateway.

**Impact:** NAT gateway has a 55,000 simultaneous connection limit and 45 Gbps bandwidth. Not a bottleneck for current traffic, but it is a single point of failure. If the NAT gateway's AZ goes down, the worker and any ECS tasks in private subnets lose internet access.

**Remediation:**
```python
nat_gateways=2  # One per AZ for HA
```
Cost: ~$32/month additional. Recommended for production.

**Priority:** P2

---

### MEDIUM: No Rate Limiting Enforcement

**Finding:** Tier config defines `api_rate_per_minute` (10 for free, 60 for plus, 120 for max) but no middleware enforces these limits. Any user can make unlimited requests.

**Impact:** A single abusive client could consume disproportionate resources. Under load test, this is actually favorable (no artificial limits), but in production it is a gap.

**Remediation:**
1. Add Flask rate limiting middleware (e.g., Flask-Limiter with Redis backend)
2. Implement at the ALB/WAF level using AWS WAF rate-based rules
3. At minimum, add nginx `limit_req` directives:
```nginx
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
location /api/ {
    limit_req zone=api burst=20 nodelay;
    ...
}
```

**Priority:** P2

---

### MEDIUM: `db.t3.micro` is Burstable and CPU-Constrained

**Finding:** `db.t3.micro` has 2 vCPUs (burstable) and 1 GB RAM. Under sustained load, CPU credits will deplete, throttling database performance to baseline (10% of vCPU).

**Impact:** After CPU credit exhaustion (typically 30-60 minutes of sustained load), query latency will increase dramatically. The aggregate queries in `/api/stats` and `/api/sources` are particularly CPU-intensive.

**Remediation:**
1. Switch to `db.t3.small` (2 GB RAM, higher credit earn rate) -- ~$15/month vs ~$7.50/month
2. Monitor CPU credit balance via CloudWatch
3. For launch, consider `db.t3.medium` to ensure credits do not deplete during traffic spikes
4. Long-term: if sustained CPU >40%, move to `db.m6g.large` (non-burstable)

**Priority:** P2

---

### MEDIUM: Nginx Missing Connection Limits and Buffering Tuning

**Finding:** The nginx config has no `worker_connections`, `keepalive_timeout`, `client_max_body_size`, or proxy buffering tuning. Default `worker_connections` is 512.

**Remediation:**
```nginx
worker_processes auto;
events {
    worker_connections 2048;
}

http {
    keepalive_timeout 65;
    client_max_body_size 1m;

    # Proxy buffering for upstream
    proxy_buffer_size 128k;
    proxy_buffers 4 256k;

    # Connection reuse to upstream
    upstream gunicorn {
        server 127.0.0.1:8001;
        keepalive 32;
    }
}
```

**Priority:** P2

---

### LOW: Health Check Hits Database

**Finding:** ALB health check calls `GET /api/stats` every 30s per target. This runs aggregate queries (COUNT, GROUP BY, AVG) on every check. With 10 max tasks, that is 20 aggregate queries/minute just for health checks.

**Remediation:** Create a lightweight `/health` endpoint that only checks database connectivity:
```python
@app.route("/health")
def health():
    try:
        session = session_factory()
        session.execute(text("SELECT 1"))
        session.close()
        return jsonify({"status": "ok"})
    except Exception:
        return jsonify({"status": "error"}), 500
```

**Priority:** P3

---

### LOW: No Database Indexes Verified

**Finding:** The news query filters on `source`, `sentiment_label`, `published`, and uses `LIKE` on `title`/`summary`. Without confirming indexes exist on these columns, query performance under load may degrade as the table grows.

**Remediation:** Verify via Alembic migration or direct check:
```sql
CREATE INDEX IF NOT EXISTS ix_news_source ON news (source);
CREATE INDEX IF NOT EXISTS ix_news_sentiment ON news (sentiment_label);
CREATE INDEX IF NOT EXISTS ix_news_published ON news (published DESC);
CREATE INDEX IF NOT EXISTS ix_news_source_published ON news (source, published DESC);
```

**Priority:** P3

---

## 4. Pass/Fail Thresholds

| Metric | Threshold | Status |
|--------|-----------|--------|
| API endpoints p95 latency | < 500ms | **PENDING** (run tests) |
| Page load p95 latency | < 2s | **PENDING** (run tests) |
| Error rate at 500 concurrent | < 1% | **AT RISK** -- connection pool too small |
| Zero data corruption under concurrent writes | No concurrent writes to same rows | **LIKELY PASS** -- webhook idempotency via StripeEvent |

### Risk Assessment

| Concurrency | Expected Result | Confidence |
|-------------|-----------------|------------|
| 100 users | PASS all thresholds | High |
| 500 users | FAIL without remediations | High -- connection pool (5/process) will exhaust |
| 1000 users | FAIL | High -- db.t3.micro CPU credits + pool exhaustion |

### Pre-Launch Remediation Checklist

- [ ] Increase database connection pool to `pool_size=5, max_overflow=5`
- [ ] Remove `maybe_refresh()` from read endpoints (rely on worker)
- [ ] Add response caching for `/api/stats` and `/api/sources` (10s TTL)
- [ ] Create lightweight `/health` endpoint, update ALB health check
- [ ] Upgrade RDS to `db.t3.small` or `db.t3.medium`
- [ ] Add `limit_req` to nginx or AWS WAF rate rules
- [ ] Verify database indexes on news table
- [ ] Run baseline (100 user) load test, fix issues, then run target (500 user) test
- [ ] Add second NAT gateway for HA (optional, cost-dependent)
