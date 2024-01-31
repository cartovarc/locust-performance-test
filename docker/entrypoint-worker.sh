echo "Starting worker"
aws s3 cp s3://locustperformance/script/locustfile.py /tmp

LOCUST_MASTER_HOST=None
while [ "$LOCUST_MASTER_HOST" = "None" ]; do
    echo "Waiting for variable to be set..."
    LOCUST_MASTER_HOST=$(aws servicediscovery discover-instances --namespace-name  locust.local --service-name locust-master --query 'Instances[0].Attributes.AWS_INSTANCE_IPV4' --region us-east-1 --output text)
    sleep 5 
done
echo "LOCUST_MASTER_HOST is now set to: $LOCUST_MASTER_HOST"

locust -f /tmp/locustfile.py --worker --master-host=$LOCUST_MASTER_HOST --master-port=5557
