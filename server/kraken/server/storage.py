#!/usr/bin/env python3
import os
import logging

from pyftpdlib.authorizers import DummyAuthorizer, AuthenticationFailed
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
from flask import Flask
import pkg_resources

from . import logs
from .models import db, Flow
from . import consts
from . import srvcheck


log = logging.getLogger('storage')


def create_app():
    # addresses
    db_url = os.environ.get('KRAKEN_DB_URL', consts.DEFAULT_DB_URL)
    planner_url = os.environ.get('KRAKEN_PLANNER_URL', consts.DEFAULT_PLANNER_URL)

    srvcheck.check_postgresql(db_url)
    srvcheck.check_url('planner', planner_url, 7997)

    logs.setup_logging('storage')
    kraken_version = pkg_resources.get_distribution('kraken-server').version
    log.info('Kraken Storage started, version %s', kraken_version)

    # Create  Flask app instance
    app = Flask('Kraken Storage')

    # Configure the SqlAlchemy part of the app instance
    app.config["SQLALCHEMY_ECHO"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # initialize SqlAlchemy
    db.init_app(app)

    return app


class KrakenAuthorizer(DummyAuthorizer):
    def __init__(self, homes_dir):
        self.homes_dir = homes_dir
        super().__init__()

    def validate_authentication(self, username, password, handler):
        """Raises AuthenticationFailed if supplied username and
        password don't match the stored credentials, else return
        None.
        """

        msg = "Authentication failed."
        # if not self.has_user(username):
        #     if username == 'anonymous':
        #         msg = "Anonymous access not allowed."
        #     raise AuthenticationFailed(msg)
        # if username != 'anonymous':
        #     if self.user_table[username]['pwd'] != password:
        #         raise AuthenticationFailed(msg)

        if '_' not in username:
            raise AuthenticationFailed(msg)
        try:
            dest, flow_id_txt = username.split('_')
            flow_id = int(flow_id_txt)
        except:
            raise AuthenticationFailed(msg)

        if dest not in ['public', 'private', 'report']:
            raise AuthenticationFailed(msg)

        flow = None
        try:
            flow = Flow.query.filter_by(id=flow_id).one_or_none()
        except:
            log.exception('problem with sql')
            db.session.rollback()
        if flow is None:
            raise AuthenticationFailed(msg)

        home_dir = os.path.join(self.homes_dir, dest, flow_id_txt)
        if not os.path.exists(home_dir):
            os.makedirs(home_dir)

        self.add_user(username, password, home_dir, perm='elradfmwMT')

        handler.username = username

        log.info('logged %s', username)


class KrakenFTPHandler(FTPHandler):
    def on_connect(self):
        log.info("%s:%s connected", self.remote_ip, self.remote_port)
        self.username = None

    def on_disconnect(self):
        log.info("%s:%s disconnected", self.remote_ip, self.remote_port)
        if self.username:
            self.authorizer.remove_user(self.username)
            self.username = None

def main():
    app = create_app()

    with app.app_context():

        storage_dir = os.environ.get('KRAKEN_STORAGE_DIR', consts.DEFAULT_STORAGE_DIR)

        # Instantiate a dummy authorizer for managing 'virtual' users
        authorizer = KrakenAuthorizer(storage_dir)

        # Instantiate FTP handler class
        handler = KrakenFTPHandler
        handler.authorizer = authorizer
        handler.permit_foreign_addresses = True  # to allow connecting from docker containers while their address are changing

        handler.banner = "Kraken Storage."

        # Instantiate FTP server class and listen on
        storage_addr = os.environ.get('KRAKEN_STORAGE_ADDR', consts.DEFAULT_STORAGE_ADDR)
        _, storage_port = storage_addr.split(':')
        address = ('', int(storage_port))
        server = FTPServer(address, handler)

        # set a limit for connections
        server.max_cons = 256
        server.max_cons_per_ip = 5

        # start ftp server
        server.serve_forever()


if __name__ == "__main__":
    main()
