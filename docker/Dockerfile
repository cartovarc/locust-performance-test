FROM --platform=linux/amd64 locustio/locust

RUN pip install --upgrade pip
RUN pip install awscli

COPY entrypoint.sh /tmp/entrypoint.sh
