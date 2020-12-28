import os
import getpass
import datetime
from fabric import task


def missing(f):
    return not files.exists(f)

def apti(pkg):
    sudo("apt -y install %s" % pkg)

def pip(cmd):
    run("pyve/bin/pip %s" % cmd)

def banner(txt):
    print("========================== %s ==========================" % txt)



def upload(c, kk_ver):
    banner("upload")
    bld_dir = 'kk-%s' % kk_ver
    c.run('rm -rf %s' % bld_dir)
    c.run('mkdir %s' % bld_dir)
    c.put('kraken-docker-stack-%s.yaml' % kk_ver, bld_dir)


def redeploy(c, kk_ver):
    bld_dir = 'kk-%s' % kk_ver
    with c.cd(bld_dir):
        c.run('docker stack deploy --with-registry-auth -c kraken-docker-stack-%s.yaml kraken' % kk_ver)
    # do some cleanup
    c.run('docker container prune -f')
    c.run('docker image prune -a -f')
    c.run('docker service update --force kraken_postgres')
    c.run('docker service update --force kraken_clickhouse')
    c.run('docker service update --force kraken_clickhouse-proxy')
    c.run('docker service update --force kraken_minio')
    c.run('docker service update --force kraken_ui')
    c.run('docker service update --force kraken_controller')
    c.run('docker service update --force kraken_server')
    c.run('docker service update --force kraken_celery')
    c.run('docker service update --force kraken_agent')


def show_state(c):
    banner("system state")
    c.run('df -h | grep /dev/xvda')
    c.run('free -m')
    c.run('top -b -n1 | head -n 10')


@task
def upgrade(c, kk_ver):
    upload(c, kk_ver)
    redeploy(c, kk_ver)
    show_state(c)
