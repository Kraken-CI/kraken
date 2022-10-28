# Copyright 2021 The Kraken Authors
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

import time
import base64
import logging
import datetime

import pytz

# KUBERNETES
import kubernetes

from .. import utils
from ..models import get_setting
from .common import _create_agent

log = logging.getLogger(__name__)


def _login(api_server_url):
    # Define the bearer token we are going to use to authenticate.
    # See here to create the token:
    # https://kubernetes.io/docs/tasks/access-application-cluster/access-cluster/
    token = get_setting('cloud', 'k8s_token')
    token = base64.b64decode(token).decode()

    # Create a configuration object
    cfg = kubernetes.client.Configuration()

    # Specify the endpoint of your Kube cluster
    cfg.host = api_server_url

    # Security part.
    # In this simple example we are not going to verify the SSL certificate of
    # the remote cluster (for simplicity reason)
    cfg.verify_ssl = False
    # Nevertheless if you want to do it you can with these 2 parameters
    # configuration.verify_ssl=True
    # ssl_ca_cert is the filepath to the file that contains the certificate.
    # configuration.ssl_ca_cert="certificate"

    cfg.api_key = {"authorization": "Bearer " + token}

    namespace = get_setting('cloud', 'k8s_namespace')

    # Create a ApiClient with our config
    api_client = kubernetes.client.ApiClient(cfg)
    return api_client, namespace


def _get_core_api():
    api_server_url = get_setting('cloud', 'k8s_api_server_url')
    if api_server_url:
        api_client, namespace = _login(api_server_url)
        core_api = kubernetes.client.CoreV1Api(api_client)
    else:
        kubernetes.config.load_incluster_config()
        core_api = kubernetes.client.CoreV1Api()
        namespace = get_setting('cloud', 'k8s_namespace')
    return core_api, namespace


def check_k8s_settings():
    namespace = get_setting('cloud', 'k8s_namespace')
    if not namespace:
        return 'Kubernetes namespace is empty'

    token = get_setting('cloud', 'k8s_token')
    api_server_url = get_setting('cloud', 'k8s_api_server_url')

    if api_server_url and not token:
        return 'Kubernetes token is empty while API server URL is provided'

    if api_server_url:
        api_client, _ = _login(api_server_url)
        core_api = kubernetes.client.CoreV1Api(api_client)
        ver_api = kubernetes.client.VersionApi(api_client)
    else:
        kubernetes.config.load_incluster_config()
        core_api = kubernetes.client.CoreV1Api()
        ver_api = kubernetes.client.VersionApi()

    try:
        res = ver_api.get_code()
        log.info('k8s api %s', res)

        res = core_api.read_namespace(namespace)
        log.info('k8s namespace %s', res)

        if res.status.phase != 'Active':
            return 'Namespace %s is not Active, it is %s' % (namespace, res.status.phase)
    except Exception as ex:
        log.exception('k8s get_code exc')
        return str(ex)

    return 'ok'


