echo "Starting worker"
aws s3 cp s3://answerscarlos123/script/locustfile.py /tmp
LOCUST_MASTER_HOST=$(aws servicediscovery discover-instances --namespace-name  locust.local --service-name locust-master --query 'Instances[0].Attributes.AWS_INSTANCE_IPV4' --region us-east-1 --output text)
locust -f /tmp/locustfile.py --worker --master-host=$LOCUST_MASTER_HOST --master-port=5557
