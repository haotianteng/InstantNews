# Architecture Overview

## System Architecture
```mermaid
graph TB
    subgraph Internet
        User([fa:fa-user User Browser])
    end

    subgraph AWS Cloud
        R53[fa:fa-globe Route 53<br/>instnews.net]
        ACM[fa:fa-lock ACM Certificate<br/>HTTPS / TLS]
        ALB[fa:fa-sitemap Application Load Balancer<br/>Health Checks · HTTP→HTTPS Redirect]

        subgraph ECS Cluster
            subgraph WebService [Web Service — Auto-scaled 2→10 tasks]
                direction TB
                NGINX[fa:fa-server Nginx :8000<br/>Static Files · Gzip · Proxy]
                GUNICORN[fa:fa-cog Gunicorn :8001<br/>Flask Application]
                NGINX --> GUNICORN
            end
            WORKER[fa:fa-refresh Feed Worker<br/>RSS Fetch · Sentiment · Dedup<br/>every 30s]
        end

        RDS[(fa:fa-database RDS PostgreSQL<br/>db.t3.micro<br/>news · users · subscriptions)]
        SECRETS[fa:fa-key Secrets Manager<br/>DB credentials · Firebase · Stripe]
        ECR[fa:fa-archive ECR Registry<br/>Docker Images]
        CW[fa:fa-chart-line CloudWatch<br/>Logs · Metrics · Alarms]
    end

    subgraph External Services
        FIREBASE[fa:fa-shield Firebase Auth<br/>Google OAuth]
        STRIPE[fa:fa-credit-card Stripe<br/>Payments · Webhooks]
        RSS[fa:fa-rss RSS Feeds<br/>15+ Financial Sources]
    end

    User --> R53
    R53 --> ACM
    ACM --> ALB
    ALB --> NGINX
    GUNICORN --> RDS
    GUNICORN --> FIREBASE
    GUNICORN --> STRIPE
    WORKER --> RDS
    WORKER --> RSS
    SECRETS -.-> GUNICORN
    SECRETS -.-> WORKER
    ECR -.-> WebService
    ECR -.-> WORKER
    GUNICORN --> CW
    WORKER --> CW

    style R53 fill:#1a73e8,color:#fff
    style ACM fill:#2e7d32,color:#fff
    style ALB fill:#e65100,color:#fff
    style NGINX fill:#009688,color:#fff
    style GUNICORN fill:#7b1fa2,color:#fff
    style WORKER fill:#c62828,color:#fff
    style RDS fill:#1565c0,color:#fff
    style SECRETS fill:#f57f17,color:#000
    style ECR fill:#00838f,color:#fff
    style CW fill:#4527a0,color:#fff
    style FIREBASE fill:#ff9800,color:#000
    style STRIPE fill:#6772e5,color:#fff
    style RSS fill:#388e3c,color:#fff
```

## Request Flow

```mermaid
sequenceDiagram
    participant B as Browser
    participant R as Route 53
    participant A as ALB
    participant N as Nginx
    participant G as Gunicorn / Flask
    participant DB as PostgreSQL

    B->>R: HTTPS www.instnews.net/api/news
    R->>A: Resolve to ALB
    A->>N: Forward to healthy task

    alt Static file (CSS, JS, HTML)
        N-->>B: Serve directly (cached)
    else API request
        N->>G: Proxy to :8001
        G->>G: Auth middleware<br/>Verify Firebase token<br/>Load user + tier
        G->>G: Tier gating<br/>Cap limits, filter fields
        G->>DB: SQL query
        DB-->>G: Result rows
        G-->>N: JSON response
        N-->>B: Response + gzip
    end
```

## Data Ingestion Pipeline

