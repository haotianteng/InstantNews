#!/bin/bash
#
# Deploy InstantNews to AWS ECS
#
# Usage:
#   ./deploy.sh              # Build, push, and deploy
#   ./deploy.sh --skip-tests # Skip tests (faster, use with caution)
#   ./deploy.sh --web-only   # Only redeploy web service
#   ./deploy.sh --worker-only # Only redeploy worker service
#
# Prerequisites:
#   - AWS CLI configured (aws configure) or running on a machine with IAM role
#   - Docker installed and running
#
set -euo pipefail

# ── Config ──────────────────────────────────────────────────────────
REGION="${AWS_REGION:-us-east-1}"
ECR_REPO="instantnews"
ECS_CLUSTER="instantnews"
WEB_SERVICE="InstantNewsStack-WebService"
WORKER_SERVICE="InstantNewsStack-WorkerService"

# ── Parse args ──────────────────────────────────────────────────────
SKIP_TESTS=false
WEB_ONLY=false
WORKER_ONLY=false

for arg in "$@"; do
  case $arg in
    --skip-tests)  SKIP_TESTS=true ;;
    --web-only)    WEB_ONLY=true ;;
    --worker-only) WORKER_ONLY=true ;;
    *)             echo "Unknown arg: $arg"; exit 1 ;;
  esac
done

# ── Resolve AWS account ────────────────────────────────────────────
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO"
IMAGE_TAG=$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)

echo "╔══════════════════════════════════════════╗"
echo "║  SIGNAL Deploy                           ║"
echo "╠══════════════════════════════════════════╣"
echo "║  Account:  $ACCOUNT_ID"
echo "║  Region:   $REGION"
echo "║  Image:    $ECR_REPO:$IMAGE_TAG"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── Step 1: Run tests ──────────────────────────────────────────────
if [ "$SKIP_TESTS" = false ]; then
  echo "▸ Running tests..."
  python -m pytest tests/ -v --tb=short
  echo "✓ Tests passed"
  echo ""
else
  echo "▸ Skipping tests (--skip-tests)"
  echo ""
fi

# ── Step 2: Login to ECR ───────────────────────────────────────────
echo "▸ Logging in to ECR..."
aws ecr get-login-password --region "$REGION" | \
  docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"
echo "✓ ECR login successful"
echo ""

# ── Step 3: Build Docker image ─────────────────────────────────────
echo "▸ Building Docker image..."
docker build -f Dockerfile.prod -t "$ECR_URI:$IMAGE_TAG" -t "$ECR_URI:latest" .
echo "✓ Image built: $ECR_URI:$IMAGE_TAG"
echo ""

# ── Step 4: Push to ECR ────────────────────────────────────────────
echo "▸ Pushing to ECR..."
docker push "$ECR_URI:$IMAGE_TAG"
docker push "$ECR_URI:latest"
echo "✓ Image pushed"
echo ""

# ── Step 5: Deploy to ECS ──────────────────────────────────────────
if [ "$WORKER_ONLY" = false ]; then
  echo "▸ Deploying web service..."
  aws ecs update-service \
    --cluster "$ECS_CLUSTER" \
    --service "$WEB_SERVICE" \
    --force-new-deployment \
    --region "$REGION" \
    --no-cli-pager > /dev/null
  echo "✓ Web service deployment triggered"
fi

if [ "$WEB_ONLY" = false ]; then
  echo "▸ Deploying worker service..."
  aws ecs update-service \
    --cluster "$ECS_CLUSTER" \
    --service "$WORKER_SERVICE" \
    --force-new-deployment \
    --region "$REGION" \
    --no-cli-pager > /dev/null
  echo "✓ Worker service deployment triggered"
fi
echo ""

# ── Step 6: Wait for stability ─────────────────────────────────────
if [ "$WORKER_ONLY" = false ]; then
  echo "▸ Waiting for web service to stabilize (this takes 2-3 minutes)..."
  aws ecs wait services-stable \
    --cluster "$ECS_CLUSTER" \
    --services "$WEB_SERVICE" \
    --region "$REGION"
  echo "✓ Web service stable"
fi
echo ""

echo "╔══════════════════════════════════════════╗"
echo "║  Deploy complete!                        ║"
echo "║  https://www.instnews.net                ║"
echo "╚══════════════════════════════════════════╝"
