# InstNews Company Information Architecture

A production-grade structure for handling company data (fundamentals, financials, competitors, institutional holders, insider transactions) with low-latency access and a clean code structure.

**Three layers:**
- **Storage** — Postgres as source of truth
- **Cache** — Redis for hot reads
- **Access** — Repository pattern with service-layer aggregation

---

## 1. Database Schema

### Layer 1: Stable Reference Data

```sql
-- Company master: rarely changes
CREATE TABLE companies (
  ticker          VARCHAR(10) PRIMARY KEY,
  cik             VARCHAR(10) UNIQUE,           -- SEC identifier
  name            VARCHAR(255) NOT NULL,
  exchange        VARCHAR(20),                   -- NYSE, NASDAQ
  sector          VARCHAR(100),
  industry        VARCHAR(100),
  country         VARCHAR(3),                    -- ISO 3166
  currency        VARCHAR(3),                    -- ISO 4217
  description     TEXT,
  website         VARCHAR(255),
  employee_count  INT,
  founded_year    INT,
  ipo_date        DATE,
  is_active       BOOLEAN DEFAULT TRUE,
  created_at      TIMESTAMP DEFAULT NOW(),
  updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_companies_sector ON companies(sector);
CREATE INDEX idx_companies_industry ON companies(industry);
```

### Layer 2: Time-Series Fundamentals & Financials

```sql
-- Quarterly/annual financial statements (append-only)
CREATE TABLE company_financials (
  ticker          VARCHAR(10) REFERENCES companies(ticker),
  period_end      DATE NOT NULL,
  period_type     VARCHAR(10) NOT NULL,          -- 'Q1','Q2','Q3','Q4','FY'
  fiscal_year     INT NOT NULL,

  -- Income Statement
  revenue         BIGINT,
  gross_profit    BIGINT,
  operating_income BIGINT,
  net_income      BIGINT,
  eps_basic       NUMERIC(10,4),
  eps_diluted     NUMERIC(10,4),

  -- Balance Sheet
  total_assets    BIGINT,
  total_liabilities BIGINT,
  total_equity    BIGINT,
  cash_equivalents BIGINT,
  long_term_debt  BIGINT,

  -- Cash Flow
  operating_cf    BIGINT,
  investing_cf    BIGINT,
  financing_cf    BIGINT,
  free_cash_flow  BIGINT,

  -- Metadata
  filing_date     DATE,
  source          VARCHAR(50),                   -- 'edgar','polygon','fmp'
  ingested_at     TIMESTAMP DEFAULT NOW(),

  PRIMARY KEY (ticker, period_end, period_type)
);

CREATE INDEX idx_financials_period ON company_financials(ticker, period_end DESC);

-- Forward-looking & computed fundamentals (updated frequently)
CREATE TABLE company_fundamentals (
  ticker              VARCHAR(10) PRIMARY KEY REFERENCES companies(ticker),
  market_cap          BIGINT,
  shares_outstanding  BIGINT,
  pe_ratio            NUMERIC(10,4),
  pb_ratio            NUMERIC(10,4),
  ev_ebitda           NUMERIC(10,4),
  dividend_yield      NUMERIC(6,4),
  beta                NUMERIC(6,4),

  next_earnings_date  DATE,
  next_earnings_time  VARCHAR(10),               -- 'BMO','AMC'
  analyst_rating      NUMERIC(3,2),              -- 1.0-5.0
  price_target_mean   NUMERIC(10,2),

  updated_at          TIMESTAMP DEFAULT NOW()
);
```

### Layer 3: Relational Data (Competitors, Institutions, Insiders)

```sql
-- Competitor graph (many-to-many, directional similarity scores)
CREATE TABLE company_competitors (
  ticker            VARCHAR(10) REFERENCES companies(ticker),
  competitor_ticker VARCHAR(10) REFERENCES companies(ticker),
  similarity_score  NUMERIC(4,3),                -- 0.000-1.000
  source            VARCHAR(50),                  -- 'embedding','manual','sec_peer'
  updated_at        TIMESTAMP DEFAULT NOW(),
  PRIMARY KEY (ticker, competitor_ticker),
  CHECK (ticker != competitor_ticker)
);

CREATE INDEX idx_competitors_score ON company_competitors(ticker, similarity_score DESC);

-- Institutional holders (from 13F filings, quarterly snapshots)
CREATE TABLE institutional_holders (
  id              BIGSERIAL PRIMARY KEY,
  ticker          VARCHAR(10) REFERENCES companies(ticker),
  institution_cik VARCHAR(10),
  institution_name VARCHAR(255),
  report_date     DATE NOT NULL,                 -- 13F reporting period
  shares_held     BIGINT,
  market_value    BIGINT,
  pct_of_portfolio NUMERIC(6,4),
  pct_of_company  NUMERIC(6,4),
  change_shares   BIGINT,                        -- QoQ change
  filing_date     DATE,
  UNIQUE (ticker, institution_cik, report_date)
);

CREATE INDEX idx_inst_ticker_date ON institutional_holders(ticker, report_date DESC);
CREATE INDEX idx_inst_by_value ON institutional_holders(ticker, report_date DESC, market_value DESC);

-- Insider transactions (from Form 4 filings, event-driven)
CREATE TABLE insider_transactions (
  id              BIGSERIAL PRIMARY KEY,
  ticker          VARCHAR(10) REFERENCES companies(ticker),
  insider_name    VARCHAR(255),
  insider_title   VARCHAR(100),                  -- 'CEO','CFO','Director'
  transaction_date DATE NOT NULL,
  transaction_type VARCHAR(20),                  -- 'BUY','SELL','OPTION_EXERCISE'
  shares          BIGINT,
  price_per_share NUMERIC(10,4),
  total_value     BIGINT,
  shares_owned_after BIGINT,
  filing_date     DATE,
  form_type       VARCHAR(10),                   -- 'Form 4','Form 5'
  sec_url         VARCHAR(500)
);

CREATE INDEX idx_insider_ticker_date ON insider_transactions(ticker, transaction_date DESC);
```

