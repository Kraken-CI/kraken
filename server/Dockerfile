FROM ubuntu:20.04 as base

ENV \
        PYTHONFAULTHANDLER=1 \
        PYTHONHASHSEED=random \
        PYTHONUNBUFFERED=1

WORKDIR /server

RUN apt-get update && apt-get install -y --no-install-recommends python3 libpq5


##############################################################################################################
FROM base as builder

ENV \
        PIP_DEFAULT_TIMEOUT=100 \
        PIP_DISABLE_PIP_VERSION_CHECK=1 \
        PIP_NO_CACHE_DIR=1 \
        POETRY_VERSION=1.0.10

RUN apt-get update && apt-get install -y --no-install-recommends python3-pip python3-venv
RUN pip3 install poetry==$POETRY_VERSION
RUN python3 -m venv /venv

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
FROM base as controller
RUN apt-get update && apt-get install -y --no-install-recommends supervisor
COPY --from=builder /venv /venv
COPY supervisor.conf /etc/supervisor.conf
CMD /venv/bin/python3 -m kraken.migrations.apply && supervisord -c /etc/supervisor.conf
ARG kkver=0.0
LABEL kkver=${kkver} kkname=server


##############################################################################################################
FROM base as server
WORKDIR /server
COPY --from=builder /venv /venv
COPY kkagent /server
COPY kktool /server
# tips for running gunicorn in container: https://pythonspeed.com/articles/gunicorn-in-docker/
CMD /venv/bin/gunicorn -b 0.0.0.0:${KRAKEN_SERVER_PORT} -w 2 --worker-tmp-dir /dev/shm --log-file=- "kraken.server.server:create_app()"
ARG kkver=0.0
LABEL kkver=${kkver} kkname=server


##############################################################################################################
FROM base as celery
WORKDIR /server
RUN groupadd user && useradd --create-home --home-dir /home/user -g user user
#COPY kkcelery /server
USER user
COPY --from=builder /venv /venv
#CMD ./kkcelery
CMD /venv/bin/python3 -m kraken.server.kkcelery
ARG kkver=0.0
LABEL kkver=${kkver} kkname=server
