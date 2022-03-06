require 'json'
require 'date'

# tools versions
NODE_VER = 'v16.13.1'
OPENAPI_GENERATOR_VER = '5.3.0'
HELM_VER = 'v3.7.2'
DOCKER_COMPOSE_VER = '2.2.2'

# Check host OS
UNAME=`uname -s`

case UNAME.rstrip
  when "Darwin"
    sysname = "Darwin"
    sysnamel = "darwin"
  when "Linux"
    sysname = "Linux"
    sysnamel = "linux"
  else
    puts "ERROR: Unknown/unsupported OS: %s" % UNAME
    fail
  end

TOOLS_DIR = File.expand_path('tools')
ENV['PATH'] = "#{TOOLS_DIR}/node-#{NODE_VER}-#{sysnamel}-x64/bin:#{ENV['PATH']}"
NPX = "#{TOOLS_DIR}/node-#{NODE_VER}-#{sysnamel}-x64/bin/npx"
NG = File.expand_path('ui/node_modules/.bin/ng')
OPENAPI_GENERATOR = "#{TOOLS_DIR}/swagger-codegen-cli-#{OPENAPI_GENERATOR_VER}.jar"
SWAGGER_FILE = File.expand_path("server/kraken/server/swagger.yml")
HELM = "#{TOOLS_DIR}/helm"

DOCKER_COMPOSE = "#{TOOLS_DIR}/docker-compose-#{DOCKER_COMPOSE_VER}"
ENV['DOCKER_BUILDKIT']='1'
ENV['COMPOSE_DOCKER_CLI_BUILD']='1'

kk_ver = ENV['kk_ver'] || '0.0'
ENV['KRAKEN_VERSION'] = kk_ver
KRAKEN_VERSION_FILE = File.expand_path("kraken-version-#{kk_ver}.txt")

helm_dest = '.'
if ENV['helm_dest']
  helm_dest = ENV['helm_dest']
end

LOCALHOST_IP=ENV['LOCALHOST_IP'] || '192.168.0.89'
CLICKHOUSE_ADDR="#{LOCALHOST_IP}:9001"
MINIO_ADDR="#{LOCALHOST_IP}:9999"
MINIO_ACCESS_KEY='UFSEHRCFU4ACUEWHCHWU'
MINIO_SECRET_KEY='HICSHuhIIUhiuhMIUHIUhGFfUHugy6fGJuyyfiGY'

file DOCKER_COMPOSE do
  sh "mkdir -p #{TOOLS_DIR}"
  sh "wget -nv https://github.com/docker/compose/releases/download/v#{DOCKER_COMPOSE_VER}/docker-compose-#{sysname}-x86_64 -O #{DOCKER_COMPOSE}"
  sh "chmod a+x #{DOCKER_COMPOSE}"
end

# prepare env
file './venv/bin/python3' do
  sh 'python3 -m venv venv'
  sh './venv/bin/pip install -U pip'
  sh './venv/bin/pip install -r requirements.txt'
end

file './agent/venv/bin/python3' do
  sh 'python3 -m venv agent/venv'
  sh './agent/venv/bin/pip install -U pip'
end

task :prepare_env => ['venv/bin/python3', './agent/venv/bin/python3'] do
  sh 'sudo DEBIAN_FRONTEND=noninteractive apt-get install -y default-jre python3-venv npm libpq-dev libpython3-dev'
  sh 'cd server && ../venv/bin/poetry install'
end

# UI
task :gen_client => [OPENAPI_GENERATOR, SWAGGER_FILE] do
  Dir.chdir('ui') do
    sh "java -jar #{OPENAPI_GENERATOR} generate  -g typescript-angular -i #{SWAGGER_FILE} -o src/app/backend --additional-properties snapshot=true,ngVersion=12.0.0,modelPropertyNaming=snake_case"
  end
end

file OPENAPI_GENERATOR do
  sh "mkdir -p #{TOOLS_DIR}"
  sh "wget -nv https://repo1.maven.org/maven2/org/openapitools/openapi-generator-cli/#{OPENAPI_GENERATOR_VER}/openapi-generator-cli-#{OPENAPI_GENERATOR_VER}.jar -O #{OPENAPI_GENERATOR}"
end

file NPX do
  sh "mkdir -p #{TOOLS_DIR}"
  Dir.chdir(TOOLS_DIR) do
    sh "wget -nv https://nodejs.org/dist/#{NODE_VER}/node-#{NODE_VER}-#{sysnamel}-x64.tar.xz -O #{TOOLS_DIR}/node.tar.xz"
    sh "tar -Jxf node.tar.xz"
  end
