import os
import glob
import logging
from ftplib import FTP

log = logging.getLogger(__name__)

def _upload(ftp, dest_f, f):
    if os.path.isdir(f):
        log.info('mkdir %s', dest_f)
        try:
            ftp.mkd(dest_f)
        except:
            pass
    else:
        log.info('store %s', dest_f)
        with open(f, 'rb') as fp:
            ftp.storbinary('STOR ' + dest_f, fp)

def run(step, **kwargs):  # pylint: disable=unused-argument

    storage_addr = step['storage_addr']
    flow_id = step['flow_id']

    host, port = storage_addr.split(':')
    port = int(port)
    user = 'prv_%d' % flow_id

    source = step['source']
    dest = step['destination']

    if not isinstance(source, list):
        source = [source]

    ftp = FTP()
    ftp.connect(host, port)
    ftp.login(user)

    # TODO: cwd
    log.info('source: %s, dest: %s', source, dest)

    for src in source:
        if '*' in src:
            if '**' in src:
                recursive = True
            else:
                recursive = False
            for f in glob.iglob(src, recursive=recursive):
                dest_f = os.path.join(dest, f)
                _upload(ftp, dest_f, f)
        else:
            dest_f = os.path.join(dest, src)
            _upload(ftp, dest_f, src)
    return 0, ''
