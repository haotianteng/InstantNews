"""AWS CDK stack for InstantNews (SIGNAL) production infrastructure.

Architecture:
    Route 53 → ALB → ECS Fargate (web) → RDS PostgreSQL
                         ↑
                   ECS Fargate (feed-worker)

Resources created:
    - VPC with public/private subnets across 2 AZs
    - RDS PostgreSQL (db.t3.micro, single-AZ by default)
    - ECS Cluster with Fargate web service + feed worker
    - Application Load Balancer with HTTPS (ACM certificate)
    - ECR repository for Docker images
    - Secrets Manager for credentials
    - Auto-scaling (2-10 tasks, 60% CPU target)
    - Route 53 hosted zone + A record
    - CloudWatch log groups
"""

from constructs import Construct
import aws_cdk as cdk
from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_ecr as ecr,
    aws_rds as rds,
    aws_secretsmanager as secretsmanager,
    aws_route53 as route53,
    aws_certificatemanager as acm,
    aws_logs as logs,
    aws_elasticloadbalancingv2 as elbv2,
)


class InstantNewsStack(Stack):

    def __init__(self, scope: Construct, id: str, domain_name: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # ---------------------------------------------------------------
        # VPC
        # ---------------------------------------------------------------
        vpc = ec2.Vpc(
            self, "Vpc",
            max_azs=2,
            nat_gateways=1,  # keep costs low; increase for HA
        )

        # ---------------------------------------------------------------
        # ECR Repository (use existing or create new)
        # ---------------------------------------------------------------
        repo = self._get_or_create_ecr_repo()

        # ---------------------------------------------------------------
        # Secrets Manager
        # ---------------------------------------------------------------
        db_secret = secretsmanager.Secret(
            self, "DbSecret",
            secret_name="instantnews/db",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"username":"signal"}',
                generate_string_key="password",
                exclude_punctuation=True,
                password_length=32,
            ),
        )

        app_secrets = secretsmanager.Secret(
            self, "AppSecrets",
            secret_name="instantnews/app",
            description="Application secrets (Stripe, Firebase, etc.)",
            # Populated manually after stack creation
        )

        # ---------------------------------------------------------------
        # RDS PostgreSQL
        # ---------------------------------------------------------------
        db = rds.DatabaseInstance(
            self, "Database",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_16,
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T3, ec2.InstanceSize.MICRO
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            database_name="signal_news",
            credentials=rds.Credentials.from_secret(db_secret),
            multi_az=False,  # single-AZ to save costs; enable for prod HA
            allocated_storage=20,
            max_allocated_storage=100,
            backup_retention=Duration.days(7),
            deletion_protection=False,  # set True for real production
            removal_policy=RemovalPolicy.SNAPSHOT,
        )

        # ---------------------------------------------------------------
        # ECS Cluster
        # ---------------------------------------------------------------
        cluster = ecs.Cluster(
            self, "Cluster",
            vpc=vpc,
            cluster_name="instantnews",
            container_insights_v2=ecs.ContainerInsights.ENABLED,
        )

        # ---------------------------------------------------------------
        # Route 53 + ACM Certificate
        # ---------------------------------------------------------------
        # Import existing hosted zone (must be created manually or via registrar)
        hosted_zone = route53.HostedZone.from_lookup(
            self, "Zone",
            domain_name=domain_name,
        )

        certificate = acm.Certificate(
            self, "Cert",
            domain_name=domain_name,
            subject_alternative_names=[f"www.{domain_name}"],
            validation=acm.CertificateValidation.from_dns(hosted_zone),
        )

        # ---------------------------------------------------------------
        # ECS Fargate — Web Service (with ALB)
        # ---------------------------------------------------------------
        web_log_group = logs.LogGroup(
            self, "WebLogs",
            log_group_name="/ecs/instantnews-web",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )

        web_task = ecs.FargateTaskDefinition(
            self, "WebTask",
            cpu=512,      # 0.5 vCPU
            memory_limit_mib=1024,  # 1 GB
        )

        web_container = web_task.add_container(
            "web",
            image=ecs.ContainerImage.from_ecr_repository(repo, tag="latest"),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="web",
                log_group=web_log_group,
            ),
            environment={
                "PORT": "8000",
                "GUNICORN_PORT": "8001",
                "STALE_SECONDS": "30",
                "FETCH_TIMEOUT": "5",
                "WORKER_ENABLED": "false",  # separate worker container handles this
                "DEDUP_THRESHOLD": "0.85",
                "DB_HOST": db.db_instance_endpoint_address,
                "DB_PORT": db.db_instance_endpoint_port,
                "DB_NAME": "signal_news",
                "DB_USER": "signal",
            },
            secrets={
                "DB_PASSWORD": ecs.Secret.from_secrets_manager(db_secret, field="password"),
                "STRIPE_SECRET_KEY": ecs.Secret.from_secrets_manager(app_secrets, field="STRIPE_SECRET_KEY"),
                "STRIPE_WEBHOOK_SECRET": ecs.Secret.from_secrets_manager(app_secrets, field="STRIPE_WEBHOOK_SECRET"),
                "STRIPE_PRICE_PLUS": ecs.Secret.from_secrets_manager(app_secrets, field="STRIPE_PRICE_PLUS"),
                "STRIPE_PRICE_MAX": ecs.Secret.from_secrets_manager(app_secrets, field="STRIPE_PRICE_MAX"),
            },
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "curl -f http://localhost:8000/api/stats || exit 1"],
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                retries=3,
                start_period=Duration.seconds(60),
            ),
        )

        web_container.add_port_mappings(
            ecs.PortMapping(container_port=8000)
        )

        web_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "WebService",
            cluster=cluster,
            task_definition=web_task,
            desired_count=2,
            certificate=certificate,
            domain_name=f"www.{domain_name}",
            domain_zone=hosted_zone,
            redirect_http=True,
            public_load_balancer=True,
            health_check_grace_period=Duration.seconds(120),
        )

        # Health check on ALB target group
        web_service.target_group.configure_health_check(
            path="/api/stats",
            healthy_http_codes="200",
            interval=Duration.seconds(30),
            timeout=Duration.seconds(10),
        )

        # Allow web service to access RDS
        db.connections.allow_from(
            web_service.service,
            ec2.Port.tcp(5432),
            "Web service to RDS",
        )

        # Auto-scaling
        scaling = web_service.service.auto_scale_task_count(
            min_capacity=2,
            max_capacity=10,
        )
        scaling.scale_on_cpu_utilization(
            "CpuScaling",
            target_utilization_percent=60,
            scale_in_cooldown=Duration.seconds(300),
            scale_out_cooldown=Duration.seconds(60),
        )
        scaling.scale_on_request_count(
            "RequestScaling",
            requests_per_target=500,
            target_group=web_service.target_group,
            scale_in_cooldown=Duration.seconds(300),
            scale_out_cooldown=Duration.seconds(60),
        )

        # ---------------------------------------------------------------
        # ECS Fargate — Feed Worker (no ALB, just background task)
        # ---------------------------------------------------------------
        worker_log_group = logs.LogGroup(
            self, "WorkerLogs",
            log_group_name="/ecs/instantnews-worker",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )

        worker_task = ecs.FargateTaskDefinition(
            self, "WorkerTask",
            cpu=512,
            memory_limit_mib=2048,  # 2 GB — embedding model needs more memory
        )

        worker_task.add_container(
            "worker",
            image=ecs.ContainerImage.from_ecr_repository(repo, tag="latest"),
            command=["python", "-m", "app.worker"],
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="worker",
                log_group=worker_log_group,
            ),
            environment={
                "STALE_SECONDS": "30",
                "FETCH_TIMEOUT": "5",
                "WORKER_INTERVAL_SECONDS": "30",
                "DEDUP_THRESHOLD": "0.85",
                "DB_HOST": db.db_instance_endpoint_address,
                "DB_PORT": db.db_instance_endpoint_port,
                "DB_NAME": "signal_news",
                "DB_USER": "signal",
            },
            secrets={
                "DB_PASSWORD": ecs.Secret.from_secrets_manager(db_secret, field="password"),
            },
        )

        worker_service = ecs.FargateService(
            self, "WorkerService",
            cluster=cluster,
            task_definition=worker_task,
            desired_count=1,  # single worker is sufficient
        )

        # Allow worker to access RDS
        db.connections.allow_from(
            worker_service,
            ec2.Port.tcp(5432),
            "Worker to RDS",
        )

        # ---------------------------------------------------------------
        # Outputs
        # ---------------------------------------------------------------
        cdk.CfnOutput(self, "AlbDns", value=web_service.load_balancer.load_balancer_dns_name)
        cdk.CfnOutput(self, "EcrRepoUri", value=repo.repository_uri)
        cdk.CfnOutput(self, "DbEndpoint", value=db.db_instance_endpoint_address)
        cdk.CfnOutput(self, "DbSecretArn", value=db_secret.secret_arn)
        cdk.CfnOutput(self, "AppSecretsArn", value=app_secrets.secret_arn)
        cdk.CfnOutput(self, "WebUrl", value=f"https://www.{domain_name}")

    def _get_or_create_ecr_repo(self):
        """Use existing ECR repo if it exists, otherwise create one."""
        import boto3
        client = boto3.client("ecr", region_name=self.region)
        try:
            client.describe_repositories(repositoryNames=["instantnews"])
            return ecr.Repository.from_repository_name(self, "Repo", "instantnews")
        except client.exceptions.RepositoryNotFoundException:
            return ecr.Repository(
                self, "Repo",
                repository_name="instantnews",
                removal_policy=RemovalPolicy.RETAIN,
                lifecycle_rules=[
                    ecr.LifecycleRule(max_image_count=10, description="Keep last 10 images"),
                ],
            )
