#!/usr/bin/env python3

# Copyright 2020 The Kraken Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import logging
import mimetypes
from queue import Queue, Empty
from ftplib import FTP, error_perm
from threading import Thread, Event

from pyftpdlib.authorizers import DummyAuthorizer, AuthenticationFailed
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
from pyftpdlib.filesystems import AbstractedFS
from flask import Flask, abort, request, Response

from . import logs
from .models import db, Run, Flow
from . import consts
from . import srvcheck
from .. import version


log = logging.getLogger('storage')


def create_app():
    # addresses
    db_url = os.environ.get('KRAKEN_DB_URL', consts.DEFAULT_DB_URL)
    planner_url = os.environ.get('KRAKEN_PLANNER_URL', consts.DEFAULT_PLANNER_URL)

    srvcheck.check_postgresql(db_url)
    srvcheck.check_url('planner', planner_url, 7997)

    logs.setup_logging('storage')
    log.info('Kraken Storage started, version %s', version.version)

    # Create  Flask app instance
    app = Flask('Kraken Storage')

    # Configure the SqlAlchemy part of the app instance
    app.config["SQLALCHEMY_ECHO"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = dict(pool_recycle=600, pool_pre_ping=True)

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

        if '_' not in username:
            raise AuthenticationFailed('Authentication failed: not _ in username')
        try:
            dest, ul_dl, entity_id_txt = username.split('_')
            entity_id = int(entity_id_txt)
        except Exception as e:
            raise AuthenticationFailed('Authentication failed: parsing username failed: %s' % str(e))

        if dest not in ['public', 'private', 'report']:
            raise AuthenticationFailed('Authentication failed: wrong destination: %s' % dest)

        if ul_dl not in ['ul', 'dl', 'dlr']:
            raise AuthenticationFailed('Authentication failed: wrong ul/dl: %s' % ul_dl)

        handler.latest_runs = None
        home_dir = os.path.join(self.homes_dir, dest)
        attemtps = 3
        while True:
            try:
                if ul_dl in ['ul', 'dlr']:
                    run = Run.query.filter_by(id=entity_id).one_or_none()
                    home_dir = os.path.join(home_dir, str(run.flow_id), str(run.id))
                else:
                    flow = Flow.query.filter_by(id=entity_id).one_or_none()
                    latest_runs = {}
                    for r in flow.runs:
                        if r.stage_id not in latest_runs or r.id > latest_runs[r.stage_id]:
                            latest_runs[r.stage_id] = r.id
                    handler.latest_runs = latest_runs
                    home_dir = os.path.join(home_dir, str(flow.id))
                break
            except Exception as e:
                log.exception('problem with sql')
                db.session.rollback()
                attemtps -= 1
                if attemtps == 0:
                    raise AuthenticationFailed('Authentication failed: problem with SQL: %s' % str(e))

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
            try:
                self.authorizer.remove_user(self.username)
            except:
                pass
            self.username = None

    def on_file_received(self, f):
        log.info('received %s', f)


class KrakenFilesystem(AbstractedFS):
    def ftp2fs(self, ftppath):
        if self.cmd_channel.latest_runs is None:
            return super().ftp2fs(ftppath)

        path = self.ftpnorm(ftppath)
        newpath = os.path.join(self.root, '0', path)
        for run_id in self.cmd_channel.latest_runs.values():
            path2 = os.path.join(self.root, str(run_id), path[1:])
            if os.path.exists(path2):
                newpath = path2
                break
        return newpath


##########################################

class FTPDownloader(object):
    def __init__(self, host, port, user, timeout=0.01):
        self.ftp = FTP()
        self.ftp.connect(host, port)
        try:
            self.ftp.login(user)
        except:
        # try one more time
            self.ftp.login(user)

        self.timeout = timeout

    def getBytes(self, filename):
        print("getBytes")
        self.ftp.retrbinary("RETR {}".format(filename) , self.bytes.put)
        self.bytes.join()   # wait for all blocks in the queue to be marked as processed
        self.finished.set() # mark streaming as finished

    def sendBytes(self):
        while not self.finished.is_set():
            try:
                yield self.bytes.get(timeout=self.timeout)
                self.bytes.task_done()
            except Empty:
                self.finished.wait(self.timeout)
        self.worker.join()

    def download(self, filename):
        self.bytes = Queue()
        self.finished = Event()
        self.worker = Thread(target=self.getBytes, args=(filename,))
        self.worker.start()
        return self.sendBytes()


def serve_artifact(store_type, flow_id, run_id, path):
    log.info('path %s, %s, %s', store_type, flow_id, path)

    if store_type not in ['public', 'report']:
        abort(400, "Not supported store type: %s" % store_type)

    storage_addr = os.environ.get('KRAKEN_STORAGE_ADDR', consts.DEFAULT_STORAGE_ADDR)
    host, port = storage_addr.split(':')

    log.info('FTP HOST %s', storage_addr)

    if flow_id:
        flow = Flow.query.filter_by(id=int(flow_id)).one_or_none()
        if flow is None:
            abort(404, "Flow not found")
        user = '%s_dl_%s' % (store_type, flow_id)
    else:
        run = Run.query.filter_by(id=int(run_id)).one_or_none()
        if run is None:
            abort(404, "Run not found")
        user = '%s_dlr_%s' % (store_type, run_id)

    mt, _ = mimetypes.guess_type(path)
    if mt is None:
        mt = 'application/octet-stream'

    try:
        ftp = FTPDownloader(host, int(port), user)
    except OSError:
        abort(500, 'Cannot connect to storage service')

    return Response(ftp.download(path), mimetype=mt)


def serve_flow_artifact(store_type, flow_id, path):
    return serve_artifact(store_type, flow_id, None, path)


def serve_run_artifact(store_type, run_id, path):
    return serve_artifact(store_type, None, run_id, path)


##########################################

def main():
    app = create_app()

    with app.app_context():

        storage_dir = os.environ.get('KRAKEN_STORAGE_DIR', consts.DEFAULT_STORAGE_DIR)

        # Instantiate a dummy authorizer for managing 'virtual' users
        authorizer = KrakenAuthorizer(storage_dir)

        # Instantiate FTP handler class
        handler = KrakenFTPHandler
        handler.authorizer = authorizer
        handler.abstracted_fs = KrakenFilesystem
        handler.permit_foreign_addresses = True  # to allow connecting from docker containers while their address are changing

        handler.banner = "Kraken Storage."

        # Instantiate FTP server class and listen on
        storage_addr = os.environ.get('KRAKEN_STORAGE_ADDR', consts.DEFAULT_STORAGE_ADDR)
        _, storage_port = storage_addr.split(':')
        address = ('', int(storage_port))
        log.info('listening on %s', address)
        server = FTPServer(address, handler)

        # set a limit for connections
        server.max_cons = 256
        server.max_cons_per_ip = 5

        # start ftp server
        server.serve_forever()


if __name__ == "__main__":
    main()