end

file NG => NPX do
  Dir.chdir('ui') do
    sh 'NG_CLI_ANALYTICS=false npm install'
  end
end

task :build_ui => [NG, :gen_client] do
  Dir.chdir('ui') do
    sh "sed -e 's/0\.0/#{kk_ver}/g' src/environments/environment.prod.ts.in > src/environments/environment.prod.ts"
    sh 'npx ng build --configuration production'
  end
end

task :serve_ui => [NG, :gen_client] do
  Dir.chdir('ui') do
    sh 'npx ng serve --host 0.0.0.0 --disable-host-check --proxy-config proxy.conf.json'
  end
end

task :lint_ui => [NG, :gen_client] do
  Dir.chdir('ui') do
    sh 'npm ci'
    sh 'npx ng lint'
    sh 'npx prettier --config .prettierrc --check \'**/*\''
  end
end

task :fix_ui => [NG, :gen_client] do
  Dir.chdir('ui') do
    sh 'npx ng lint --fix'
    sh 'npx prettier --config .prettierrc --write \'**/*\''
  end
end

task :lint_py do
  Dir.chdir('server') do
    sh '../venv/bin/poetry run pylint --rcfile ../pylint.rc kraken'
  end
end


# BACKEND


# TODO TODEL
#file './server/venv/bin/python3' do
#  sh 'python3 -m venv server/venv'
#  sh './server/venv/bin/pip install -U pip'
#end

# TODO TODEL
#def setup_py_develop
#  Dir.chdir('server') do
#    sh './venv/bin/pip install -r requirements.txt'
#    sh './venv/bin/python3 setup.py develop --upgrade'
#  end
#end

file KRAKEN_VERSION_FILE do
  sh 'rm -f kraken-version-*.txt'
  sh "touch #{KRAKEN_VERSION_FILE}"
end

file 'server/kraken/version.py' => KRAKEN_VERSION_FILE do
  sh "echo \"version = '#{kk_ver}'\" > server/kraken/version.py"
end

task :run_server => 'server/kraken/version.py' do
  sh 'cp dot.env .env'
  Dir.chdir('server') do
    sh "KRAKEN_CLICKHOUSE_ADDR=#{CLICKHOUSE_ADDR} MINIO_ACCESS_KEY='#{MINIO_ACCESS_KEY}' MINIO_SECRET_KEY='#{MINIO_SECRET_KEY}' ../venv/bin/poetry run python -m kraken.server.server"
  end
end

task :run_scheduler => 'server/kraken/version.py' do
  Dir.chdir('server') do
    sh "KRAKEN_CLICKHOUSE_ADDR=#{CLICKHOUSE_ADDR} ../venv/bin/poetry run kkscheduler"
  end
end

file './agent/venv/bin/kkagent' => './agent/venv/bin/python3' do
  Dir.chdir('agent') do
    sh './venv/bin/pip install -r requirements.txt'
    sh './venv/bin/python3 setup.py develop --upgrade'
  end
end

task :run_agent => ['./agent/venv/bin/kkagent', :build_agent] do
  sh 'cp server/kraken/server/consts.py agent/kraken/agent/'
  sh 'cp server/kraken/server/logs.py agent/kraken/agent/'
  sh 'rm -rf /tmp/kk-jobs/ /opt/kraken/*'
  sh 'cp agent/kkagent agent/kktool /opt/kraken'
  sh "LANGUAGE=en_US:en LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 KRAKEN_CLICKHOUSE_ADDR=#{CLICKHOUSE_ADDR} KRAKEN_MINIO_ADDR=#{MINIO_ADDR} /opt/kraken/kkagent run -d /tmp/kk-jobs -s http://localhost:8080 --no-update"
end

task :run_agent_in_docker do
  Rake::Task["build_agent"].invoke
  Dir.chdir('agent') do
    sh 'docker build -f docker-agent.txt -t kkagent .'
  end
  sh "docker run --rm -ti  -v /var/run/docker.sock:/var/run/docker.sock -v /var/snap/lxd/common/lxd/unix.socket:/var/snap/lxd/common/lxd/unix.socket -v `pwd`/agent:/agent -e KRAKEN_AGENT_SLOT=7 -e KRAKEN_CLICKHOUSE_ADDR=#{CLICKHOUSE_ADDR} -e KRAKEN_MINIO_ADDR=#{MINIO_ADDR} kkagent /opt/kraken/kkagent run -s http://#{LOCALHOST_IP}:8080"
