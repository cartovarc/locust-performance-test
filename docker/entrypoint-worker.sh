echo "Starting worker"
aws s3 cp s3://locustperformance/script/locustfile.py /tmp
locust -f /tmp/locustfile.py --worker --master-host=$LOCUST_MASTER_HOST --master-port=$LOCUST_MASTER_PORT
