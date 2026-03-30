from aws_cdk import (
    Stack, Duration, RemovalPolicy, CfnOutput, CfnParameter,
    aws_ec2 as ec2, aws_rds as rds,
    aws_lambda as lambda_, aws_apigateway as apigw,
    aws_s3 as s3, aws_logs as logs,
    aws_events as events, aws_events_targets as targets,
    aws_iam as iam, aws_sns as sns, aws_sns_subscriptions as subs,
)
from constructs import Construct


class HannaStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- CfnParameters ---

        # WARNING: Default 0.0.0.0/0 is for development only. Override AllowedIps parameter with specific IPs before production.
        allowed_ips_param = CfnParameter(
            self, "AllowedIps",
            type="String",
            default="0.0.0.0/0",
            description=(
                "CIDR range for PostgreSQL ingress. Override with developer "
                "IPs before production (e.g., 1.2.3.4/32)."
            ),
        )

        alert_email_param = CfnParameter(
            self, "AlertEmail",
            type="String",
            default="alerts@hannacenter.org",
            description="Email address for billing alert notifications.",
        )

        # --- VPC ---
        vpc = ec2.Vpc(
            self, "HannaVpc",
            max_azs=2,
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                )
            ],
        )

        # --- Security Group ---
        db_sg = ec2.SecurityGroup(
            self, "DbSecurityGroup",
            vpc=vpc,
            description="Allow PostgreSQL access from AllowedIps parameter",
            allow_all_outbound=True,
        )
        db_sg.add_ingress_rule(
            ec2.Peer.ipv4(allowed_ips_param.value_as_string),
            ec2.Port.tcp(5432),
            "Allow PostgreSQL from AllowedIps (override at deploy time for production)",
        )

        # --- RDS Parameter Group (SSL enforcement) ---
        param_group = rds.ParameterGroup(
            self, "HannaDbParams",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_16_4,
            ),
            parameters={
                "rds.force_ssl": "1",
            },
        )

        # --- RDS PostgreSQL ---
        db = rds.DatabaseInstance(
            self, "HannaDb",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_16_4,
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE4_GRAVITON,
                ec2.InstanceSize.MICRO,
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PUBLIC,
            ),
            security_groups=[db_sg],
            publicly_accessible=True,
            database_name="hanna",
            credentials=rds.Credentials.from_generated_secret("hanna_admin"),
            parameter_group=param_group,
            removal_policy=RemovalPolicy.DESTROY,
            deletion_protection=False,
            allocated_storage=20,
            max_allocated_storage=20,
        )

        # TODO Phase 2: Enable Secrets Manager rotation once VPC endpoint or
        # rotation Lambda networking is resolved. Current design puts Lambda
        # outside the VPC (no NAT, saves $32/mo). The default rotation Lambda
        # created by add_rotation_single_user() needs network access to RDS,
        # which requires either: (a) VPC endpoint for Secrets Manager, or
        # (b) placing rotation Lambda in VPC with NAT. For Phase 1, manually
        # rotate the DB password every 90 days via AWS Console or CLI:
        #   aws secretsmanager rotate-secret --secret-id <DbSecretArn>
        # A CloudWatch dashboard reminder or calendar event is recommended.

        # --- S3 Bucket ---
        bucket = s3.Bucket(
            self, "HannaBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="ArchiveAndExpire",
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=Duration.days(90),
                        )
                    ],
                    expiration=Duration.days(365),
                )
            ],
        )

        # --- Lambda Execution Role (least-privilege) ---
        lambda_role = iam.Role(
            self, "HannaLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )
        # Secrets Manager: read DB credentials only
        db.secret.grant_read(lambda_role)
        # S3: read/write to Hanna bucket only
        bucket.grant_read_write(lambda_role)
        # Bedrock: invoke Titan Embed Text V2 only (scoped to model ARN)
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[
                    "arn:aws:bedrock:us-west-1::foundation-model/amazon.titan-embed-text-v2:0"
                ],
            )
        )

        # --- Lambda Placeholder ---
        placeholder_fn = lambda_.Function(
            self, "HannaPlaceholderFn",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="index.handler",
            code=lambda_.Code.from_inline(
                "def handler(event, context): return {'statusCode': 200, 'body': 'placeholder'}"
            ),
            timeout=Duration.seconds(30),
            memory_size=128,
            role=lambda_role,
        )

        # --- API Gateway Scaffold ---
        api = apigw.RestApi(
            self, "HannaGrantsApi",
            rest_api_name="HannaGrantsApi",
            api_key_source_type=apigw.ApiKeySourceType.HEADER,
        )
        health_resource = api.root.add_resource("health")
        health_resource.add_method(
            "GET",
            apigw.MockIntegration(
                integration_responses=[
                    apigw.IntegrationResponse(
                        status_code="200",
                        response_templates={
                            "application/json": '{"status": "ok"}',
                        },
                    )
                ],
                request_templates={
                    "application/json": '{"statusCode": 200}',
                },
            ),
            method_responses=[
                apigw.MethodResponse(status_code="200"),
            ],
        )

        # API Key + Usage Plan (rate limit: 10 req/sec burst 20, quota: 500/day)
        api_key = apigw.ApiKey(self, "HannaApiKey")
        usage_plan = apigw.UsagePlan(
            self, "HannaUsagePlan",
            throttle=apigw.ThrottleSettings(
                rate_limit=10,
                burst_limit=20,
            ),
            quota=apigw.QuotaSettings(
                limit=500,
                period=apigw.Period.DAY,
            ),
        )
        usage_plan.add_api_key(api_key)
        usage_plan.add_api_stage(stage=api.deployment_stage)

        # --- CloudWatch Log Group (14-day retention per cost plan) ---
        log_group = logs.LogGroup(  # noqa: F841
            self, "HannaLogGroup",
            retention=logs.RetentionDays.TWO_WEEKS,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # --- EventBridge Scaffolds (both disabled -- enabled in Phase 2/3) ---

        # Daily ingestion: 6am PT = 13:00 UTC (Phase 2 enables this)
        daily_rule = events.Rule(
            self, "HannaDailyIngestion",
            schedule=events.Schedule.cron(hour="13", minute="0"),
            enabled=False,
        )
        daily_rule.add_target(targets.LambdaFunction(placeholder_fn))

        # Weekly evaluation: Monday 7am PT = 14:00 UTC (Phase 3 enables this)
        weekly_rule = events.Rule(
            self, "HannaWeeklyEvaluation",
            schedule=events.Schedule.cron(week_day="MON", hour="14", minute="0"),
            enabled=False,
        )
        weekly_rule.add_target(targets.LambdaFunction(placeholder_fn))

        # --- SNS Topic for Billing Alerts ---
        billing_topic = sns.Topic(
            self, "HannaBillingAlerts",
            topic_name="hanna-billing-alerts",
        )
        billing_topic.add_subscription(
            subs.EmailSubscription(alert_email_param.value_as_string)
        )

        # NOTE: CloudWatch billing alarms MUST be created in us-east-1 (not us-west-1).
        # The AWS/Billing EstimatedCharges metric only exists in us-east-1.
        # After deploying this stack, manually create two alarms in us-east-1:
        #
        # 1. Warning alarm ($40/month):
        #    Namespace: AWS/Billing
        #    MetricName: EstimatedCharges
        #    Statistic: Maximum
        #    Period: 21600 (6 hours)
        #    Threshold: 40
        #    ComparisonOperator: GreaterThanOrEqualToThreshold
        #    Actions: SNS topic ARN from BillingAlertsSnsTopicArn output
        #            (or create a mirror SNS topic in us-east-1)
        #
        # 2. Critical alarm ($50/month):
        #    Same as above, threshold: 50
        #
        # AWS CLI example:
        #   aws cloudwatch put-metric-alarm --region us-east-1 \
        #     --alarm-name "hanna-billing-warning-40" \
        #     --namespace "AWS/Billing" \
        #     --metric-name "EstimatedCharges" \
        #     --statistic Maximum --period 21600 \
        #     --threshold 40 --comparison-operator GreaterThanOrEqualToThreshold \
        #     --evaluation-periods 1 --treat-missing-data missing \
        #     --alarm-actions <SNS_TOPIC_ARN_IN_US_EAST_1>

        # --- CfnOutputs ---
        CfnOutput(self, "DbEndpoint", value=db.db_instance_endpoint_address)
        CfnOutput(self, "DbSecretArn", value=db.secret.secret_arn)
        CfnOutput(self, "BucketName", value=bucket.bucket_name)
        CfnOutput(self, "ApiUrl", value=api.url)
        CfnOutput(self, "ApiKeyId", value=api_key.key_id)
        CfnOutput(self, "LambdaRoleArn", value=lambda_role.role_arn)
        CfnOutput(self, "BillingAlertsSnsTopicArn", value=billing_topic.topic_arn)
        CfnOutput(self, "AllowedIpsParam", value=allowed_ips_param.value_as_string)