end

task :run_agent_in_lxd_all do
#  Rake::Task["build_agent"].invoke
  Dir.chdir('agent') do
    systems = [
      ['images:ubuntu/focal/amd64', 'u20'],
      ['images:fedora/34/amd64', 'f34'],
#      ['images:centos/7/amd64', 'c7'], TODO: problem with locales
#      ['images:centos/8/amd64', 'c8'], TODO: problem with sudo which hangs
      ['images:debian/buster/amd64', 'd10'],
      ['images:debian/bullseye/amd64', 'd11'],
#      ['images:opensuse/15.3/amd64', 's15'], TODO: problem with network (wicked)
#      ['images:rockylinux/8/amd64', 'rl8'], # TODO: problem with sudo which hangs
    ]

#    sh 'lxc network delete kk-net || true'
#    sh 'lxc network create kk-net || true'
#    sh "sleep 10"
    systems.each do |sys, name|
      cntr_name = "kk-agent-#{name}"
      sh "lxc stop #{cntr_name} || true"
      sh "lxc delete #{cntr_name} || true"
      sh "lxc launch #{sys} #{cntr_name}"
      sh "lxc network attach kk-net #{cntr_name}"
      sh "sleep 5"
      if sys.include?('centos/7') or sys.include?('debian/buster')
        sh "lxc exec #{cntr_name} -- dhclient"
      end
      if sys.include?('centos') or sys.include?('rocky')
        sh "lxc exec #{cntr_name} -- yum install -y python3 sudo wget which"
      end
      if sys.include?('fedora')
        sh "lxc exec #{cntr_name} -- dnf install -y wget"
      end
      if sys.include?('debian')
        sh "lxc exec #{cntr_name} -- apt-get update"
        sh "lxc exec #{cntr_name} -- apt-get install -y curl python3 sudo wget"
      end
      if sys.include?('opensuse/15')
        sh "lxc exec #{cntr_name} -- zypper install -y curl python3 sudo system-group-wheel"
      end
      if sys.include?('ubuntu')
        sh "lxc exec #{cntr_name} -- apt install -y wget"
      end
      #sh "lxc file push agent/kkagent #{cntr_name}/root/kkagent"
      #sh "lxc exec #{cntr_name} -- ./kkagent install -s http://#{LOCALHOST_IP}:8080"
      sh "lxc exec #{cntr_name} -- wget http://#{LOCALHOST_IP}:4200/install/kraken-agent-install.sh"
      sh "lxc exec #{cntr_name} -- chmod a+x kraken-agent-install.sh"
      #sh "lxc exec #{cntr_name} -- bash -c 'LC_ALL=en_US.utf8 LANG=en_US.utf8 ./kraken-agent-install.sh'"
      sh "lxc exec #{cntr_name} -- ./kraken-agent-install.sh"
      sh "lxc exec #{cntr_name} -- journalctl -u kraken-agent.service"
      # sh "lxc exec #{cntr_name} -- journalctl -f -u kraken-agent.service'
    end
  end
end

task :run_agent_in_lxd do
  Rake::Task["build_agent"].invoke
  Dir.chdir('agent') do
    systems = [
      ['ubuntu:20.04', 'u20'],
    ]

    sh 'lxc network delete kk-net || true'
    sh 'lxc network create kk-net || true'
    systems.each do |sys, name|
      cntr_name = "kk-agent-#{name}"
      sh "lxc stop #{cntr_name} || true"
      sh "lxc delete #{cntr_name} || true"
      sh "lxc launch #{sys} #{cntr_name}"
      sh "lxc config set #{cntr_name} security.nesting true"
      sh "lxc network attach kk-net #{cntr_name}"
      sh "lxc exec #{cntr_name} -- sleep 5"
      if sys.include?('centos/7') or sys.include?('debian/buster')
        sh "lxc exec #{cntr_name} -- dhclient"
      end
      if sys.include?('centos')
        sh "lxc exec #{cntr_name} -- yum install -y python3 sudo"
      end
      if sys.include?('debian')
        sh "lxc exec #{cntr_name} -- apt-get update"
        sh "lxc exec #{cntr_name} -- apt-get install -y curl python3 sudo"
      end
      if sys.include?('opensuse/15.2')
        sh "lxc exec #{cntr_name} -- zypper install -y curl python3 sudo system-group-wheel"
      end

      sh "lxc exec #{cntr_name} -- apt-get update"
      sh "lxc exec #{cntr_name} -- apt-get install -y python3-docker docker.io"

      sh "lxc exec #{cntr_name} -- curl -o agent http://#{LOCALHOST_IP}:8080/install/agent"
      sh "lxc exec #{cntr_name} -- chmod a+x agent"
      sh "lxc exec #{cntr_name} -- ./agent install -s http://#{LOCALHOST_IP}:8080"
      #sh "lxc exec #{cntr_name} -- journalctl -u kraken-agent.service"
      sh "lxc exec #{cntr_name} -- journalctl -f -u kraken-agent.service"
    end
  end
