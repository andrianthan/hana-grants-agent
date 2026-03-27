from aws_cdk import (
    Stack, Duration, RemovalPolicy, CfnOutput,
    aws_ec2 as ec2, aws_rds as rds,
    aws_lambda as lambda_, aws_apigateway as apigw,
    aws_s3 as s3, aws_logs as logs,
    aws_events as events, aws_events_targets as targets,
)
from constructs import Construct


class HannaStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

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
            description="Allow PostgreSQL access",
            allow_all_outbound=True,
        )
        db_sg.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(5432),
            "Allow PostgreSQL",
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

        # --- S3 Bucket ---
        bucket = s3.Bucket(
            self, "HannaBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # --- Lambda Placeholder ---
        placeholder_fn = lambda_.Function(
            self, "HannaPlaceholderFn",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_inline(
                "def handler(event, context): return {'statusCode': 200, 'body': 'placeholder'}"
            ),
            timeout=Duration.seconds(30),
            memory_size=128,
        )

        # --- API Gateway Scaffold ---
        api = apigw.RestApi(
            self, "HannaGrantsApi",
            rest_api_name="HannaGrantsApi",
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

        # --- CloudWatch Log Group ---
        log_group = logs.LogGroup(
            self, "HannaLogGroup",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # --- EventBridge Scaffold ---
        schedule_rule = events.Rule(
            self, "HannaWeeklySchedule",
            schedule=events.Schedule.cron(
                week_day="MON", hour="15", minute="0",
            ),
            enabled=False,
        )
        schedule_rule.add_target(targets.LambdaFunction(placeholder_fn))

        # --- CfnOutputs ---
        CfnOutput(self, "DbEndpoint", value=db.db_instance_endpoint_address)
        CfnOutput(self, "DbSecretArn", value=db.secret.secret_arn)
        CfnOutput(self, "BucketName", value=bucket.bucket_name)
        CfnOutput(self, "ApiUrl", value=api.url)
