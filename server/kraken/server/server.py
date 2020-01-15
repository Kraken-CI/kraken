#!/usr/bin/env python3
import os
import re
import time
import logging

from flask import render_template
import connexion
from connexion.resolver import Resolver

from . import logs
from . import models
from . import backend
from . import consts
from . import srvcheck
from . import webhooks

log = logging.getLogger('server')


class MyResolver(Resolver):
    def resolve_operation_id(self, operation):
        operation_id = operation.operation_id
        tags = operation._operation['tags']
        name = 'kraken.server.{}.{}'.format(tags[0].lower(), operation_id)
        return name


def create_app():
    # addresses
    db_url = os.environ.get('KRAKEN_DB_URL', consts.DEFAULT_DB_URL)
    redis_addr = os.environ.get('KRAKEN_REDIS_ADDR', consts.DEFAULT_REDIS_ADDR)
    elasticsearch_url = os.environ.get('KRAKEN_ELASTICSEARCH_URL', consts.DEFAULT_ELASTICSEARCH_URL)
    logstash_addr = os.environ.get('KRAKEN_LOGSTASH_ADDR', consts.DEFAULT_LOGSTASH_ADDR)
    planner_url = os.environ.get('KRAKEN_PLANNER_URL', consts.DEFAULT_PLANNER_URL)
    server_addr = os.environ.get('KRAKEN_SERVER_ADDR', consts.DEFAULT_SERVER_ADDR)

    #_check_udp_service('logstash', 'logstash', 5959)
    srvcheck.check_postgresql(db_url)
    srvcheck.check_tcp_service('redis', redis_addr, 6379)
    srvcheck.check_url('elasticsearch', elasticsearch_url, 9200)
    srvcheck.check_url('planner', planner_url, 7997)

    logs.setup_logging('server')
    log.info('Kraken Server started')

    # Create the connexion application instance
    basedir = os.path.abspath(os.path.dirname(__file__))
    _, server_port = server_addr.split(':')
    connex_app = connexion.App('Kraken Server', port=int(server_port), specification_dir=basedir)

    # Get the underlying Flask app instance
    app = connex_app.app

    # Configure the SqlAlchemy part of the app instance
    app.config["SQLALCHEMY_ECHO"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # initialize SqlAlchemy
    models.db.init_app(app)

    # Read the swagger.yml file to configure the endpoints
    connex_app.add_api("swagger.yml", resolver=MyResolver())

    # backend for serving agents
    connex_app.add_url_rule("/backend", view_func=backend.serve_agent_request, methods=['POST'])

    # install webhooks
    webhooks_bp = webhooks.create_blueprint()
    app.register_blueprint(webhooks_bp, url_prefix='/webhooks')

    return connex_app


def main():
    app = create_app()
    app.run(debug=True)


if __name__ == "__main__":
    main()