end

task :run_rq => './server/kraken/version.py' do
  sh 'cp dot.env .env'
  Dir.chdir('server') do
    sh "KRAKEN_CLICKHOUSE_ADDR=#{CLICKHOUSE_ADDR} KRAKEN_MINIO_ADDR=#{MINIO_ADDR} MINIO_ACCESS_KEY='#{MINIO_ACCESS_KEY}' MINIO_SECRET_KEY='#{MINIO_SECRET_KEY}' ../venv/bin/poetry run kkrq"
  end
end

task :run_qneck => './server/kraken/version.py' do
  Dir.chdir('server') do
    sh "KRAKEN_CLICKHOUSE_ADDR=#{CLICKHOUSE_ADDR} KRAKEN_MINIO_ADDR=#{MINIO_ADDR} MINIO_ACCESS_KEY='#{MINIO_ACCESS_KEY}' MINIO_SECRET_KEY='#{MINIO_SECRET_KEY}' ../venv/bin/poetry run kkqneck"
  end
end

task :run_planner => 'server/kraken/version.py' do
  Dir.chdir('server') do
    sh "KRAKEN_CLICKHOUSE_ADDR=#{CLICKHOUSE_ADDR} ../venv/bin/poetry run kkplanner"
  end
end

task :run_watchdog => 'server/kraken/version.py' do
  Dir.chdir('server') do
    sh "KRAKEN_CLICKHOUSE_ADDR=#{CLICKHOUSE_ADDR} ../venv/bin/poetry run kkwatchdog"
  end
end

file './venv/bin/shiv' => ['./venv/bin/python3', 'requirements.txt'] do
    sh './venv/bin/pip install -r requirements.txt'
end

task :build_agent => './venv/bin/shiv' do
  sh 'cp server/kraken/server/consts.py agent/kraken/agent/'
  sh 'cp server/kraken/server/logs.py agent/kraken/agent/'
  Dir.chdir('agent') do
    sh 'rm -rf dist-agent'
    sh '../venv/bin/pip install --target dist-agent -r requirements.txt'
    sh '../venv/bin/pip install --target dist-agent --upgrade .'
    sh "../venv/bin/shiv --site-packages dist-agent --compressed -p '/usr/bin/env python3' -o kkagent -c kkagent"
    sh 'rm -rf dist-tool'
    sh '../venv/bin/pip install --target dist-tool -r reqs-tool.txt'
    sh '../venv/bin/pip install --target dist-tool --upgrade .'
    sh "../venv/bin/shiv --site-packages dist-tool --compressed -p '/usr/bin/env python3' -o kktool -c kktool"
  end
  sh "cp agent/kkagent agent/kktool server/"
end

task :build_py => [:build_agent, 'server/kraken/version.py']

task :clean_backend do
  sh 'rm -rf venv'
  sh 'rm -rf server/venv'
  sh 'rm -rf agent/venv'
end

task :build_all => [:build_py, :build_ui]

task :server_ut do
  at_exit {
    sh "docker rm -f -v kk-ut-pgsql"
  }
  sh "docker run --name kk-ut-pgsql -d -p 15432:5432 -e POSTGRES_DB=kkut -e POSTGRES_USER=kkut -e POSTGRES_PASSWORD=kkut postgres:11 && sleep 5"

  ENV['POSTGRES_URL'] = "postgresql://kkut:kkut@localhost:15432/"
  Dir.chdir('server') do
    sh "../venv/bin/poetry run pytest -s -r A -vv #{ENV['test']}"
  end
end

task :agent_ut do
  Dir.chdir('agent') do
    sh "./venv/bin/pytest -s -v"
  end
