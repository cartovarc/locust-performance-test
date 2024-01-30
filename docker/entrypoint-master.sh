echo "Starting master"
aws s3 cp s3://locustperformance/script/locustfile.py /tmp
locust -f /tmp/locustfile.py --master -H http://${LOCUST_MASTER_HOST}:${LOCUST_MASTER_PORT}
