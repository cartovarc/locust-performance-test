aws s3 cp s3://locust-performance-test-cartovarc/script/locustfile.py /tmp
locust -f /tmp/locustfile.py --autostart
