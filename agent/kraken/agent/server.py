import os
import json
import time
import logging
import datetime
import urllib.request

from . import config
from . import consts

log = logging.getLogger(__name__)


PORT_IN = 42000
PORT_OUT = 42001
BCAST_ADDR = ('<broadcast>', PORT_OUT)

AGENT_DATA_DIR = '.'


def get_addr_file_path():
    agent_dir = os.path.dirname(os.path.abspath(__file__))
    var_dir = os.path.join(agent_dir, AGENT_VAR_DIR)
    try:
        os.makedirs(var_dir)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(var_dir):
            pass
        else:
            raise
    return os.path.join(var_dir, BIND_SERVER_FILE)


def init_bind_file(bind_file):
    for etc_file in ETC_FILES:
        if os.path.exists(etc_file):
            shutil.copy2(etc_file, bind_file)


def get_bind_data():
    bind_file = get_bind_file()
    init_bind_file(bind_file)
    if not os.path.isfile(bind_file):
        return {}
    f = open(bind_file)
    try:
        data = f.read()
        bind_data = {}
        for key, value in re.findall(r"(\w+):(.*)", data):
            bind_data[key.strip()] = value.strip()
    except:
        return {}
    finally:
        f.close()
    return bind_data


def get_bind_server():
    bind_data = get_bind_data()
    serv = ''
    if 'ip' in bind_data:
        serv = bind_data['ip']
    return serv


def unbind_server():
    bind_file = get_bind_file()
    if not os.path.exists(bind_file):
        log.info("Bind file does not exist.")
        return False
    bind_data = get_bind_data()
    if 'ip' in bind_data:
        log.info('Removing ip from bind file...')
        bind_data['ip'] = ''
        data = ""
        for item in bind_data:
            data += str(item) + ': ' + str(bind_data[item]) + '\n'
        f = open(bind_file, 'w')
        f.write(data)
        f.close()
        log.info('Bind ip address removed successfully')
        return True
    else:
        log.warning("Lack of ip address in bind file.")
        return False


def send_get_addr_packet(ip, mac, hostname, bind_server, srv_addr_bcast=BCAST_ADDR):
    send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        if bind_server:
            # if bind exist, send only to bind server, otherwise broadcast
            # we need to bind to specific ip: case with multiple interfaces
            # unicast is being sent for each interface over same outgoing port when no bind
            # that generates unwanted auto-discovery machines entries
            src_ip = ip
            dest_addr = (bind_server, PORT_OUT)
            dest_type = 'unicast'
        else:
            src_ip = ip
            dest_addr = srv_addr_bcast
            dest_type = 'broadcast'
            send_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        send_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # src port does not have to be specified, this is a sending socket, we care
        # only about dst port, additionally linux discards src port when socket is bind to ip
        src_addr = (src_ip, 0)
        send_sock.bind(src_addr)

        # request IP
        data = "give me ip;%s;%s;%s" % (mac, hostname, bind_server)
        data = ensure_bytes(data, "ascii")
        log.info("Sending %s request from %s (mac: %s) to %s.", dest_type, src_addr, mac, dest_addr)
        send_sock.sendto(data, dest_addr)
        log.info("Sending message '%s'..." % data)
    finally:
        send_sock.close()


def connect_to_server():
    recv_addr = ('', PORT_IN)
    recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    recv_sock.bind(recv_addr)
    recv_sock.settimeout(TIMEOUT)

    try:
        bind_file = get_bind_file()
        my_ip = ''

        log.info("Searching for server's address...")
        t0 = 0
        cnt = 0
        while not my_ip:
            ip_list = checks.get_ip_list()
            cnt += 1
            bind_server = get_bind_server()
            for ip in ip_list:
                mac = checks.get_hw_address(ip)
                if not mac:
                    log.info("No MAC address found for %s ip. (Returned %s)" % (ip, mac))
                    continue

                srv_addr_bcast = BCAST_ADDR
                if cnt % 2 == 0 and ip.startswith("192.168"):
                    srv_addr_bcast = (".".join(ip.split('.')[:3] + ['255']), PORT_OUT)

                try:
                    send_get_addr_packet(ip, mac, socket.gethostname(), bind_server, srv_addr_bcast)

                    # receive IP
                    data, serv_addr = recv_sock.recvfrom(512)
                    data = data if PY2 else data.decode('ascii')
                    my_ip = ip
                    log.info("got response, server address %s, data: '%s'", serv_addr, data[:25])
                    break
                except socket.timeout:
                    log.debug("Receive timeout. No server connection on %s ip. Retrying..." % ip)
                    continue
                except KeyboardInterrupt:
                    log.exception("Interrupted by user")
                    raise
                except:
                    log.exception("unexpected exception")
                    continue
                finally:
                    t0 += TIMEOUT

            # Broadcast after second unsuccessful try
            if not my_ip and cnt % 3 == 0:
                unbind_server()  # Delete ip from file if our old server do not respond
            if not my_ip and t0 > NETWORK_TIMEOUT * 60:
                log.debug("Get server address timeout.")
                unbind_server()  # Delete ip from file if our old server do not respond
                return None
            if not ip_list:
                time.sleep(1)
                t0 += 1

        addr = {}
        for key, value in re.findall(r"(\w+):(.*)", data):
            addr[key.strip()] = value.strip()
        if 'ip' in addr:
            addr['ip'] = serv_addr[0]
        file_data = ""
        fragile_fields = ['smb_password', 'smb_user', 'db']  # security
        for item in addr:
            if item not in fragile_fields:
                file_data += str(item) + ': ' + str(addr[item]) + '\n'

        os.environ[AGENT_BERTA_IP_ENV] = my_ip
        f = open(bind_file, 'w')
        # write to file address of berta instance, then use it as bind address
        f.write(file_data)
        f.close()
        # log('Client stopped.')

        return data
    finally:
        recv_sock.close()


