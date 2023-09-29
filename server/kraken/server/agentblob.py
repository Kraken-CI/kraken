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

from flask import send_file, abort, make_response

from .models import get_setting

log = logging.getLogger(__name__)


KKAGENT_DIR = os.environ.get('KKAGENT_DIR', '')


INSTALL_SCRIPT_SH = '''#!/bin/bash
set -x

KRAKEN_URL="{url}"

# check sudo
sudo -n true
if [ $? -ne 0 ]; then
    echo "error: sudo with no password is required"
    exit 1
fi

# check python3
python3 --version
if [ $? -ne 0 ]; then
    echo "error: missing python3, it is required to run Kraken agent"
    exit 1
fi

# check curl and wget
DL_TOOL=
which curl
if [ $? -ne 0 ]; then
    which wget
    if [ $? -ne 0 ]; then
        echo "error: missing curl and wget, install any of them"
        exit 1
    else
        DL_TOOL=wget
    fi
else
    DL_TOOL=curl
fi

set -e

if [ "$DL_TOOL" == "wget" ]; then
    wget -O /tmp/kkagent ${KRAKEN_URL}/bk/install/agent
else
    curl -o /tmp/kkagent ${KRAKEN_URL}/bk/install/agent
fi
chmod a+x /tmp/kkagent

export KRAKEN_CLICKHOUSE_ADDR="{clickhouse-addr}"

/tmp/kkagent install -s ${KRAKEN_URL}
rm -f /tmp/kkagent
echo 'Kraken Agent installed'
'''

# powershell Invoke-WebRequest -Uri 'http://192.168.68.113:8080/install/kraken-agent-install.bat' -OutFile kraken-agent-install.bat

INSTALL_SCRIPT_BAT = '''
<# :
@echo off
setlocal
set "POWERSHELL_BAT_ARGS=%*"
if defined POWERSHELL_BAT_ARGS set "POWERSHELL_BAT_ARGS=%POWERSHELL_BAT_ARGS:"=\"%"
endlocal & powershell -NoLogo -NoProfile -Command "$input | &{ [ScriptBlock]::Create( ( Get-Content \"%~f0\" ) -join [char]10 ).Invoke( @( &{ $args } %POWERSHELL_BAT_ARGS% ) ) }"
goto :EOF
#>

Write-Host 'Downloading Kraken Agent'

#    Set-PSDebug -Trace 2
$global:ProgressPreference = 'SilentlyContinue'

$PythonPath = Get-Command 'python.exe' | Select -ExpandProperty 'path'
#if ($PythonPath -eq "") {
#    throw "Cannot find path to Python. Please, install it."
#}
Write-Host "Path to Python: $PythonPath"

$KrakenURL = '{url}'
$KKAgentURL = "$KrakenURL/bk/install/agent"

$KKAgentPath = Join-Path $env:Temp 'kkagent'

if (Test-Path -Path $KKAgentPath -PathType Leaf) {
    Remove-Item $KKAgentPath
}

Invoke-WebRequest $KKAgentURL -OutFile $KKAgentPath
Write-Host "Downloaded Kraken Agent to $KKAgentPath"

$env:KRAKEN_CLICKHOUSE_ADDR = '{clickhouse-addr}'

$Cmd = "$KKAgentPath install -s $KrakenURL"
Write-Host "Invoke cmd: $PythonPath $Cmd"
$p = Start-Process -PassThru -NoNewWindow -Wait -FilePath $PythonPath -ArgumentList $Cmd
if ($p.ExitCode -gt 0) {
    throw "Installing Kraken Agent failed"
}

Remove-Item $KKAgentPath

Write-Host 'Kraken Agent installed'
'''


def serve_agent_blob(blob):
    if blob not in ['agent', 'tool', 'kraken-agent-install.sh', 'kraken-agent-install.bat']:
        abort(404)

    if blob.startswith('kraken-agent-install.'):
        # get and check server url
        url = get_setting('general', 'server_url')
        if not url:
            abort(500, 'Cannot get server URL and put it in Kraken agent install script. ' +
                  'The URL should be set on Kraken Settings page first.')

        # get and check clickhouse addr
        clickhouse_addr = get_setting('general', 'clickhouse_addr')
        if not clickhouse_addr:
            abort(500, 'Cannot get ClickHouse address and put it in Kraken agent install script. ' +
                  'The ClickHouse address should be set on Kraken Settings page first.')

        # patch install script with url and addresses

        if blob.endswith('.bat'):
            script = INSTALL_SCRIPT_BAT
        else:
            script = INSTALL_SCRIPT_SH
        script = script.replace('{url}', url)
        script = script.replace('{clickhouse-addr}', clickhouse_addr)

        resp = make_response(script)

        # add a filename
        if blob.endswith('.bat'):
            resp.headers.set("Content-Type", "application/x-bat")
        else:
            resp.headers.set("Content-Type", "application/x-sh")
        resp.headers.set("Content-Disposition", "attachment", filename=blob)
        return resp

    p = os.path.join(KKAGENT_DIR, 'kk' + blob)
    return send_file(p)
