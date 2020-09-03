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
import glob
import logging
from ftplib import FTP, error_perm

log = logging.getLogger(__name__)


def _mkdir_p(ftp, existing_dirs, path):
    inter_path = '/'
    for d in path.strip('/').split('/'):
        inter_path = os.path.join(inter_path, d)
        if inter_path in existing_dirs:
            continue
        # log.info('inter mkdir %s', inter_path)
        try:
            ftp.mkd(inter_path)
            existing_dirs.add(inter_path)
        except error_perm as e:
            if '550 File exists' not in str(e):
                log.exception('IGNORED EXCEPTION')


def _upload_all(ftp, cwd, source, dest, report_artifact):
    existing_dirs = set()

    _mkdir_p(ftp, existing_dirs, dest)

    for src in source:
        if cwd:
            cwd = os.path.abspath(cwd)
            src = os.path.abspath(os.path.join(cwd, src))

        if '*' not in src and os.path.isdir(src):
            src = os.path.join(src, '**')

        recursive = '**' in src

        files_num = 0
        for f in glob.iglob(src, recursive=recursive):
            if cwd:
                f_path = os.path.relpath(f, cwd)
            else:
                f_path = f
            dest_f = os.path.join(dest, f_path)

            if os.path.isdir(f):
                _mkdir_p(ftp, existing_dirs, dest_f)
            else:
                base_dir = os.path.dirname(dest_f)
                _mkdir_p(ftp, existing_dirs, base_dir)
                log.info('store %s -> %s', f, dest_f)
                with open(f, 'rb') as fp:
                    ftp.storbinary('STOR ' + dest_f, fp)

                artifact = dict(path=dest_f, size=os.path.getsize(f))
                report_artifact(artifact)
                files_num += 1

        # if no files were uploaded then raise error or just mention about that
        if files_num == 0:
            if '*' in src:
                log.warning('no files found for %s', src)
            else:
                msg = 'file %s not found for upload' % src
                log.error(msg)
                return 1, msg

    return 0, ''


def _download_dir(ftp, source, dest):
    dest_file = os.path.join(dest, source)
    with open(dest_file, 'wb') as f:
        ftp.retrbinary("RETR " + source, f.write)

    # #list children:
    # filelist=ftp.nlst()

    # for f in filelist:
    #     try:
    #         #this will check if file is folder:
    #         ftp.cwd(path+f+"/")
    #         #if so, explore it:
    #         downloadFiles(path+f+"/",destination)
    #     except ftplib.error_perm:
    #         #not a folder with accessible content
    #         #download & return
    #         os.chdir(destination[0:len(destination)-1]+path)
    #         #possibly need a permission exception catch:
    #         ftp.retrbinary("RETR "+f, open(os.path.join(destination,f),"wb").write)


def _download_all(ftp, cwd, source, dest):
    if cwd:
        dest = os.path.join(cwd, dest)

    if not os.path.exists(dest):
        os.makedirs(dest)

    for src in source:
        try:
            _download_dir(ftp, src, dest)
        except Exception as e:
            msg = 'problem with downloading %s: %s' % (src, str(e))
            log.error(msg)
            return 1, msg

    return 0, ''


def run_artifacts(step, report_artifact=None):

    storage_addr = step['storage_addr']
    action = step.get('action', 'upload')
    cwd = step.get('cwd', None)
    public = step.get('public', False)

    host, port = storage_addr.split(':')
    port = int(port)

    if action == 'report':
        user = 'report_'
    elif public:
        user = 'public_'
    else:
        user = 'private_'

    if action == 'download':
        user += 'dl_%d' % step['flow_id']
    else:
        user += 'ul_%d' % step['run_id']

    source = step['source']
    dest = step.get('destination', '.' if action == 'download' else '/')

    log.info('%s: source: %s, dest: %s', action, source, dest)

    if not isinstance(source, list):
        source = [source]

    ftp = FTP()
    ftp.connect(host, port)
    try:
        ftp.login(user)
    except:
        # try one more time
        ftp.login(user)

    if action == 'download':
        status, msg = _download_all(ftp, cwd, source, dest)
    else:
        status, msg = _upload_all(ftp, cwd, source, dest, report_artifact)

    return status, msg
