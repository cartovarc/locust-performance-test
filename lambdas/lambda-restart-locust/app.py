import logging
import os

import boto3

log_level = os.environ.get("LAMBDA_LOG_LEVEL", "INFO")
logger = logging.getLogger()
logger.setLevel(log_level)

CLUSTER_NAME = os.environ.get("CLUSTER_NAME")
MASTER_SERVICE_NAME = os.environ.get("MASTER_SERVICE_NAME")
WORKERS_SERVICE_NAME = os.environ.get("WORKERS_SERVICE_NAME")


def lambda_handler(event: dict, context: dict):
    """Lambda handler for the connect lambda function"""

    logger.info("View connection event: %s", event)
    logger.info("View connection context: %s", context)

    object_key = event["Records"][0]["s3"]["object"]["key"]

    logger.info("Object key updated: %s", object_key)

    if not object_key.endswith("locustfile.py"):
        logger.info("Object key does not match locustfile.py, exiting")
        return {"statusCode": 200}

    logger.info("Starting restart of services")

    client = boto3.client("ecs")
    response = client.update_service(
        cluster=CLUSTER_NAME,
        service=MASTER_SERVICE_NAME,
        forceNewDeployment=True,
    )

    logger.info("Response from ECS MASTER: %s", response)

    response = client.update_service(
        cluster=CLUSTER_NAME,
        service=WORKERS_SERVICE_NAME,
        forceNewDeployment=True,
    )

    logger.info("Response from ECS WORKERS: %s", response)

    return {"statusCode": 200}
