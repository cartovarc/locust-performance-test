FROM --platform=linux/amd64 locustio/locust

RUN pip install --upgrade pip
RUN pip install awscli

USER root
RUN chmod 777 /tmp

COPY entrypoint-master.sh /tmp/entrypoint-master.sh
COPY entrypoint-worker.sh /tmp/entrypoint-worker.sh