end

# DATABASE
DB_URL = "postgresql://kraken:kk123@localhost:5433/kraken"
task :db_up do
  Dir.chdir('server/kraken/migrations') do
    sh "KRAKEN_DB_URL=#{DB_URL} ../../../venv/bin/poetry run alembic -c alembic.ini upgrade head"
  end
end

task :db_down do
  Dir.chdir('server/kraken/migrations') do
    sh "KRAKEN_DB_URL=#{DB_URL} ../../../venv/bin/poetry run alembic -c alembic.ini downgrade -1"
  end
end

task :db_init do
  Dir.chdir('server/kraken/migrations') do
    sh "KRAKEN_DB_URL=#{DB_URL} ../../../venv/bin/poetry run python apply.py"
  end
end

task :db_new_revision do
  Dir.chdir('server/kraken/migrations') do
    comment = ENV['comment']
    sh "KRAKEN_DB_URL=#{DB_URL} ../../../venv/bin/poetry run alembic revision -m '#{comment}' --autogenerate"
  end
end


# DOCKER Support

task :docker_srv_builder do
  Dir.chdir('server') do
    sh 'docker build -f docker-builder.txt -t krakenci/srv-builder .'
    sh 'docker push krakenci/srv-builder:latest'
  end
end

task :docker_srv_base do
  Dir.chdir('server') do
    sh 'docker build -f docker-base.txt -t krakenci/srv-base .'
    sh 'docker push krakenci/srv-base:latest'
  end
end


# DOCKER

task :docker_up => [DOCKER_COMPOSE, :build_all] do
  sh "cp dot.env .env"
  sh "#{DOCKER_COMPOSE} down"
  sh "#{DOCKER_COMPOSE} build --build-arg kkver=#{kk_ver}"
  sh "#{DOCKER_COMPOSE} up"
end

task :docker_down => DOCKER_COMPOSE do
  sh "#{DOCKER_COMPOSE} down -v --remove-orphans"
end

task :docker_test_up => [DOCKER_COMPOSE] do
  sh "cp dot.env .env"
  sh "cp docker-compose.yaml docker-compose-test.yaml"
  sh "sed -i -e s/kk_ver/#{kk_ver}/g docker-compose-test.yaml"
  sh "sed -i -e 's#127.0.0.1:5000#us-docker.pkg.dev/kraken-261806/kk#g' docker-compose-test.yaml"
  sh "yq e 'del(.services.*.build)' -i docker-compose-test.yaml"
  sh "yq e 'del(.services.agent.deploy)' -i docker-compose-test.yaml"
  sh "#{DOCKER_COMPOSE} -f docker-compose-test.yaml down -v"
  sh "#{DOCKER_COMPOSE} -f docker-compose-test.yaml up"
end

task :run_ch => DOCKER_COMPOSE do
  sh "#{DOCKER_COMPOSE} up clickhouse clickhouse-proxy"
end

task :run_minio => DOCKER_COMPOSE do
  sh "#{DOCKER_COMPOSE} up minio"
end


task :build_chp => DOCKER_COMPOSE do
  sh "#{DOCKER_COMPOSE} build --build-arg kkver=#{kk_ver} clickhouse-proxy"
end

task :run_chcli do
  sh 'docker run -it --rm --network kraken_db_net --link kraken_clickhouse_1:clickhouse-server yandex/clickhouse-client --host clickhouse-server'
end

task :run_pgsql do
  sh 'docker run --rm -p 5433:5432 -e POSTGRES_USER=kraken -e POSTGRES_PASSWORD=kk123 -e POSTGRES_DB=kraken postgres:11'
end

task :run_redis do
  sh 'docker run --rm -p 6379:6379 redis:alpine'
end

task :build_docker_deploy => DOCKER_COMPOSE do
  sh "#{DOCKER_COMPOSE} -f docker-compose-swarm.yaml config > docker-compose-swarm-deploy.yaml"
end

