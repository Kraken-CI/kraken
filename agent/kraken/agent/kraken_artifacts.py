import logging
from ftplib import FTP

log = logging.getLogger(__name__)


def run(step, **kwargs):  # pylint: disable=unused-argument

    storage_addr = step['storage_addr']
    flow_id = step['flow_id']
    log.info('storage addr: %s, flow: %d', storage_addr, flow_id)

    host, port = storage_addr.split(':')
    port = int(port)
    user = 'prv_%d' % flow_id

    ftp = FTP()
    ftp.connect(host, port)
    ftp.login(user)

    log.info('LIST %s', ftp.retrlines('LIST'))

    return 0, ''
