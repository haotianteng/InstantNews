# InstNews Documentation

## For Developers

| Doc | Description |
|-----|-------------|
| [**Deployment Guide**](deployment.md) | CI/CD pipeline, Docker, ECR, ECS, secrets, troubleshooting |
| [**Database Migrations**](database-migrations.md) | Alembic usage, creating migrations, testing against PostgreSQL |
| [**Architecture**](architecture.md) | System design, file structure, data flow |

## Feature Implementation History

| Phase | Doc | Description |
|-------|-----|-------------|
| 1 | [Backend Restructure](phase-1-backend-restructure.md) | Monolith → modular Flask, SQLAlchemy migration |
| 2 | [Authentication](phase-2-authentication.md) | Firebase Auth, Google OAuth |
| 3a | [Tier Gating](phase-3a-tier-gating.md) | Feature flags per tier, middleware |
| 4a | [Stripe Integration](phase-4-stripe-integration.md) | Checkout, webhooks, subscription management |
| 4b | [Frontend + AI](phase-4-frontend-ai.md) | Vite build, account dashboard, AI sentiment, API keys |
| 5 | [AWS Deployment](phase-5-aws-deployment.md) | CDK stack, ECS Fargate, RDS, ALB |

## Planning

| Doc | Description |
|-----|-------------|
| [Future Features](future-features.md) | Roadmap with priorities |
