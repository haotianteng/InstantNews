"""AWS CDK stack for InstantNews (SIGNAL) production infrastructure.

Architecture:
    Public:  Route 53 -> Public ALB -> ECS Fargate (web) -> RDS PostgreSQL (primary)
    Private: VPN -> Private DNS -> Internal ALB -> ECS Fargate (admin) -> RDS (replica)
    Background: ECS Fargate (feed-worker) -> RDS PostgreSQL (primary)

Resources:
    - VPC with public/private subnets across 2 AZs
    - RDS PostgreSQL Multi-AZ primary + read replica
    - ECS Cluster: web service, admin service, feed worker
    - Public ALB (www.instnews.net) + Internal ALB (admin.instnews.net)
    - AWS Client VPN for private admin access
    - Route 53 public + private hosted zones
    - Secrets Manager, CloudWatch, auto-scaling
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
    aws_route53_targets as route53_targets,
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
            nat_gateways=1,
        )

        # ---------------------------------------------------------------
        # ECR Repository
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
            description="Application secrets (Stripe, Firebase, AI, etc.)",
        )

        # ---------------------------------------------------------------
        # RDS PostgreSQL — Primary (Multi-AZ)
        # ---------------------------------------------------------------
        db = rds.DatabaseInstance(
            self, "Database",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_16,
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T3, ec2.InstanceSize.SMALL,
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            database_name="signal_news",
            credentials=rds.Credentials.from_secret(db_secret),
            multi_az=True,
            allocated_storage=20,
            max_allocated_storage=100,
            backup_retention=Duration.days(7),
            deletion_protection=True,
            removal_policy=RemovalPolicy.SNAPSHOT,
        )

        # ---------------------------------------------------------------
        # RDS Read Replica — for admin panel and analytics
        # ---------------------------------------------------------------
        db_replica = rds.DatabaseInstanceReadReplica(
            self, "DatabaseReplica",
            source_database_instance=db,
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T3, ec2.InstanceSize.MICRO,
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            removal_policy=RemovalPolicy.DESTROY,
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
        # Route 53 — Public Zone + Certificate
        # ---------------------------------------------------------------
        hosted_zone = route53.HostedZone.from_lookup(
            self, "Zone",
            domain_name=domain_name,
        )

        # Existing web certificate — unchanged (do not add SANs, forces replacement)
        certificate = acm.Certificate(
            self, "Cert",
            domain_name=domain_name,
            subject_alternative_names=[f"www.{domain_name}"],
            validation=acm.CertificateValidation.from_dns(hosted_zone),
        )

        # Separate certificate for admin subdomain (internal ALB)
        admin_certificate = acm.Certificate(
            self, "AdminCert",
            domain_name=f"admin.{domain_name}",
            validation=acm.CertificateValidation.from_dns(hosted_zone),
        )

        # ---------------------------------------------------------------
        # Route 53 — Private Hosted Zone (admin.instnews.net)
        # ---------------------------------------------------------------
        private_zone = route53.PrivateHostedZone(
            self, "PrivateZone",
            zone_name=domain_name,
            vpc=vpc,
        )

        # ---------------------------------------------------------------
        # Shared env vars and secrets for ECS containers
        # ---------------------------------------------------------------
        shared_env = {
            "STALE_SECONDS": "30",
            "FETCH_TIMEOUT": "5",
            "DEDUP_THRESHOLD": "0.85",
            "BEDROCK_ENABLED": "true",
            "BEDROCK_REGION": "us-east-1",
            "MINIMAX_MODEL_ID": "MiniMax-M2.7",
            "DB_HOST": db.db_instance_endpoint_address,
            "DB_PORT": db.db_instance_endpoint_port,
            "DB_NAME": "signal_news",
            "DB_USER": "signal",
        }

        shared_secrets = {
            "DB_PASSWORD": ecs.Secret.from_secrets_manager(db_secret, field="password"),
            "FIREBASE_CREDENTIALS_JSON": ecs.Secret.from_secrets_manager(app_secrets, field="FIREBASE_CREDENTIALS_JSON"),
            "MINIMAX_API_KEY": ecs.Secret.from_secrets_manager(app_secrets, field="MINIMAX_API_KEY"),
            "MINIMAX_BASE_URL": ecs.Secret.from_secrets_manager(app_secrets, field="MINIMAX_BASE_URL"),
            "ANTHROPIC_API_KEY": ecs.Secret.from_secrets_manager(app_secrets, field="ANTHROPIC_API_KEY"),
            "POLYGON_API_KEY": ecs.Secret.from_secrets_manager(app_secrets, field="POLYGON_API_KEY"),
        }

        web_secrets = {
            **shared_secrets,
            "STRIPE_SECRET_KEY": ecs.Secret.from_secrets_manager(app_secrets, field="STRIPE_SECRET_KEY"),
            "STRIPE_WEBHOOK_SECRET": ecs.Secret.from_secrets_manager(app_secrets, field="STRIPE_WEBHOOK_SECRET"),
            "STRIPE_PUBLISHABLE_KEY": ecs.Secret.from_secrets_manager(app_secrets, field="STRIPE_PUBLISHABLE_KEY"),
            "STRIPE_PRICE_PLUS": ecs.Secret.from_secrets_manager(app_secrets, field="STRIPE_PRICE_PLUS"),
            "STRIPE_PRICE_MAX": ecs.Secret.from_secrets_manager(app_secrets, field="STRIPE_PRICE_MAX"),
            "WECHAT_APP_ID": ecs.Secret.from_secrets_manager(app_secrets, field="WECHAT_APP_ID"),
            "WECHAT_APP_SECRET": ecs.Secret.from_secrets_manager(app_secrets, field="WECHAT_APP_SECRET"),
            "APP_JWT_SECRET": ecs.Secret.from_secrets_manager(app_secrets, field="APP_JWT_SECRET"),
        }

        # ---------------------------------------------------------------
        # ECS Fargate — Web Service (Public ALB)
        # ---------------------------------------------------------------
        web_log_group = logs.LogGroup(
            self, "WebLogs",
            log_group_name="/ecs/instantnews-web",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )

        web_task = ecs.FargateTaskDefinition(
            self, "WebTask",
            cpu=512,
            memory_limit_mib=1024,
        )

        web_container = web_task.add_container(
            "web",
            image=ecs.ContainerImage.from_ecr_repository(repo, tag="latest"),
            logging=ecs.LogDrivers.aws_logs(stream_prefix="web", log_group=web_log_group),
            environment={
                **shared_env,
                "PORT": "8000",
                "GUNICORN_PORT": "8001",
                "WORKER_ENABLED": "false",
                "ADMIN_ENABLED": "false",
            },
            secrets=web_secrets,
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "curl -f http://localhost:8000/api/stats || exit 1"],
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                retries=3,
                start_period=Duration.seconds(60),
            ),
        )
        web_container.add_port_mappings(ecs.PortMapping(container_port=8000))

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

        web_service.target_group.configure_health_check(
            path="/api/stats",
            healthy_http_codes="200",
            interval=Duration.seconds(30),
            timeout=Duration.seconds(10),
        )

        db.connections.allow_from(web_service.service, ec2.Port.tcp(5432))

        # Auto-scaling
        scaling = web_service.service.auto_scale_task_count(min_capacity=2, max_capacity=10)
        scaling.scale_on_cpu_utilization("CpuScaling", target_utilization_percent=60,
            scale_in_cooldown=Duration.seconds(300), scale_out_cooldown=Duration.seconds(60))
        scaling.scale_on_request_count("RequestScaling", requests_per_target=500,
            target_group=web_service.target_group,
            scale_in_cooldown=Duration.seconds(300), scale_out_cooldown=Duration.seconds(60))

        # ---------------------------------------------------------------
        # ECS Fargate — Admin Service (Internal ALB, private subnet)
        # ---------------------------------------------------------------
        admin_log_group = logs.LogGroup(
            self, "AdminLogs",
            log_group_name="/ecs/instantnews-admin",
            retention=logs.RetentionDays.THREE_MONTHS,
            removal_policy=RemovalPolicy.DESTROY,
        )

        admin_task = ecs.FargateTaskDefinition(
            self, "AdminTask",
            cpu=256,
            memory_limit_mib=512,
        )

        admin_container = admin_task.add_container(
            "admin",
            image=ecs.ContainerImage.from_ecr_repository(repo, tag="latest"),
            logging=ecs.LogDrivers.aws_logs(stream_prefix="admin", log_group=admin_log_group),
            environment={
                **shared_env,
                "PORT": "8000",
                "GUNICORN_PORT": "8001",
                "WORKER_ENABLED": "false",
                "ADMIN_ENABLED": "true",
                "DB_REPLICA_HOST": db_replica.db_instance_endpoint_address,
            },
            secrets=web_secrets,
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "curl -f http://localhost:8000/api/stats || exit 1"],
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                retries=3,
                start_period=Duration.seconds(60),
            ),
        )
        admin_container.add_port_mappings(ecs.PortMapping(container_port=8000))

        admin_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "AdminService",
            cluster=cluster,
            task_definition=admin_task,
            desired_count=1,
            certificate=admin_certificate,
            public_load_balancer=False,  # Internal ALB
            health_check_grace_period=Duration.seconds(120),
        )

        admin_service.target_group.configure_health_check(
            path="/api/stats",
            healthy_http_codes="200",
            interval=Duration.seconds(30),
            timeout=Duration.seconds(10),
        )

        db.connections.allow_from(admin_service.service, ec2.Port.tcp(5432))
        db_replica.connections.allow_from(admin_service.service, ec2.Port.tcp(5432))

        # Private DNS: admin.instnews.net -> Internal ALB
        route53.ARecord(
            self, "AdminDns",
            zone=private_zone,
            record_name=f"admin.{domain_name}",
            target=route53.RecordTarget.from_alias(
                route53_targets.LoadBalancerTarget(admin_service.load_balancer)
            ),
        )

        # ---------------------------------------------------------------
        # ECS Fargate — Feed Worker (background, no ALB)
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
            memory_limit_mib=2048,
        )

        worker_task.add_container(
            "worker",
            image=ecs.ContainerImage.from_ecr_repository(repo, tag="latest"),
            command=["python", "-m", "app.worker"],
            logging=ecs.LogDrivers.aws_logs(stream_prefix="worker", log_group=worker_log_group),
            environment={
                **shared_env,
                "WORKER_INTERVAL_SECONDS": "30",
            },
            secrets=shared_secrets,
        )

        worker_service = ecs.FargateService(
            self, "WorkerService",
            cluster=cluster,
            task_definition=worker_task,
            desired_count=1,
        )

        db.connections.allow_from(worker_service, ec2.Port.tcp(5432))

        # ---------------------------------------------------------------
        # AWS Client VPN (for admin panel access)
        # ---------------------------------------------------------------
        # ---------------------------------------------------------------
        # AWS Client VPN — private access to admin panel
        # ---------------------------------------------------------------
        vpn_server_cert_arn = self.node.try_get_context("vpn_server_cert_arn") or ""
        vpn_client_cert_arn = self.node.try_get_context("vpn_client_cert_arn") or ""

        if vpn_server_cert_arn and vpn_client_cert_arn:
            vpn_endpoint = ec2.ClientVpnEndpoint(
                self, "VpnEndpoint",
                vpc=vpc,
                server_certificate_arn=vpn_server_cert_arn,
                client_certificate_arn=vpn_client_cert_arn,
                cidr="10.100.0.0/22",
                split_tunnel=True,
                dns_servers=["10.0.0.2"],  # VPC DNS resolves admin.instnews.net privately
                logging=True,
                log_group=logs.LogGroup(
                    self, "VpnLogs",
                    log_group_name="/vpn/instantnews-admin",
                    retention=logs.RetentionDays.THREE_MONTHS,
                    removal_policy=RemovalPolicy.DESTROY,
                ),
            )
            vpn_endpoint.add_authorization_rule(
                "Allow all VPN users",
                cidr="0.0.0.0/0",
            )
            # Allow inbound UDP 443 for VPN connections
            vpn_endpoint.connections.allow_from_any_ipv4(ec2.Port.udp(443))
            cdk.CfnOutput(self, "VpnEndpointId", value=vpn_endpoint.endpoint_id)

        # ---------------------------------------------------------------
        # Outputs
        # ---------------------------------------------------------------
        cdk.CfnOutput(self, "AlbDns", value=web_service.load_balancer.load_balancer_dns_name)
        cdk.CfnOutput(self, "AdminAlbDns", value=admin_service.load_balancer.load_balancer_dns_name)
        cdk.CfnOutput(self, "EcrRepoUri", value=repo.repository_uri)
        cdk.CfnOutput(self, "DbEndpoint", value=db.db_instance_endpoint_address)
        cdk.CfnOutput(self, "DbReplicaEndpoint", value=db_replica.db_instance_endpoint_address)
        cdk.CfnOutput(self, "DbSecretArn", value=db_secret.secret_arn)
        cdk.CfnOutput(self, "AppSecretsArn", value=app_secrets.secret_arn)
        cdk.CfnOutput(self, "WebUrl", value=f"https://www.{domain_name}")
        cdk.CfnOutput(self, "AdminUrl", value=f"https://admin.{domain_name} (VPN required)")

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
