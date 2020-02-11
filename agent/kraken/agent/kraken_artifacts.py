import os
import glob
import logging
from ftplib import FTP

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
        except:
            log.exception('IGNORED EXCEPTION')


def _upload_all(ftp, cwd, source, dest):
    log.info('UPLOAD')
    existing_dirs = set()

    _mkdir_p(ftp, existing_dirs, dest)

    for src in source:
        if cwd:
            cwd = os.path.abspath(cwd)
            src = os.path.abspath(os.path.join(cwd, src))

        if '*' not in src and os.path.isdir(src):
            src = os.path.join(src, '**')

        if '**' in src:
            recursive = True
        else:
            recursive = False

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


def _download_all(ftp, cwd, source, dest):
    log.info('DOWNLOAD')
    for src in source:
        pass

def run(step, **kwargs):  # pylint: disable=unused-argument

    storage_addr = step['storage_addr']
    flow_id = step['flow_id']
    action = step.get('action', 'upload')
    cwd = step.get('cwd', None)

    host, port = storage_addr.split(':')
    port = int(port)
    user = 'prv_%d' % flow_id

    source = step['source']
    dest = step.get('destination', '/')

    if not isinstance(source, list):
        source = [source]

    ftp = FTP()
    ftp.connect(host, port)
    ftp.login(user)

    log.info('source: %s, dest: %s', source, dest)

    if action == 'download':
        _download_all(ftp, cwd, source, dest)
    else:
        _upload_all(ftp, cwd, source, dest)

    return 0, ''
