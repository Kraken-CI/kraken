#!/usr/bin/env python3

# Copyright 2020-2023 The Kraken Authors
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

import sys
import logging
import platform

import click
import pkg_resources

from . import logs
from . import agent
from . import config
from . import sysutils
from . import install as inst


log = logging.getLogger('agent')


def _intro():
    ver = platform.python_version_tuple()
    major = int(ver[0])
    minor = int(ver[1])
    if major == 2 or minor < 7:
        print('Kraken Agent requires Python version 3.7 or newer, current is %s' % platform.python_version())
        sys.exit(1)

    logs.setup_logging('agent')
    kraken_version = pkg_resources.get_distribution('kraken-agent').version
    log.info('Starting Kraken Agent, version %s', kraken_version)
    log.info('using Python version %s', platform.python_version())


def _load_cfg(**kwargs):
    config.set_config(kwargs)


@click.group()
def main():
    'Kraken Agent'
    #print('missing command - please, provide one of commands: run, install, check-integrity')
    #sys.exit(1)


@click.command()
@click.option('-s', '--server', envvar='KRAKEN_SERVER_ADDR', required=True, help='Server URL')
@click.option('-d', '--data-dir', envvar='KRAKEN_DATA_DIR', default=sysutils.get_default_data_dir(), help='Directory for presistent data')
@click.option('-t', '--tools-dirs', envvar='KRAKEN_TOOLS_DIR', help='List of tools directories')
@click.option('-c', '--clickhouse-addr', envvar='KRAKEN_CLICKHOUSE_ADDR', help='ClickHouse address (host:port)')
@click.option('--system-id', envvar='KRAKEN_SYSTEM_ID',
              help='System ID of currently running system, used in case of agents installed in VM e.g. in AWS EC2 or Azure VM')
def install(server, data_dir, tools_dirs, clickhouse_addr, system_id):
    'Install Kraken Agent in the system as a systemd service'
    _intro()
    _load_cfg(server=server,
              data_dir=data_dir,
              tools_dirs=tools_dirs,
              clickhouse_addr=clickhouse_addr,
              system_id=system_id)

    inst.install()


@click.command(short_help='Check if current installation of Kraken Agent is integral')
def check_integrity():
    'Check if current installation of Kraken Agent is integral ie. is complete and should work ok'
    _intro()
    agent.check_integrity()


@click.command()
@click.option('-s', '--server', envvar='KRAKEN_SERVER_ADDR', required=True, help='Server URL')
@click.option('-d', '--data-dir', envvar='KRAKEN_DATA_DIR', default=sysutils.get_default_data_dir(), help='Directory for presistent data')
@click.option('-t', '--tools-dirs', envvar='KRAKEN_TOOLS_DIRS', help='List of tools directories')
@click.option('-c', '--clickhouse-addr', envvar='KRAKEN_CLICKHOUSE_ADDR', help='ClickHouse address (host:port)')
@click.option('--no-update', default=False, is_flag=True, help='Do not update agent automatically (useful in agent development)')
@click.option('--system-id', envvar='KRAKEN_SYSTEM_ID',
              help='System ID of currently running system, used in case of agents spawned in containers e.g. in Kubernetes or AWS ECS'
              ' or agents installed in VM e.g. in AWS EC2 or Azure VM')
@click.option('--one-job', default=False, is_flag=True, help='If provided then the agent exits after performing one job')
def run(server, data_dir, tools_dirs, clickhouse_addr, no_update, system_id, one_job):
    'Start Kraken Agent service'
    _intro()
    _load_cfg(server=server,
              data_dir=data_dir,
              tools_dirs=tools_dirs,
              clickhouse_addr=clickhouse_addr,
              no_update=no_update,
              system_id=system_id,
              one_job=one_job)

    agent.run()


main.add_command(install)
main.add_command(check_integrity)
main.add_command(run)


if __name__ == '__main__':
    main()