def _send_http_request(url, data):
    data = json.dumps(data)
    data = data.encode('utf-8')
    req = urllib.request.Request(url=url, data=data, headers={'content-type': 'application/json'})
    resp = None

    # Codes description:
    #     -2 - 'Name or service not known'
    #     32 - 'Broken pipe'
    #     100 - 'Network is down'
    #     101 - 'Network is unreachable'
    #     110 - 'Connection timed out'
    #     111 - 'Connection refused'
    #     112 - 'Host is down'
    #     113 - 'No route to host'
    #     10053 - 'An established connection was aborted by the software in your host machine'
    #     10054 - An existing connection was forcibly closed by the remote host
    #     10060 - 'Connection timed out'
    #     10061 - 'No connection could be made because the target machine actively refused it'
    CONNECTION_ERRORS = [-2, 32, 100, 101, 110, 111, 112, 113, 10053, 10054, 10060, 10061]

    while resp is None:
        try:
            with urllib.request.urlopen(req) as f:
                resp = f.read().decode('utf-8')
        except KeyboardInterrupt:
            raise
        # except socket.error as e:
        #     if e.errno in CONNECTION_ERRORS:
        #         # TODO: just warn and sleep for a moment
        except urllib.error.URLError as e:
            if e.__context__ and e.__context__.errno in CONNECTION_ERRORS:
                log.warn('connection problem to %s: %s, trying one more time in 5s', url, str(e))
                time.sleep(5)
            else:
                raise
        except ConnectionError as e:
            log.warn('connection problem to %s: %s, trying one more time in 5s', url, str(e))
            time.sleep(5)
        except:
            log.exception('some problem with connecting to server to %s', url)
            log.info('trying one more time in 5s')
            time.sleep(5)

    resp = json.loads(resp)
    return resp


class Server():
    def __init__(self):
        self.srv_addr = config.get('server')
        self.checks_num = 0
        self.last_check = datetime.datetime.now()
        self.my_addr = "server"


    def check_server(self):
        current_addr = self.srv_addr
        self.checks_num += 1
        if self.checks_num > 15 or (datetime.datetime.now() - self.last_check > datetime.timedelta(seconds=60 * 5)):
            self.srv_addr = None
            self.checks_num = 0

        if self.srv_addr is None:
            srv_addr = self._get_srv_data()
        else:
            srv_addr = None

        if srv_addr is not None and srv_addr != current_addr:
            self.srv_addr = srv_addr

        return self.srv_addr, upgrade_required

        config.merge(new_cfg)

    def _get_srv_addr(self):
        pass

    def _ensure_srv_address(self):
        if self.srv_addr is None:
            self._establish_connection()

    def _establish_connection(self):
        raise NotImplementedError

    def get_job(self):
        self._ensure_srv_address()

        request = {'address': self.my_addr, 'msg': 'get-job'}

        response = _send_http_request(self.srv_addr, request)

        if 'cfg' in response:
            config.merge(response['cfg'])

        if 'job' in response:
            return response['job']

        return {}

    def report_step_result(self, job_id, step_idx, result):
        request = {'address': self.my_addr,
                   'msg': 'step-result',
                   'job_id': job_id,
                   'step_idx': step_idx,
                   'result': result}

        response = _send_http_request(self.srv_addr, request)

        if 'cfg' in response:
            config.merge(response['cfg'])

        return {}

    def in_progres(self):
        pass

    def dispatch_tests(self, job_id, step_idx, tests):
        request = {'address': self.my_addr,
                   'msg': 'dispatch-tests',
                   'job_id': job_id,
                   'step_idx': step_idx,
                   'tests': tests}

        response = _send_http_request(self.srv_addr, request)

        if 'cfg' in response:
            config.merge(response['cfg'])

        return response