---

## 2. Caching Strategy

Three tiers with TTLs aligned to data volatility:

| Data                         | TTL     | Invalidation Trigger         |
|------------------------------|---------|------------------------------|
| Company master               | 24h     | Manual admin update          |
| Fundamentals (market_cap, PE)| 5 min   | Price tick webhook           |
| Latest financials            | 1h      | New 10-Q/10-K detected       |
| Competitors                  | 24h     | Embedding recompute job      |
| Top institutions             | 6h      | New 13F filing detected      |
| Recent insider txns          | 15 min  | New Form 4 detected          |

### Redis Key Structure

```
company:{ticker}:master             → full company row
company:{ticker}:fundamentals       → current market metrics
company:{ticker}:financials:latest  → most recent quarter
company:{ticker}:competitors:top10  → sorted set by similarity
company:{ticker}:institutions:top20 → sorted set by market_value
company:{ticker}:insiders:30d       → list of recent transactions
```

---

## 3. Code Structure

```
instnews/
├── models/                    # SQLAlchemy / Pydantic models
│   ├── company.py
│   ├── financials.py
│   ├── fundamentals.py
│   ├── competitors.py
│   ├── institutions.py
│   └── insiders.py
│
├── repositories/              # DB access layer (one per aggregate)
│   ├── base.py                # BaseRepository with cached_get pattern
│   ├── company_repo.py
│   ├── financials_repo.py
│   ├── competitors_repo.py
│   ├── institutions_repo.py
│   └── insiders_repo.py
│
├── services/                  # Business logic, orchestrates repos
│   └── company_service.py     # get_full_profile() aggregates all
│
├── cache/
│   ├── redis_client.py
│   └── cache_keys.py          # centralized key builders
│
├── ingestion/                 # Data pipelines (separate from reads)
│   ├── edgar_ingester.py      # 10-Q, 10-K, 13F, Form 4
│   ├── market_data_ingester.py # prices, market_cap
│   └── competitor_builder.py   # embedding-based peer detection
│
└── api/
    └── routes/
        └── company.py          # GET /company/{ticker}/profile
```

---

## 4. Key Patterns

### Repository with Cache-Aside

```python
class CompanyRepository(BaseRepository):
    async def get(self, ticker: str) -> Company | None:
        key = f"company:{ticker}:master"
        if cached := await self.redis.get(key):
            return Company.parse_raw(cached)

        row = await self.db.fetch_one(
            "SELECT * FROM companies WHERE ticker = $1", ticker
        )
        if row:
            company = Company(**row)
            await self.redis.setex(key, 86400, company.json())
            return company
        return None
```

### Service Layer Aggregates for the Full Profile Endpoint

```python
class CompanyService:
    async def get_full_profile(self, ticker: str) -> CompanyProfile:
        # Parallel fetches — all cache-aside
        company, fundamentals, financials, competitors, institutions, insiders = await asyncio.gather(
            self.company_repo.get(ticker),
            self.fundamentals_repo.get(ticker),
            self.financials_repo.get_latest(ticker),
            self.competitors_repo.get_top(ticker, n=10),
            self.institutions_repo.get_top(ticker, n=20),
            self.insiders_repo.get_recent(ticker, days=90),
        )
        return CompanyProfile(
            company=company,
            fundamentals=fundamentals,
            latest_financials=financials,
            competitors=competitors,
            top_institutions=institutions,
            recent_insiders=insiders,
        )
```

---

## 5. Why This Structure

1. **Separation by volatility** — stable data, seasonal data, and event-driven data live in different tables with different TTLs. No cache stampedes from over-aggressive invalidation.
2. **Append-only financials** — full history for backtesting AgenticTrader signals without destructive updates.
3. **Repository pattern** — each aggregate (company, competitors, insiders) has one owner. Easy to mock for tests, easy to swap Redis for another cache.
4. **Parallel fetching in service layer** — a full company profile is 6 parallel cache lookups (~2–5ms total on cache hit), degrades gracefully to DB on miss.
5. **Ingestion separated from reads** — EDGAR pollers, 13F parsers, and Form 4 webhooks write directly to Postgres and invalidate specific cache keys. Your read path never blocks on ingestion.

---

## 6. Open Design Decision

Whether the competitor graph is **computed** (from embeddings of company descriptions/sectors) or **sourced** (SEC peer filings, manual curation).

Given the ML background and scale needs, an embedding-based nightly batch job is more defensible and scales better than manual curation — but SEC peer filings can serve as a ground-truth signal for evaluation.