task :build_docker => DOCKER_COMPOSE do
  sh 'cp dot.env .env'

  # generate docker-compose config for installing kraken under the desk and for pushing images to docker images repository
  sh "cp docker-compose.yaml kraken-docker-compose-#{kk_ver}-tmp.yaml"
  sh "sed -i -e s/kk_ver/#{kk_ver}/g kraken-docker-compose-#{kk_ver}-tmp.yaml"
  sh "sed -i -e 's#127.0.0.1:5000#us-docker.pkg.dev/kraken-261806/kk#g' kraken-docker-compose-#{kk_ver}-tmp.yaml"
  sh "cp agent/kkagent agent/kktool server/"

  # build images, in case of server everything is build in containers
  if ENV['reuse'] == 'true'
    flags = ''
  else
    flags = '--force-rm --no-cache --pull'
  end
  sh "#{DOCKER_COMPOSE} -f kraken-docker-compose-#{kk_ver}-tmp.yaml build #{flags} --build-arg kkver=#{kk_ver}"
end

task :publish_docker => DOCKER_COMPOSE do
  Rake::Task["build_docker"].invoke

  # push built images
  sh "#{DOCKER_COMPOSE} -f kraken-docker-compose-#{kk_ver}-tmp.yaml push"
  # strip build: section - release docker-compose file should use build images directly
  sh "yq e 'del(.services.*.build)' -i kraken-docker-compose-#{kk_ver}-tmp.yaml"
  # strip deploy: section - deploy is used only in swarm
  sh "yq e 'del(.services.*.deploy)' -i kraken-docker-compose-#{kk_ver}-tmp.yaml"
  # validate final docker compose file
  sh "#{DOCKER_COMPOSE} -f kraken-docker-compose-#{kk_ver}-tmp.yaml config > /dev/null"
  sh "mv kraken-docker-compose-#{kk_ver}-tmp.yaml kraken-docker-compose-#{kk_ver}.yaml"
end

task :publish_docker_aws do
  names = ['kkserver:',
           'kkcontroller:',
           'kkrq:',
           'kkagent:',
           'kkui:',
           'clickhouse-server:20.11.4.13.',
           'kkchproxy:']
  names.each do |name|
    sh "docker tag us-docker.pkg.dev/kraken-261806/kk/#{name}#{kk_ver} public.ecr.aws/kraken-ci/#{name}#{kk_ver}"
    sh "docker push public.ecr.aws/kraken-ci/#{name}#{kk_ver}"
  end
end

task :prune_gcp_artifacts do
  ago = (Date.today - 20)
  sh "gcloud artifacts docker images list us-docker.pkg.dev/kraken-261806/kk --include-tags --filter='tags!~released AND createTime<=#{ago}' --format='value[separator=\"@\"](package,version)' | xargs -n1 gcloud artifacts docker images delete --quiet --delete-tags --async"
end

task :show_old_gcp_artifacts do
  ago = (Date.today - 20)
  sh "gcloud artifacts docker images list us-docker.pkg.dev/kraken-261806/kk --include-tags --filter='tags!~released AND createTime<=#{ago}'"
end

task :mark_images_as_published do
  names = ['kkserver:',
           'kkcontroller:',
           'kkrq:',
           'kkagent:',
           'kkui:',
           'clickhouse-server:20.11.4.13.',
           'kkchproxy:']
  names.each do |name|
    sh "gcloud artifacts docker tags add us-docker.pkg.dev/kraken-261806/kk/#{name}#{kk_ver} us-docker.pkg.dev/kraken-261806/kk/#{name}#{kk_ver}-released"
  end
end


task :compose_to_swarm => DOCKER_COMPOSE do
  sh 'cp lab.env .env'
  sh 'cp docker-compose.yaml docker-compose-swarm-tmp.yaml'
  sh "yq e 'del(.services.*.depends_on)'                         -i docker-compose-swarm-tmp.yaml"
  sh "yq e 'del(.services.*.build)'                              -i docker-compose-swarm-tmp.yaml"
#  sh "yq e 'del(.services.*.networks)'                           -i docker-compose-swarm-tmp.yaml"
#  sh "yq e 'del(.networks)'                                      -i docker-compose-swarm-tmp.yaml"
  sh "yq e '.services.ui.ports = [\"8888:80\"]'                  -i docker-compose-swarm-tmp.yaml"
  sh "yq e 'del(.services.clickhouse.ports)'                     -i docker-compose-swarm-tmp.yaml"
  sh "yq e '.services.agent.environment = .services.agent.environment + \"KRAKEN_AGENT_SLOT={{.Task.Slot}}\"' -i docker-compose-swarm-tmp.yaml"
  sh "yq eval-all 'select(fileIndex == 0) * select(filename == \"docker-compose-swarm-patch.yaml\")' docker-compose-swarm-tmp.yaml docker-compose-swarm-patch.yaml > docker-compose-swarm.yaml"
  sh 'rm docker-compose-swarm-tmp.yaml'
  sh "#{DOCKER_COMPOSE} -f docker-compose-swarm.yaml config > kraken-docker-stack-#{kk_ver}.yaml"
  sh 'rm docker-compose-swarm.yaml'
  sh "sed -i -e s/kk_ver/#{kk_ver}/g kraken-docker-stack-#{kk_ver}.yaml"
  sh "yq e '.version = \"3.6\"'                                  -i kraken-docker-stack-#{kk_ver}.yaml"
