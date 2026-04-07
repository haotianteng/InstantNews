# Deployment Guide

## Quick Deploy (TL;DR)

```bash
# From project root
cd frontend && npx vite build && cd ..
docker build -f Dockerfile.prod -t instantnews:latest .
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 596080539716.dkr.ecr.us-east-1.amazonaws.com
docker tag instantnews:latest 596080539716.dkr.ecr.us-east-1.amazonaws.com/instantnews:latest
docker push 596080539716.dkr.ecr.us-east-1.amazonaws.com/instantnews:latest
aws ecs update-service --cluster instantnews --service InstantNewsStack-WebService5EA589E6-CfUW4VYKPEtz --desired-count 2 --force-new-deployment
aws ecs update-service --cluster instantnews --service InstantNewsStack-WorkerService99815FA9-b2XWHFz72OWl --desired-count 1 --force-new-deployment
```

---

## CI/CD Pipeline (Step by Step)

### Step 1: Build Frontend

```bash
cd frontend
npx vite build
cd ..
```

This compiles `frontend/src/` → `static/` with hashed asset filenames for cache busting. **You must do this before building Docker** — the Docker image copies `static/` directly.

Verify: check `static/assets/` has fresh `.js` and `.css` files.

### Step 2: Build Docker Image

```bash
docker build -f Dockerfile.prod -t instantnews:latest .
```

The `Dockerfile.prod` creates a production image with:
- **Nginx** — serves static files (`/assets/*`), proxies everything else to Gunicorn
- **Gunicorn** — runs the Flask app on internal port 8001
- **Supervisor** — manages both processes
- **Entrypoint** — runs `alembic upgrade head` before starting (auto-migrates DB)

Verify: `docker run --rm instantnews:latest cat /app/static/index.html | head -5`

### Step 3: Push to ECR

```bash
# Login (valid for 12 hours)
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 596080539716.dkr.ecr.us-east-1.amazonaws.com

# Tag and push
docker tag instantnews:latest 596080539716.dkr.ecr.us-east-1.amazonaws.com/instantnews:latest
docker push 596080539716.dkr.ecr.us-east-1.amazonaws.com/instantnews:latest
```

### Step 4: Deploy to ECS

```bash
# Web service (serves frontend + API)
aws ecs update-service --cluster instantnews \
  --service InstantNewsStack-WebService5EA589E6-CfUW4VYKPEtz \
  --desired-count 2 --force-new-deployment

# Worker service (feed refresh + AI analysis)
aws ecs update-service --cluster instantnews \
  --service InstantNewsStack-WorkerService99815FA9-b2XWHFz72OWl \
  --desired-count 1 --force-new-deployment
```

ECS performs a **rolling deployment**: starts new tasks with the new image, waits for health checks, then drains old tasks. Takes ~2-3 minutes.

### Step 5: Verify

```bash
# Check deployment status
aws ecs describe-services --cluster instantnews \
  --services InstantNewsStack-WebService5EA589E6-CfUW4VYKPEtz \
  --query 'services[0].deployments[*].{status:status,running:runningCount,pending:pendingCount}' \
  --output table

# Test endpoints
curl -s https://www.instnews.net/api/stats | python3 -c "import sys,json;print(json.loads(sys.stdin.read()))"
curl -s https://www.instnews.net/api/news?limit=1 | python3 -c "import sys,json;d=json.loads(sys.stdin.read());print('OK:', d['count'], 'items')"
curl -s https://www.instnews.net/api/pricing | python3 -c "import sys,json;d=json.loads(sys.stdin.read());print('Tiers:', [t['key'] for t in d['tiers']])"

# Check logs for errors
aws logs filter-log-events --log-group-name /ecs/instantnews-web \
  --start-time $(python3 -c "import time; print(int((time.time()-300)*1000))") \
  --filter-pattern "ERROR" --limit 5 \
  --query 'events[*].message' --output text
```

---

## When to Deploy What

| Change | What to rebuild | What to deploy |
|--------|----------------|----------------|
| Frontend only (HTML/CSS/JS) | `vite build` + Docker | Web service |
| Backend only (Python) | Docker | Web + Worker |
| DB schema change | Docker (includes migration) | Web + Worker |
| Infrastructure (CDK stack) | `cd infra && cdk deploy` | Automatic |
| Secrets (API keys, etc.) | Update Secrets Manager | Web + Worker (force redeploy) |
| Tier/pricing changes | Just edit `tiers.py` | Docker → Web + Worker |

---

## Infrastructure Changes (CDK)

Only needed when changing ECS config, adding new secrets/env vars, modifying RDS, ALB, etc.

```bash
cd infra
cdk diff          # preview changes
cdk deploy        # apply changes
```

CDK updates task definitions automatically. You still need to push a new Docker image and force a redeployment for the tasks to pick up the new config.

---

## Secrets Management

Secrets are stored in **AWS Secrets Manager** (`instantnews/app`):

```bash
# View current secrets (keys only)
aws secretsmanager get-secret-value --secret-id instantnews/app \
  --query SecretString --output text | python3 -c "import sys,json;print(list(json.loads(sys.stdin.read()).keys()))"

# Update a secret
python3 -c "
import json, subprocess
result = subprocess.run(['aws', 'secretsmanager', 'get-secret-value', '--secret-id', 'instantnews/app', '--query', 'SecretString', '--output', 'text'], capture_output=True, text=True)
secrets = json.loads(result.stdout.strip())
secrets['NEW_KEY'] = 'new_value'
subprocess.run(['aws', 'secretsmanager', 'put-secret-value', '--secret-id', 'instantnews/app', '--secret-string', json.dumps(secrets)])
"
```