def create_pods(ag, system, num,
                server_url, clickhouse_addr):
    core_api, namespace = _get_core_api()

    # prepare create_container
    cmd = 'apt-get update && apt-get install -y --no-install-recommends ca-certificates sudo wget python3'
    cmd += ' && mkdir -p /opt/kraken'
    cmd += ' && wget -O /opt/kraken/kkagent {server_url}/bk/install/agent'
    cmd += ' && wget -O /opt/kraken/kktool {server_url}/bk/install/tool'
    cmd += ' && chmod a+x /opt/kraken/kkagent /opt/kraken/kktool'
    cmd += ' && mkdir -p /tmp/kk-jobs'
    cmd += ' && /opt/kraken/kkagent run -d /tmp/kk-jobs -s {server_url} -c {clickhouse_addr}'
    cmd += ' --system-id {system_id} --one-job'
    cmd = cmd.format(server_url=server_url, clickhouse_addr=clickhouse_addr,
                     system_id=system.id)

    container = kubernetes.client.V1Container(
        image=system.name,
        name='kraken-container',
        args=['args'],
        env=[{'name': 'LC_ALL', 'value': 'C.UTF-8'},
             {'name': 'LANG', 'value': 'C.UTF-8'}],
        command=['bash', '-c', cmd])

    log.info('Created container with name: %s, image: %s and args: %s',
             container.name, container.image, container.args)

    # prepare pod template
    # prepare job
    t0 = datetime.datetime(2020, 1, 1, tzinfo=pytz.utc)
    n = datetime.datetime.now(pytz.utc)
    dt = n - t0
    dt = int(dt.total_seconds())
    series = 'kk-%d-%d-%d' % (ag.id, system.id, dt)

    triggered_pods = []
    for i in range(num):
        pod_name = '%s-%d' % (series, i)
        pod_def = kubernetes.client.V1Pod(
            spec=kubernetes.client.V1PodSpec(restart_policy="Never", containers=[container]),
            metadata=kubernetes.client.V1ObjectMeta(name=pod_name, labels={'series': series,
                                                                           'group': str(ag.id),
                                                                           'name': pod_name}))
        # start pod
        res = core_api.create_namespaced_pod(namespace, pod_def)
        triggered_pods.append(res)
        #print('POD ', res)

    log.info('group: %s, sys: %s: started k8s %d pods for %s series',
             ag.name, system.name, num, series)

    while True:
        pods = core_api.list_namespaced_pod(namespace, label_selector="series=%s" % series, pretty=True)
        #print('pods ', pods)

        # check if all started otherwise wait for pending
        all_started = True
        for pod in pods.items:
            if pod.status.phase == 'Pending':
                all_started = False
        if all_started:
            break

        time.sleep(1)
        continue

    pods = core_api.list_namespaced_pod(namespace, label_selector="series=%s" % series, pretty=True)
    for pod in pods.items:
        #print('pod ', pod.metadata.name, pod.status)
        if pod.status.phase != 'Running':
            log.error('unexpected state of pod %s: %s', pod.metadata.name, pod.status.phase)
            continue

        params = dict(name=pod.metadata.name,
                      address=pod.status.pod_ip,
                      ip_address=pod.status.host_ip,
                      extra_attrs=dict(system=system.id,
                                       series=series,
                                       instance_id=pod.metadata.name,
                                       namespace=namespace))
        a = _create_agent(params, ag)
        log.info('spawned new agent %s in K8S pod %s', a, pod.metadata.name)
        #print('PARAMS ', params)


def destroy_pod(ag, agent):  # pylint: disable=unused-argument
    namespace = agent.extra_attrs['namespace']
    pod_name = agent.extra_attrs['instance_id']

    core_api, _ = _get_core_api()

    log.info('delete K8S pod %s', pod_name)
    try:
        core_api.delete_namespaced_pod(pod_name, namespace)
    except Exception:
        log.exception('IGNORED EXCEPTION')


def pod_exists(ag, agent):  # pylint: disable=unused-argument
    namespace = agent.extra_attrs['namespace']
    pod_name = agent.extra_attrs['instance_id']

    core_api, _ = _get_core_api()

    log.info('does K8S pod %s exist', pod_name)
    try:
        core_api.read_namespaced_pod(pod_name, namespace)
    except Exception:
        log.exception('IGNORED EXCEPTION')
        return False

    return True


def cleanup_dangling_pods(ag):
    core_api, namespace = _get_core_api()

    now = utils.utcnow()

    instances = 0
    terminated_instances = 0
    assigned_instances = 0
    orphaned_instances = 0
    orphaned_terminated_instances = 0

    pods = core_api.list_namespaced_pod(namespace, label_selector="group=%s" % ag.id, pretty=True)
    for pod in pods.items:

        # if assigned to some agent then skip it
        assigned = False
        for aa in ag.agents:
            agent = aa.agent
            if agent.extra_attrs and 'instance_id' in agent.extra_attrs and agent.extra_attrs['instance_id'] == pod.metadata.name:
                assigned = True
                break
        if assigned:
            assigned_instances += 1
            continue

        # instances have to be old enough to avoid race condition with
        # case when instances are being created but not yet assigned to agents
        created_at = pod.status.start_time
        if not created_at or now - created_at < datetime.timedelta(minutes=10):
            continue

        # the instance is not terminated, not assigned, old enough
        # so delete it as it seems to be a lost instance
        log.info('terminating lost K8S pod %s', pod.metadata.name)
        orphaned_instances += 1
        try:
            core_api.delete_namespaced_pod(pod.metadata.name, namespace)
        except Exception:
            log.exception('IGNORED EXCEPTION')

        orphaned_terminated_instances += 1

    return instances, terminated_instances, assigned_instances, orphaned_instances, orphaned_terminated_instances