end

task :run_swarm => :build_docker_deploy do
  sh 'docker stack deploy --with-registry-auth -c docker-compose-swarm-deploy.yaml kraken'
end

task :run_portainer do
  sh 'docker volume create portainer_data'
  sh 'docker run -d -p 8000:8000 -p 9000:9000 -v /var/run/docker.sock:/var/run/docker.sock -v portainer_data:/data portainer/portainer'
end

file HELM do
  sh "mkdir -p #{TOOLS_DIR}"
  Dir.chdir(TOOLS_DIR) do
    sh "wget -nv https://get.helm.sh/helm-#{HELM_VER}-#{sysnamel}-amd64.tar.gz"
    sh "tar xzf helm-#{HELM_VER}-#{sysnamel}-amd64.tar.gz #{sysnamel}-amd64/helm"
    sh "mv #{sysnamel}-amd64/helm #{HELM}"
    sh "rm -rf #{sysnamel}-amd64"
  end
end

task :helm_pkg => HELM do
  sh "#{HELM} lint ./helm --strict"
  sh "#{HELM} package ./helm --app-version #{kk_ver} --version #{kk_ver}.0 -d #{helm_dest}"
end

task :helm_deploy => :helm_pkg do
  sh "#{HELM} upgrade kk --install --create-namespace --namespace kk --debug --wait --set access.external_ips={`minikube ip`} --set access.method='external-ips' kraken-ci-#{kk_ver}.0.tgz"
end

task :helm_upload do
  sh "#{HELM} repo index #{helm_dest} --url https://kraken.ci/helm-repo/charts"
  Dir.chdir(helm_dest) do
    sh "git add kraken-ci-#{kk_ver}.0.tgz"
    sh "git commit -am 'added new kraken version #{kk_ver}'"
    sh "git push"
  end
end

task :helm_release do
  Rake::Task['helm_pkg'].invoke
  Rake::Task['helm_upload'].invoke
end

task :deploy_lab => ['./venv/bin/python3'] do
  # prepare docker stack config
  Rake::Task["compose_to_swarm"].invoke

  # deploy to lab.kraken.ci
  sh "./venv/bin/fab -e -H #{ENV['host']} upgrade --kk-ver #{kk_ver}"
end

task :github_release do
  curl_opts = '--retry 3 --silent --location'

  # create release entry
  sh "curl -H \"Authorization: token $GITHUB_TOKEN\"  #{curl_opts} --fail --data '{\"tag_name\": \"v#{kk_ver}\"}' -o github-release-#{kk_ver}.json  https://api.github.com/repos/kraken-ci/kraken/releases"

  # upload artifacts
  file = File.read("github-release-#{kk_ver}.json")
  rel = JSON.parse(file)
  upload_url = rel['upload_url'].chomp('{?name,label}')
  sh "curl -H \"Authorization: token $GITHUB_TOKEN\" -H 'Content-Type:text/plain' #{curl_opts} --data-binary @kraken-docker-compose-#{kk_ver}.yaml '#{upload_url}?name=kraken-docker-compose-#{kk_ver}.yaml'"
  sh "curl -H \"Authorization: token $GITHUB_TOKEN\" -H 'Content-Type:text/plain' #{curl_opts} --data-binary @dot.env '#{upload_url}?name=kraken-#{kk_ver}.env'"
  sh "rm -f github-release-#{kk_ver}.json"

  # generate and set release notes
  ENV['GREN_GITHUB_TOKEN'] = ENV['GITHUB_TOKEN']
  Dir.chdir('ui') do
    sh 'npm install github-release-notes'
  end
  sh './ui/node_modules/.bin/gren release --override'
end

task :release_deploy do
  Rake::Task["build_all"].invoke
  Rake::Task["publish_docker"].invoke
#  Rake::Task["github_release"].invoke
  Rake::Task["deploy_lab"].invoke
end