After updating secrets, the CDK stack must reference them (`infra/stack.py` → `secrets={...}`) and you need `cdk deploy` + ECS redeployment.

Current secrets:
- `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PUBLISHABLE_KEY`
- `STRIPE_PRICE_PLUS`, `STRIPE_PRICE_MAX`
- `FIREBASE_CREDENTIALS_JSON`
- `MINIMAX_API_KEY`, `MINIMAX_BASE_URL`, `ANTHROPIC_API_KEY`

---

## Database Migrations

See [database-migrations.md](database-migrations.md) for full details.

Key points:
- Migrations run **automatically** on container start via `deploy/entrypoint.sh`
- RDS is in a private subnet — can't run migrations from local machine
- Always test migrations against PostgreSQL locally before deploying:

```bash
docker run --rm -d --name test_pg -e POSTGRES_PASSWORD=test -e POSTGRES_DB=testdb -p 5433:5432 postgres:15-alpine
sleep 3
DATABASE_URL=postgresql://postgres:test@localhost:5433/testdb alembic upgrade head
DATABASE_URL=postgresql://postgres:test@localhost:5433/testdb alembic downgrade -1
DATABASE_URL=postgresql://postgres:test@localhost:5433/testdb alembic upgrade head
docker stop test_pg
```

---

## Troubleshooting

### Deployment stuck (tasks not starting)
```bash
# Check for failed tasks
aws ecs describe-services --cluster instantnews \
  --services InstantNewsStack-WebService5EA589E6-CfUW4VYKPEtz \
  --query 'services[0].deployments' --output json

# Check stopped task reason
TASK=$(aws ecs list-tasks --cluster instantnews --desired-status STOPPED --query 'taskArns[0]' --output text)
aws ecs describe-tasks --cluster instantnews --tasks $TASK --query 'tasks[0].stoppedReason' --output text
```

### API returning 500
```bash
aws logs filter-log-events --log-group-name /ecs/instantnews-web \
  --start-time $(python3 -c "import time; print(int((time.time()-300)*1000))") \
  --filter-pattern "ERROR" --limit 5 \
  --query 'events[*].message' --output text
```

### Migration failed
If alembic fails, the entrypoint falls back to raw SQL. Check logs for "WARNING: Migration failed". The app will start with whatever schema exists. Fix the migration and redeploy.

### Stale frontend (browser cache)
The Vite build uses content-hashed filenames (`auth-VueSn6OU.js`). New deploys get new hashes, so browsers fetch fresh files. If users report stale content, they need to hard refresh (Ctrl+Shift+R).

### Services scaled to 0
Auto-scaling may scale down to 0 during low traffic. Force desired count:
```bash
aws ecs update-service --cluster instantnews \
  --service InstantNewsStack-WebService5EA589E6-CfUW4VYKPEtz \
  --desired-count 2
```

---

## Admin Panel Access

The admin panel runs on an **internal ALB** (`admin.instnews.net`) — only accessible via VPN.

| Resource | Value |
|----------|-------|
| Admin ALB | `internal-Instan-Admin-rD6sd8lmrnm1-1823759022.us-east-1.elb.amazonaws.com` |
| Admin Service | `InstantNewsStack-AdminServiceFA17513E-3NiDDdFVAuMK` |
| Read Replica | `instantnewsstack-databasereplicafd06ab0d-ozqlltiqidin.cfzsdjjkx5ri.us-east-1.rds.amazonaws.com` |
| Admin Logs | `/ecs/instantnews-admin` (CloudWatch, 3-month retention) |

### Seed first superadmin (one-time)

```bash
python scripts/seed_admin.py your@email.com
```

On production, run via ECS task override:
```bash
aws ecs run-task \
  --cluster instantnews \
  --task-definition $(aws ecs describe-services --cluster instantnews --services InstantNewsStack-WebService5EA589E6-CfUW4VYKPEtz --query 'services[0].taskDefinition' --output text) \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-0169a5616c8ee7340],securityGroups=[sg-0423fa62afd7e0c24],assignPublicIp=DISABLED}" \
  --overrides '{"containerOverrides":[{"name":"web","entryPoint":["python","scripts/seed_admin.py","your@email.com"]}]}'
```

### VPN Setup (required for admin access)

1. Generate certs: `./scripts/generate-vpn-certs.sh`
2. Upload to ACM: follow output instructions
3. Add ARNs to `infra/cdk.json` context
4. Uncomment VPN section in `infra/stack.py`
5. `cdk deploy`

## Environment Reference

| Component | Value |
|-----------|-------|
| AWS Region | us-east-1 |
| AWS Account | 596080539716 |
| ECR Repo | 596080539716.dkr.ecr.us-east-1.amazonaws.com/instantnews |
| ECS Cluster | instantnews |
| Web Service | InstantNewsStack-WebService5EA589E6-CfUW4VYKPEtz |
| Admin Service | InstantNewsStack-AdminServiceFA17513E-3NiDDdFVAuMK |
| Worker Service | InstantNewsStack-WorkerService99815FA9-b2XWHFz72OWl |
| RDS Endpoint | instantnewsstack-databaseb269d8bb-*.rds.amazonaws.com |
| Domain | www.instnews.net |
| Secrets | instantnews/app (Secrets Manager) |
| DB Secrets | instantnews/db (Secrets Manager) |
| Web Logs | /ecs/instantnews-web (CloudWatch) |
| Worker Logs | /ecs/instantnews-worker (CloudWatch) |
| Admin Logs | /ecs/instantnews-admin (CloudWatch, 3 months) |
| RDB Primary | instantnewsstack-databaseb269d8bb-e2qnabn1vzdu... |
| RDS Replica | instantnewsstack-databasereplicafd06ab0d-ozqlltiqidin... |
