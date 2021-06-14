FROM krakenci/srv-builder as builder

# install python dependencies first
COPY pyproject.toml poetry.lock /server/
RUN \
        . /venv/bin/activate && \
        poetry install -n --no-dev --no-root

# then install kraken-server
COPY . /server
RUN \
        . /venv/bin/activate && \
        poetry build -f wheel -n && \
        pip install --no-deps dist/*.whl && \
        rm -rf dist *.egg-info


##############################################################################################################
FROM krakenci/srv-base as controller
RUN apt-get update && apt-get install -y --no-install-recommends supervisor && rm -rf /var/lib/apt/lists/*
COPY --from=builder /venv /venv
COPY supervisor.conf /etc/supervisor.conf
CMD /venv/bin/python3 -m kraken.migrations.apply && supervisord -c /etc/supervisor.conf
ARG kkver=0.0
LABEL kkver=${kkver} kkname=server


##############################################################################################################
FROM krakenci/srv-base as server
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /server
COPY --from=builder /venv /venv
COPY kkagent /server
COPY kktool /server
# tips for running gunicorn in container: https://pythonspeed.com/articles/gunicorn-in-docker/
CMD /venv/bin/gunicorn -b 0.0.0.0:${KRAKEN_SERVER_PORT} -w 2 --worker-tmp-dir /dev/shm --log-file=- "kraken.server.server:create_app()"
ARG kkver=0.0
LABEL kkver=${kkver} kkname=server


##############################################################################################################
FROM krakenci/srv-base as rq
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /server
RUN groupadd user && useradd --create-home --home-dir /home/user -g user user
USER user
COPY --from=builder /venv /venv
CMD /venv/bin/python3 -m kraken.server.kkrq
ARG kkver=0.0
LABEL kkver=${kkver} kkname=server
