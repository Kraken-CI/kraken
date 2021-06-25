import time
from fabric import task


def banner(txt):
    print("========================== %s ==========================" % txt)



def upload(c, kk_ver):
    banner("upload")
    bld_dir = 'kk-%s' % kk_ver
    c.run('rm -rf %s' % bld_dir)
    c.run('mkdir %s' % bld_dir)
    c.put('kraken-docker-stack-%s.yaml' % kk_ver, bld_dir)


def redeploy(c, kk_ver):
    c.run('docker service scale kraken_agent=0')
    c.run('docker service scale kraken_ui=0')
    c.run('docker service scale kraken_server=0')
    c.run('docker service scale kraken_controller=0')
    c.run('docker service scale kraken_rq=0')
    c.run('docker service scale kraken_redis=0')
    c.run('docker service scale kraken_clickhouse-proxy=0')
    c.run('docker service scale kraken_clickhouse=0')
    c.run('docker service scale kraken_minio=0')
    c.run('docker service ls')

    # backup the old backup
    with c.cd('backup'):
        c.run('rm -f db-vol.prev.tar.gz db-sql.prev.gz')
        c.run('mv db-vol.current.tar.gz db-vol.prev.tar.gz')
        c.run('mv db-sql.current.gz db-sql.prev.gz')

    # dump postgresql as sql
    c.run("""bash -c "docker exec `docker ps -qf 'name=kraken_postgres'` bash -c 'export PGPASSWORD=kk123 && /usr/bin/pg_dump -U kraken kraken' | gzip -9 > ~/backup/db-sql.current.gz" """)
    c.run('ls -lh ~/backup/db-sql.current.gz')

    # dump volume with postgresql files
    c.run('docker service scale kraken_postgres=0')
    c.run("docker run --rm -v kraken_db-data:/db -v ~/backup:/backup ubuntu:20.04 bash -c 'cd /db && tar -zcf /backup/db-vol.current.tar.gz .'")
    c.run('ls -lh ~/backup/db-vol.current.tar.gz')
    c.run('ls -alh ~/backup')

    # deploy the stack
    bld_dir = 'kk-%s' % kk_ver
    with c.cd(bld_dir):
        c.run('docker stack deploy --with-registry-auth -c kraken-docker-stack-%s.yaml kraken' % kk_ver)

    # do some cleanup
    c.run('docker container prune -f')
    c.run('docker image prune -a -f')
    c.run('docker builder prune -a -f')
    c.run('docker volume prune -f')

    # restart services
    c.run('docker service update --force kraken_postgres')
    c.run('docker service update --force kraken_clickhouse')
    c.run('docker service update --force kraken_clickhouse-proxy')
    c.run('docker service update --force kraken_minio')
    c.run('docker service update --force kraken_controller')
    c.run('docker service update --force kraken_server')
    c.run('docker service update --force kraken_rq')
    c.run('docker service update --force kraken_agent')
    c.run('docker service update --force kraken_ui')
    time.sleep(10)
    c.run('docker service update --force kraken_minio')


def show_state(c):
    banner("system state")
    c.run('docker service ls')
    c.run('df -h | grep /dev/xvda')
    c.run('free -m')
    c.run('top -b -n1 | head -n 10')
    c.run('ls -lh ~/backup')


@task
def upgrade(c, kk_ver):
    upload(c, kk_ver)
    redeploy(c, kk_ver)
    show_state(c)
