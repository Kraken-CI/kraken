#!/usr/bin/env python3
import os
import logging

from flask import render_template
from flask_cors import CORS
import connexion
from connexion.resolver import Resolver

import logs
import models
import backend
import consts

log = logging.getLogger('server')


class MyResolver(Resolver):
    def resolve_operation_id(self, operation):
        operation_id = operation.operation_id
        tags = operation._operation['tags']
        return '{}.{}'.format(tags[0].lower(), operation_id)


def create_app():
    logs.setup_logging('server')

    # Create the connexion application instance
    basedir = os.path.abspath(os.path.dirname(__file__))
    port = int(os.environ.get('KRAKEN_PORT', 8080))
    connex_app = connexion.App('Kraken Server', port=port, specification_dir=basedir)

    # Get the underlying Flask app instance
    app = connex_app.app

    # db url
    db_url = os.environ.get('DB_URL', "postgresql://kraken:kk123@localhost:5433/kraken")

    # Configure the SqlAlchemy part of the app instance
    app.config["SQLALCHEMY_ECHO"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # initialize SqlAlchemy
    models.db.init_app(app)
    models.db.create_all(app=app)
    with app.app_context():
        models.prepare_initial_data()

    # Read the swagger.yml file to configure the endpoints
    connex_app.add_api("swagger.yml", resolver=MyResolver())

    # # Create a URL route in our application for "/"
    # connex_app.add_url_rule('/', view_func=home)
    # connex_app.add_url_rule("/people", view_func=people)
    # connex_app.add_url_rule("/people/<int:person_id>", view_func=people)

    # # Create a URL route to the notes page
    # connex_app.add_url_rule("/people/<int:person_id>", view_func=notes)
    # connex_app.add_url_rule("/people/<int:person_id>/notes", view_func=notes)
    # connex_app.add_url_rule("/people/<int:person_id>/notes/<int:note_id>", view_func=notes)

    # backend for serving agents
    connex_app.add_url_rule("/backend", view_func=backend.serve_agent_request, methods=['POST'])

    # add handling CORS
    CORS(app)

    return connex_app


def main():
    app = create_app()
    log.info('server initiated', version='0.1')
    app.run(debug=True)


if __name__ == "__main__":
    main()
