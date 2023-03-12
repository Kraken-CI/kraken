import os
import alembic.config
from flask import Flask
import sqlalchemy
import psycopg2.errors

from kraken.server import models, initdb, consts, srvcheck

def _get_db_version(app):
    with app.app_context():
        db_version = None
        try:
            db_version = models.AlembicVersion.query.one_or_none()
            if db_version is not None:
                db_version = db_version.version_num
        except sqlalchemy.exc.ProgrammingError as ex:
            if not isinstance(ex.orig, psycopg2.errors.UndefinedTable):
                raise

    return db_version


def main():
    print('Kraken DB Migration')

    # Create  Flask app instance
    app = Flask('Kraken DB Migration')

    db_url = os.environ.get('KRAKEN_DB_URL', consts.DEFAULT_DB_URL)
    print('migrating db: %s' % db_url)

    # wait for db
    srvcheck.check_postgresql(db_url)

    # Configure the SqlAlchemy part of the app instance
    app.config["SQLALCHEMY_ECHO"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # initialize SqlAlchemy
    models.db.init_app(app)

    db_version = _get_db_version(app)

    here = os.path.dirname(os.path.abspath(__file__))
    alembic_ini_path = os.path.join(here, 'alembic.ini')
    alembic_args = [
        '-c', alembic_ini_path,
    ]

    if db_version is None:
        # create tables in db
        with app.app_context():
            models.db.create_all()

        # stamp the alembic version of db schema in db
        alembic_args.extend(['stamp', 'head'])
        alembic.config.main(argv=alembic_args)
        print('alembic stamp completed')
    else:
        alembic_args.extend(['upgrade', 'head'])
        alembic.config.main(argv=alembic_args)
        print('alembic migration completed')

    with app.app_context():
        initdb.prepare_initial_data()

    db_version = _get_db_version(app)
    print('DB version: %s' % str(db_version))
    print('Kraken DB Migration completed')


if __name__ == "__main__":
    main()
