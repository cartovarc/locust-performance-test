from aws_cdk import (
    aws_ecs as ecs,
    aws_ecs_patterns as ecsp,
    aws_iam as iam,
    aws_s3 as s3,
    aws_lambda,
    Duration,
    aws_s3_notifications,
    Stack,
)
from constructs import Construct


class LocusPerformanceStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        bucket = s3.Bucket.from_bucket_name(
            self,
            "locustPerformanceBucket",
            bucket_name="locustperformance",
        )

        application = ecsp.ApplicationLoadBalancedFargateService(
            self,
            "LocustServer",
            task_image_options=ecsp.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_asset(
                    directory="docker",
                ),
                entry_point=["/bin/sh", "/tmp/entrypoint.sh"],
                container_port=8089,
            ),
            public_load_balancer=True,
        )

        # This allows get the script from S3
        allow_read_bucket_policy_statement = iam.PolicyStatement(
            actions=["s3:Get*", "s3:List*"],
            effect=iam.Effect.ALLOW,
            resources=[
                f"{bucket.bucket_arn}/*",
                f"{bucket.bucket_arn}",
            ],
        )
        application.task_definition.task_role.add_to_principal_policy(
            allow_read_bucket_policy_statement
        )

        # Create a lambda to restart the locust service
        lambda_restart_locust = aws_lambda.Function(
            self,
            "lambdaRestartLocust",
            function_name="lambda-restart-locust",
            runtime=aws_lambda.Runtime.PYTHON_3_11,
            code=aws_lambda.Code.from_asset("lambdas/lambda-restart-locust"),
            timeout=Duration.seconds(30),
            handler="app.lambda_handler",
        )

        lambda_restart_locust.add_environment("CLUSTER_NAME", application.cluster.cluster_name)
        lambda_restart_locust.add_environment("SERVICE_NAME", application.service.service_name)

        # Allow the lambda to update ECS tasks
        allow_read_bucket_policy_statement = iam.PolicyStatement(
            actions=["ecs:UpdateService"],
            effect=iam.Effect.ALLOW,
            resources=["*"],
        )
        lambda_restart_locust.add_to_role_policy(allow_read_bucket_policy_statement)

        # Trigger lambda restart locust when a file is updated
        bucket.add_event_notification(
            event=s3.EventType.OBJECT_CREATED,
            dest=aws_s3_notifications.LambdaDestination(lambda_restart_locust),
        )
