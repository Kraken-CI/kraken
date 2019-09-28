#!/usr/bin/env python3
import os
import logging

from flask import render_template
import connexion

import models
import backend
import consts

log = logging.getLogger('server')


def home():
    """
    This function just responds to the browser URL
    localhost:5000/

    :return:        the rendered template "home.html"
    """
    return render_template("home.html")


def people(person_id=""):
    """
    This function just responds to the browser URL
    localhost:5000/people

    :return:        the rendered template "people.html"
    """
    return render_template("people.html", person_id=person_id)


def notes(person_id, note_id=""):
    """
    This function responds to the browser URL
    localhost:5000/notes/<person_id>

    :param person_id:   Id of the person to show notes for
    :return:            the rendered template "notes.html"
    """
    return render_template("notes.html", person_id=person_id, note_id=note_id)


def create_app():
    basedir = os.path.abspath(os.path.dirname(__file__))

    logging.basicConfig(format=consts.CONSOLE_LOG_FMT, level=logging.INFO)

    # Create the connexion application instance
    connex_app = connexion.App('Kraken Server', specification_dir=basedir)

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
    connex_app.add_api("swagger.yml")

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

    return connex_app


def main():
    app = create_app()
    app.run(debug=True)


if __name__ == "__main__":
    main()