```mermaid
flowchart LR
    subgraph Sources [15+ RSS Feeds]
        CNBC[CNBC]
        REUTERS[Reuters]
        YAHOO[Yahoo Finance]
        MORE[...]
    end

    subgraph Worker [Feed Worker — every 30s]
        FETCH[Parallel Fetch<br/>15 threads]
        PARSE[Parse XML<br/>RSS 2.0 / Atom]
        SCORE[Sentiment Scoring<br/>50+ signal words]
        STORE[Store in DB<br/>INSERT OR IGNORE]
        DEDUP[Semantic Dedup<br/>all-MiniLM-L6-v2<br/>cosine similarity ≥ 0.85]
        CLEAN[Cleanup<br/>Delete old entries]
    end

    subgraph DB [PostgreSQL]
        NEWS[(news table)]
    end

    CNBC --> FETCH
    REUTERS --> FETCH
    YAHOO --> FETCH
    MORE --> FETCH
    FETCH --> PARSE --> SCORE --> STORE --> DEDUP --> CLEAN
    STORE --> NEWS
    DEDUP --> NEWS

    style FETCH fill:#1565c0,color:#fff
    style PARSE fill:#00838f,color:#fff
    style SCORE fill:#2e7d32,color:#fff
    style STORE fill:#6a1b9a,color:#fff
    style DEDUP fill:#e65100,color:#fff
    style CLEAN fill:#c62828,color:#fff
```

## Authentication Flow

```mermaid
sequenceDiagram
    participant B as Browser
    participant F as Firebase Auth
    participant G as Google OAuth
    participant S as SIGNAL Backend
    participant DB as PostgreSQL

    B->>F: signInWithPopup()
    F->>G: OAuth consent screen
    G-->>F: Google credentials
    F-->>B: Firebase ID token (JWT)

    B->>S: GET /api/news<br/>Authorization: Bearer <token>
    S->>F: verify_id_token(token)
    F-->>S: Decoded claims (uid, email, name)

    alt First login
        S->>DB: INSERT user (tier=free)
    else Returning user
        S->>DB: SELECT user by firebase_uid
    end

    S->>S: Set g.current_user<br/>Apply tier gating
    S-->>B: JSON response (filtered by tier)
```

## Payment Flow

```mermaid
sequenceDiagram
    participant B as Browser
    participant S as SIGNAL Backend
    participant ST as Stripe
    participant DB as PostgreSQL

    B->>S: POST /api/billing/checkout<br/>{tier: "plus"}
    S->>ST: Create Checkout Session
    ST-->>S: Session URL
    S-->>B: {url: "https://checkout.stripe.com/..."}

    B->>ST: Redirect — user enters payment
    ST-->>B: Redirect to /pricing?success=true

    Note over ST,S: Async webhook (seconds later)
    ST->>S: POST /api/billing/webhook<br/>checkout.session.completed
    S->>S: Verify signature
    S->>ST: Get subscription details
    S->>DB: Create Subscription record
    S->>DB: UPDATE user SET tier='plus'
    S-->>ST: 200 OK
```

## Auto-Scaling Behavior

```mermaid
graph LR
    subgraph Normal_Load [Normal Load]
        T1[Task 1]
        T2[Task 2]
    end

    subgraph Burst_Traffic [Burst Traffic]
        T3[Task 1]
        T4[Task 2]
        T5[Task 3]
        T6[Task 4]
        T7[...]
        T8[Task 10]
    end

    Normal_Load -->|CPU > 60% or<br/>500+ req/target| Burst_Traffic
    Burst_Traffic -->|CPU < 60% for 5min| Normal_Load

    style T1 fill:#2e7d32,color:#fff
    style T2 fill:#2e7d32,color:#fff
    style T3 fill:#2e7d32,color:#fff
    style T4 fill:#2e7d32,color:#fff
    style T5 fill:#e65100,color:#fff
    style T6 fill:#e65100,color:#fff
    style T7 fill:#e65100,color:#fff
    style T8 fill:#e65100,color:#fff
```

| Parameter | Value |
|-----------|-------|
| Min tasks | 2 |
| Max tasks | 10 |
| Scale-out trigger | CPU > 60% or > 500 req/target |
| Scale-out cooldown | 60 seconds |
| Scale-in cooldown | 300 seconds |
| Worker tasks | 1 (fixed, no scaling) |
