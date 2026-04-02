# Deployment Guide

## Prerequisites

- AWS account with billing configured
- AWS CLI installed and configured (`aws configure`)
- AWS CDK installed (`npm install -g aws-cdk`)
- Docker installed and running
- Domain `instnews.net` registered

## Initial Deployment

### 1. Configure DNS

```bash
aws route53 create-hosted-zone --name instnews.net --caller-reference $(date +%s)
```

Update your domain registrar (GoDaddy, etc.) nameservers to the 4 NS records from the output.

### 2. Deploy Infrastructure

```bash
cd infra
pip install -r requirements.txt
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
cdk bootstrap aws://$ACCOUNT_ID/us-east-1
cdk deploy --context domain=instnews.net
```

Takes ~15-20 minutes. Save the outputs.

### 3. Push Docker Image

```bash
cd ..
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com
docker build -f Dockerfile.prod -t $ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/instantnews:latest .
docker push $ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/instantnews:latest
```

### 4. Configure Secrets

See [[Configuration Reference|Developer-Manual:-Configuration-Reference]] for all secrets.

### 5. Redeploy

```bash
aws ecs update-service --cluster instantnews --service InstantNewsStack-WebService --force-new-deployment
aws ecs update-service --cluster instantnews --service InstantNewsStack-WorkerService --force-new-deployment
```

## Subsequent Deployments

```bash
./deploy.sh                # Full: test → build → push → deploy
./deploy.sh --skip-tests   # Skip tests
./deploy.sh --web-only     # Web service only
./deploy.sh --worker-only  # Worker only
```

## Monitoring

```bash
# Live logs
aws logs tail /ecs/instantnews-web --follow
aws logs tail /ecs/instantnews-worker --follow

# Service status
aws ecs describe-services --cluster instantnews --services InstantNewsStack-WebService \
  --query 'services[0].{status:status,running:runningCount,desired:desiredCount}'

# Health check
curl -s https://www.instnews.net/api/stats | python3 -m json.tool
```

## Rollback

```bash
# Find previous image tag
aws ecr describe-images --repository-name instantnews --query 'imageDetails | sort_by(@, &imagePushedAt) | [-5:].[imageTags[0], imagePushedAt]' --output table

# Deploy specific version
# Edit ECS task definition to use the older tag, then force redeploy
```

## Tear Down

```bash
cd infra
cdk destroy
```

This removes all AWS resources. RDS takes a final snapshot before deletion.
