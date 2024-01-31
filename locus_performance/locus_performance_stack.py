from aws_cdk import (
    aws_ecs as ecs,
    aws_ecs_patterns as ecsp,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_s3 as s3,
    aws_lambda,
    aws_servicediscovery as servicediscovery,
    Duration,
    aws_s3_notifications,
    Stack,
)
from constructs import Construct


class LocusPerformanceStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        locust_interface_container_port = 8089
        locust_master_port = 5557

        self.bucket = s3.Bucket.from_bucket_name(
            self,
            "locustPerformanceBucket",
            bucket_name="locustperformance",
        )

        vpc = ec2.Vpc(
            self,
            "LocustVpc",
            max_azs=2,
        )

        service_desconvery_namespace = servicediscovery.PrivateDnsNamespace(
            self,
            "LocustServiceDiscovery",
            vpc=vpc,
            name="locust.local",
            description="Namespace for Locust",
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
                container_port=locust_interface_container_port,
            ),
            vpc=vpc,
            cloud_map_options=ecs.CloudMapOptions(
                name="locust-master",
                dns_record_type=servicediscovery.DnsRecordType.A,
                dns_ttl=Duration.seconds(60),
                cloud_map_namespace=service_desconvery_namespace,
                container_port=locust_master_port,
            ),
            public_load_balancer=True,
        )
        self.application_master = application_master

        application_master.service.connections.allow_from_any_ipv4(
            ec2.Port.tcp(locust_master_port),
            "Allow inbound traffic on the locust master port",
        )

        # Add the locust master port to the container
        application_master.task_definition.default_container.add_port_mappings(
            ecs.PortMapping(
                host_port=locust_master_port,
                container_port=locust_master_port,
            )
        )

        self.workers_task_definition = ecs.FargateTaskDefinition(
            self,
            "LocustWorkersTaskDefinition",
        )

        self.workers_task_definition.add_container(
            "locust-workers",
            image=ecs.ContainerImage.from_asset(
                directory="docker",
            ),
            entry_point=["/bin/sh", "/tmp/entrypoint-worker.sh"],
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="locust-workers",
            ),
        )

        self.locust_workers_service = ecs.FargateService(
            self,
            "LocustWorkers",
            service_name="locust-performance-workers",
            task_definition=self.workers_task_definition,
            cluster=application_master.cluster,
        )

        self.setup_permissions()
        self.setup_lambda_restart()
        self.configure_autoscaling()
        # self.setup_service_descovery()

    def setup_permissions(self):
        self.workers_task_definition.execution_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AmazonECSTaskExecutionRolePolicy"
            )
        )
        self.workers_task_definition.task_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AmazonECSTaskExecutionRolePolicy"
            )
        )
        self.workers_task_definition.execution_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AWSCloudMapReadOnlyAccess")
        )
        self.workers_task_definition.task_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AWSCloudMapReadOnlyAccess")
        )

        # This allows get the script from S3
        bucket_policy_statement = iam.PolicyStatement(
            actions=["s3:*"],
            effect=iam.Effect.ALLOW,
            resources=[
                f"{self.bucket.bucket_arn}/*",
                f"{self.bucket.bucket_arn}",
            ],
        )

        # Setup read only access to S3
        self.workers_task_definition.task_role.add_to_principal_policy(
            bucket_policy_statement
        )
        self.workers_task_definition.execution_role.add_to_principal_policy(
            bucket_policy_statement
        )
        self.application_master.task_definition.task_role.add_to_principal_policy(
            bucket_policy_statement
        )
        self.application_master.task_definition.execution_role.add_to_principal_policy(
            bucket_policy_statement
        )

    def setup_lambda_restart(self):
        """Create a lambda to restart the locust service"""
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
            "CLUSTER_NAME", self.application_master.cluster.cluster_name
        )
        lambda_restart_locust.add_environment(
            "MASTER_SERVICE_NAME", self.application_master.service.service_name
        )
        lambda_restart_locust.add_environment(
            "WORKERS_SERVICE_NAME", self.locust_workers_service.service_name
        )

        # Allow the lambda to update ECS tasks
        allow_read_bucket_policy_statement = iam.PolicyStatement(
            actions=["ecs:UpdateService"],
            effect=iam.Effect.ALLOW,
            resources=["*"],
        )
        lambda_restart_locust.add_to_role_policy(allow_read_bucket_policy_statement)

        # Trigger lambda restart locust when a file is updated
        self.bucket.add_event_notification(
            event=s3.EventType.OBJECT_CREATED,
            dest=aws_s3_notifications.LambdaDestination(lambda_restart_locust),
        )

    def configure_autoscaling(self):
        """Configure autoscaling for the workers service."""
        workers_scaling = self.locust_workers_service.auto_scale_task_count(
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
