import time
import socket
from urllib.parse import urlparse


def _is_service_open(addr, port, sock_type):
   s = socket.socket(socket.AF_INET, sock_type)
   s.settimeout(1)
   try:
       s.connect((addr, int(port)))
       s.shutdown(socket.SHUT_RDWR)
       return True
   except:
       return False
   finally:
       s.close()


def check_tcp_service(name, addr, port):
    attempt = 1
    trace = "checking TCP service %s on %s:%d..." % (name, addr, port)
    print("%s %d." % (trace, attempt))
    while not _is_service_open(addr, port, socket.SOCK_STREAM):
        if attempt < 3:
            time.sleep(2)
        elif attempt < 10:
            time.sleep(5)
        else:
            time.sleep(30)
        attempt += 1
        print("%s %d." % (trace, attempt))
    print("%s is up" % name)


def check_url(name, url, default_port):
    o = urlparse(url)
    check_tcp_service(name, o.hostname, o.port or default_port)


def check_postgresql(url):
    check_url('postgresql', url, 5432)
