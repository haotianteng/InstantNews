#!/bin/bash
# Deploy InstantNews to production
# Usage: ./scripts/deploy.sh [web|worker|all]
#
# Examples:
#   ./scripts/deploy.sh          # deploy all (default)
#   ./scripts/deploy.sh web      # deploy web service only
#   ./scripts/deploy.sh worker   # deploy worker service only

set -e

REGION="us-east-1"
ACCOUNT="596080539716"
ECR_REPO="$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/instantnews"
CLUSTER="instantnews"
WEB_SERVICE="InstantNewsStack-WebService5EA589E6-CfUW4VYKPEtz"
WORKER_SERVICE="InstantNewsStack-WorkerService99815FA9-b2XWHFz72OWl"

TARGET="${1:-all}"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== InstantNews Deploy ($TARGET) ==="
echo ""

# Step 1: Build frontend
echo "[1/5] Building frontend..."
cd "$PROJECT_ROOT/frontend"
npx vite build 2>&1 | tail -3
echo "  ✓ Frontend built"

# Step 2: Build Docker image
echo "[2/5] Building Docker image..."
cd "$PROJECT_ROOT"
docker build -f Dockerfile.prod -t instantnews:latest . 2>&1 | tail -3
echo "  ✓ Docker image built"

# Step 3: Push to ECR
echo "[3/5] Pushing to ECR..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_REPO 2>/dev/null
docker tag instantnews:latest "$ECR_REPO:latest"
docker push "$ECR_REPO:latest" 2>&1 | tail -3
echo "  ✓ Image pushed"

# Step 4: Deploy to ECS
echo "[4/5] Deploying to ECS..."
if [ "$TARGET" = "web" ] || [ "$TARGET" = "all" ]; then
  aws ecs update-service --cluster $CLUSTER --service $WEB_SERVICE \
    --desired-count 2 --force-new-deployment --output text --query 'service.deployments[0].status' > /dev/null
  echo "  ✓ Web service deploying"
fi
if [ "$TARGET" = "worker" ] || [ "$TARGET" = "all" ]; then
  aws ecs update-service --cluster $CLUSTER --service $WORKER_SERVICE \
    --desired-count 1 --force-new-deployment --output text --query 'service.deployments[0].status' > /dev/null
  echo "  ✓ Worker service deploying"
fi

# Step 5: Wait and verify
echo "[5/5] Waiting for deployment..."
sleep 90

DEPLOYMENTS=$(aws ecs describe-services --cluster $CLUSTER --services $WEB_SERVICE \
  --query 'services[0].deployments | length(@)' --output text 2>/dev/null)
if [ "$DEPLOYMENTS" = "1" ]; then
  echo "  ✓ Deployment complete"
else
  echo "  ⏳ Deployment in progress ($DEPLOYMENTS active deployments)"
  echo "  Run: aws ecs describe-services --cluster $CLUSTER --services $WEB_SERVICE --query 'services[0].deployments[*].{status:status,running:runningCount}' --output table"
fi

# Quick smoke test
echo ""
echo "=== Smoke Test ==="
STATUS=$(curl -so /dev/null -w "%{http_code}" https://www.instnews.net/ 2>/dev/null)
echo "  Landing page: $STATUS"
STATUS=$(curl -so /dev/null -w "%{http_code}" https://www.instnews.net/api/stats 2>/dev/null)
echo "  API stats:    $STATUS"
NEWS=$(curl -s https://www.instnews.net/api/news?limit=1 2>/dev/null | python3 -c "import sys,json;d=json.loads(sys.stdin.read());print(d.get('count','error'))" 2>/dev/null)
echo "  API news:     $NEWS items"

echo ""
echo "=== Done ==="
echo "Site: https://www.instnews.net"
