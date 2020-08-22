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
import re
import logging
import subprocess

log = logging.getLogger(__name__)


class SshAgent:
    def __init__(self):
        self.process = subprocess.run(['ssh-agent', '-s'], stdout=subprocess.PIPE, universal_newlines=True, check=True)

        pattern = re.compile(r'SSH_AUTH_SOCK=(?P<socket>[^;]+).*SSH_AGENT_PID=(?P<pid>\d+)', re.MULTILINE | re.DOTALL)
        match = pattern.search(self.process.stdout)
        if match is None:
            raise Exception('Could not parse ssh-agent output. It was: %s' % self.process.stdout)
        data = match.groupdict()
        self.sock = data['socket']
        self.pid = data['pid']

    def shutdown(self):
        subprocess.run(['kill', self.pid], check=True)

    def add_key(self, key):
        env = os.environ.copy()
        env['SSH_AUTH_SOCK'] = self.sock
        env['SSH_AGENT_PID'] = self.pid
        process = subprocess.run('ssh-add -', shell=True, input=bytes(key, 'ascii'), env=env)  # pylint: disable=subprocess-run-check
        if process.returncode != 0:
            raise Exception('failed to add the key')


def test():
    sa = SshAgent()
    sa.add_key('''-----BEGIN RSA PRIVATE KEY-----
MIIEogIBAAKCAQEAnJi0iKg0XAgKYUdU6sPN9reuDTrSaGdboYXFRY6p9qM7x9ll
Xzj5F+e6jP9vhDBiuigCHAfEGTAZgsKP0AW5VUAAUr5blSJDSeN20qihbpQmS4mJ
6azq0pJowZAJ28Xz91PiM6wgZ7rD45JAP2Wp/DpXC+VD/LnR+b8CN5+/3l91L5gf
T8DrH6jGikcPjz+x4IwnFoHsRdKZycvkCXoEVZChthHcJY/oy46G1uxLE7qXD6IK
;oksergejrgoijse;ogjoiegoisersdfgsde9iRIHwFyiX1b0Ob7YlgBrGttZK8S
S2pO8tRS2p8t77vGCybQruOWOE1VI7w1tS3xQwIBIwKCAQBMD6glHn/U7fZpw4+l
OoicZ9gyT8VIpzsikW5yPfrIQKgB++DH2dgS7OWU8Rjob0XlY+PEeMz2SpAMT99z
lwkferka;oerkfkerokgfkserkg;reh40FTMrYNWs60EWNWVY0H710LwjeoeE9YQ
KhC8VtnSk+3ShiQo2R5ViBtdYM4mO/8ZEVX/abw+xMgxb3kL7GHYiXY0/g0qNwP3
noKDkbra11pSBFg8Gln2c1YhoST+YM3tD0dH0ncv2xuvhVJvKQKyHtW0eOAAIsEP
FfUX4RwL7/SXJv0OH3kjcNWnRwWn+QCW84crAkmdw/NFpjSYSZA19N9aKEeJNDjj
h5YjAoGBAMxR4wDUcB0M+3jR1xs9sF'lserkg;sekgksergk;oser/cy+HTu4lg/
69e01iMA2ZO3T/nRGhyGMOy2dyra+JyXBAR77p1XIJh8icEwZKCVuqY4AhYjCwOz
onB66eDMvmVHOnWJkwO8rD/Iz5XQUKGbHZIs6vDIuw1Zy4wGTwEdAoGBAMQ0owI4
pZV9TBVzcWc3E0EN09U2H7cT907X03Yo0tdXnKJIErxRlY+XbG5i7Ha+lT62Azsm
oFEe/2iKwGuyns5xuGcPBwUlQaYbhXoyusW2x1kZtvtrfG08bSgW7zvSk0fDoSMS
rkg;oskreg;ksrafsrk;oke;krgkse34i43fAoGBAJ2eQWcKR9vlcYkW58SOrJzO
3YkVgcnMtAIONDUTrToJUR3IPAJvI6Mp/xQdycM7K4CUugnb0lCExqf6eS+wPCEG
yJW+sMKFCoRC0Kr5cjK8pe3wsScFFyAc3GVmIiJyDzgvoiAoTNb/QwyiOby2pJns
sGlzG6PODKPmL07DCb8HAoGBAIaKfmfsVEk/+ahPKTDVTwgJe1BfoLgNsOWbTyxz
w8bc/bEbeo/C6jaTuBEt4/mnQcSaENgafI9ltnOSWA9V6T0ax5cgP1P8SkYEPkUq
GawlkAKVSkYAj9XgStmpU5a8R7wuX92JFtL5Mn7a4It93VH2C8TPbFWHhjmEyyp+
i5R7AoGAVp9ksYumM2uayFnjskIyoqGZurRTgpF8go36/vCtikSl1pAFTjuNSxqS
tdcDpwcvm4e/NtYOg/WZaAsYkBn7WmYdZRtAmOLLLn6ETVuGmunqQfMH9vd1wFcE
UelohNhV7IO0xIs9+7+o/3L0mSRjzWxRDdNz7ues6OmWO5XF968=
-----END RSA PRIVATE KEY-----''')
    sa.shutdown()


if __name__ == '__main__':
    test()
