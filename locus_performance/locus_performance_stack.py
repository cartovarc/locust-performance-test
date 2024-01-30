from aws_cdk import (
    aws_ecs as ecs,
    aws_ecs_patterns as ecsp,
    aws_iam as iam,
    aws_s3 as s3,
    aws_lambda,
    aws_elasticloadbalancingv2 as elbv2,
    Duration,
    aws_s3_notifications,
    Stack,
)
from constructs import Construct


class LocusPerformanceStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        locust_container_port = 8089

        bucket = s3.Bucket.from_bucket_name(
            self,
            "locustPerformanceBucket",
            bucket_name="locustperformance",
        )

        application_master = ecsp.ApplicationLoadBalancedFargateService(
            self,
            "LocustMaster",
            service_name="locust-performance-master",
            task_image_options=ecsp.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_asset(
                    directory="docker",
                ),
                entry_point=["/bin/sh", "/tmp/entrypoint-master.sh"],
                container_port=locust_container_port,
            ),
            public_load_balancer=True,
        )

        self.application_master = application_master

        # Listen also by the Locust port and not only http
        application_master.load_balancer.add_listener(
            "LocustMasterListener",
            port=locust_container_port,
            protocol=elbv2.ApplicationProtocol.HTTP,
            default_target_groups=[application_master.target_group],
        )

        workers_task_definition = ecs.FargateTaskDefinition(
            self,
            "LocustWorkersTaskDefinition",
        )

        workers_task_definition.add_container(
            "locust-workers",
            image=ecs.ContainerImage.from_asset(
                directory="docker",
            ),
            entry_point=["/bin/sh", "/tmp/entrypoint-worker.sh"],
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="locust-workers",
            ),
        )

        # Allow ECS common actions
        workers_task_definition.execution_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AmazonECSTaskExecutionRolePolicy"
            )
        )

        locust_workers_service = ecs.FargateService(
            self,
            "LocustWorkers",
            service_name="locust-performance-workers",
            task_definition=workers_task_definition,
            cluster=application_master.cluster,
        )

        workers_task_definition.default_container.add_environment(
            "LOCUST_MASTER_HOST",
            application_master.load_balancer.load_balancer_dns_name,
        )
        workers_task_definition.default_container.add_environment(
            "LOCUST_MASTER_PORT", str(locust_container_port)
        )

        workers_scaling = locust_workers_service.auto_scale_task_count(
            max_capacity=5,
            min_capacity=1,
        )

        workers_scaling.scale_on_cpu_utilization(
            "CpuScaling",
            target_utilization_percent=50,
            scale_in_cooldown=Duration.seconds(60),
            scale_out_cooldown=Duration.seconds(60),
        )

        workers_scaling.scale_on_memory_utilization(
            "MemoryScaling",
            target_utilization_percent=50,
            scale_in_cooldown=Duration.seconds(60),
            scale_out_cooldown=Duration.seconds(60),
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
        application_master.task_definition.task_role.add_to_principal_policy(
            allow_read_bucket_policy_statement
        )
        workers_task_definition.task_role.add_to_principal_policy(
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

        lambda_restart_locust.add_environment(
            "CLUSTER_NAME", application_master.cluster.cluster_name
        )
        lambda_restart_locust.add_environment(
            "MASTER_SERVICE_NAME", application_master.service.service_name
        )
        lambda_restart_locust.add_environment(
            "WORKERS_SERVICE_NAME", locust_workers_service.service_name
        )

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
