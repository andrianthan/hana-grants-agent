import json
import os

from aws_cdk import (
    Stack, Duration, RemovalPolicy, CfnOutput, CfnParameter,
    aws_ec2 as ec2, aws_rds as rds,
    aws_lambda as lambda_, aws_apigateway as apigw,
    aws_s3 as s3, aws_logs as logs,
    aws_events as events, aws_events_targets as targets,
    aws_iam as iam, aws_sns as sns, aws_sns_subscriptions as subs,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as sfn_tasks,
    aws_ecr_assets as ecr_assets,
    aws_cloudwatch as cw,
    aws_cloudwatch_actions as cw_actions,
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
                version=rds.PostgresEngineVersion.VER_16_12,
            ),
            parameters={
                "rds.force_ssl": "1",
            },
        )

        # --- RDS PostgreSQL ---
        db = rds.DatabaseInstance(
            self, "HannaDb",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_16_12,
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
                    "arn:aws:bedrock:us-west-2::foundation-model/amazon.titan-embed-text-v2:0"
                ],
            )
        )

        # --- Scraper Docker Lambda (INFRA-04, D-09) ---
        scraper_fn = lambda_.DockerImageFunction(
            self, "HannaScraperFn",
            code=lambda_.DockerImageCode.from_image_asset(
                directory=os.path.join(os.path.dirname(__file__), "..", ".."),  # repo root
                file="infrastructure/docker/scraper/Dockerfile",
                platform=ecr_assets.Platform.LINUX_AMD64,
                exclude=[
                    "infrastructure/cdk.out", ".venv", ".git", ".planning",
                    "org-materials", "__pycache__", "*.pyc", ".context",
                ],
            ),
            memory_size=2048,
            timeout=Duration.minutes(10),
            role=lambda_role,
            environment={
                "DB_SECRET_ARN": db.secret.secret_arn,
                "S3_BUCKET": bucket.bucket_name,
                "AWS_REGION_NAME": "us-west-2",
                "OPENROUTER_API_KEY": "",  # Set via Lambda console or SSM
                "OPENAI_BASE_URL": "https://openrouter.ai/api/v1",
                "EXTRACTION_MODEL": "openai/gpt-5.4-mini",
            },
            architecture=lambda_.Architecture.X86_64,
        )

        # --- Processing Lambda (zip package, lightweight utility per INFRA-04) ---
        processing_fn = lambda_.Function(
            self, "HannaProcessingFn",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="processing_handler.handler",
            code=lambda_.Code.from_asset(
                os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "scrapers", "processing"),
            ),
            memory_size=512,
            timeout=Duration.minutes(5),
            role=lambda_role,
            environment={
                "DB_SECRET_ARN": db.secret.secret_arn,
                "S3_BUCKET": bucket.bucket_name,
                "AWS_REGION_NAME": "us-west-2",
                "OPENROUTER_API_KEY": "",
                "OPENAI_BASE_URL": "https://openrouter.ai/api/v1",
                "EXTRACTION_MODEL": "openai/gpt-5.4-mini",
            },
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

        # --- Step Functions Pipeline (INGEST-06, D-11, PIPE-01) ---

        # Load scraper_registry.json at CDK synth time for EventBridge input
        registry_path = os.path.join(os.path.dirname(__file__), "..", "..", "scraper_registry.json")
        with open(registry_path) as f:
            scraper_registry = json.load(f)
        source_configs = [
            {"scraper_id": s["scraper_id"], "type": s["type"], "url": s["url"]}
            for s in scraper_registry["scraper_registry"]
        ]

        # Scrape task: invoke scraper Lambda per source
        scrape_task = sfn_tasks.LambdaInvoke(
            self, "ScrapeSingle",
            lambda_function=scraper_fn,
            payload=sfn.TaskInput.from_json_path_at("$"),
            result_path="$.scrapeResult",
            retry_on_service_exceptions=True,
        )
        scrape_task.add_retry(
            max_attempts=2,
            backoff_rate=2.0,
            interval=Duration.seconds(5),
            errors=["States.TaskFailed"],
        )
        scrape_task.add_catch(
            handler=sfn.Pass(self, "CatchScrapeError"),
            result_path="$.error",
        )

        # Process task: run dedup -> extract -> embed -> health for each batch
        process_task = sfn_tasks.LambdaInvoke(
            self, "ProcessBatch",
            lambda_function=processing_fn,
            payload=sfn.TaskInput.from_json_path_at("$.scrapeResult.Payload"),
            result_path="$.processResult",
        )

        # Chain: scrape -> process per source
        scrape_then_process = scrape_task.next(process_task)

        # DistributedMap: fan out to all sources with failure tolerance (D-11)
        map_state = sfn.DistributedMap(
            self, "ScrapeAllSources",
            max_concurrency=5,
            items_path="$.sources",
            result_path="$.results",
            tolerated_failure_percentage=30,
        )
        map_state.item_processor(scrape_then_process)

        # Log pipeline run after all sources processed
        log_run = sfn_tasks.LambdaInvoke(
            self, "LogPipelineRun",
            lambda_function=processing_fn,
            payload=sfn.TaskInput.from_object({
                "action": "log_pipeline_run",
                "results": sfn.JsonPath.string_at("$.results"),
            }),
        )

        # Start -> DistributedMap -> Log
        definition = map_state.next(log_run)

        pipeline_sm = sfn.StateMachine(
            self, "HannaIngestionPipeline",
            definition_body=sfn.DefinitionBody.from_chainable(definition),
            state_machine_type=sfn.StateMachineType.STANDARD,
            timeout=Duration.minutes(30),
        )

        # Grant Step Functions permissions to invoke Lambdas
        scraper_fn.grant_invoke(pipeline_sm.role)
        processing_fn.grant_invoke(pipeline_sm.role)

        # --- EventBridge Rules ---

        # Daily ingestion: 6am PT = 13:00 UTC — NOW ENABLED for Phase 2
        daily_rule = events.Rule(
            self, "HannaDailyIngestion",
            schedule=events.Schedule.cron(hour="13", minute="0"),
            enabled=True,
        )
        daily_rule.add_target(targets.SfnStateMachine(
            pipeline_sm,
            input=events.RuleTargetInput.from_object({
                "sources": source_configs,
            }),
        ))

        # Weekly evaluation: Monday 7am PT = 14:00 UTC (Phase 3 enables this)
        weekly_rule = events.Rule(
            self, "HannaWeeklyEvaluation",
            schedule=events.Schedule.cron(week_day="MON", hour="14", minute="0"),
            enabled=False,
        )
        # Placeholder target until Phase 3 wires the evaluator
        weekly_rule.add_target(targets.SfnStateMachine(pipeline_sm))

        # --- SNS Topic for Billing Alerts ---
        billing_topic = sns.Topic(
            self, "HannaBillingAlerts",
            topic_name="hanna-billing-alerts",
        )
        billing_topic.add_subscription(
            subs.EmailSubscription(alert_email_param.value_as_string)
        )

        # --- CloudWatch Alarm for scraper health (INGEST-07, D-01) ---
        health_alarm = cw.Alarm(
            self, "ScraperHealthAlarm",
            metric=cw.Metric(
                namespace="HannaGrants",
                metric_name="ScraperConsecutiveZeros",
                statistic="Maximum",
                period=Duration.hours(24),
            ),
            threshold=3,
            evaluation_periods=1,
            alarm_description="A scraper has returned 0 grants for 3+ consecutive days",
        )
        health_alarm.add_alarm_action(cw_actions.SnsAction(billing_topic))

        # NOTE: CloudWatch billing alarms MUST be created in us-east-1 (not us-west-2).
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
        CfnOutput(self, "ScraperFnArn", value=scraper_fn.function_arn)
        CfnOutput(self, "ProcessingFnArn", value=processing_fn.function_arn)
        CfnOutput(self, "IngestionPipelineArn", value=pipeline_sm.state_machine_arn)
