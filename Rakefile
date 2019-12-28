TOOLS_DIR = File.expand_path('tools')
NODE_VER = 'node-v10.16.3-linux-x64'
ENV['PATH'] = "#{TOOLS_DIR}/#{NODE_VER}/bin:#{ENV['PATH']}"
NPX = "#{TOOLS_DIR}/#{NODE_VER}/bin/npx"
NG = File.expand_path('webui/node_modules/.bin/ng')
SWAGGER_CODEGEN = "#{TOOLS_DIR}/swagger-codegen-cli-2.4.8.jar"
SWAGGER_FILE = File.expand_path("server/kraken/server/swagger.yml")

# prepare env
task :prepare_env do
  sh 'sudo DEBIAN_FRONTEND=noninteractive apt-get install -y default-jre python3-venv npm libpq-dev libpython3.7-dev'
  sh 'python3 -m venv venv && ./venv/bin/pip install -U pip'
end

# UI
task :gen_client => [SWAGGER_CODEGEN, SWAGGER_FILE] do
  Dir.chdir('ui') do
    sh "java -jar #{SWAGGER_CODEGEN} generate  -l typescript-angular -i #{SWAGGER_FILE} -o src/app/backend --additional-properties snapshot=true,ngVersion=8.2.8,modelPropertyNaming=snake_case"
  end
end

file SWAGGER_CODEGEN do
  sh "mkdir -p #{TOOLS_DIR}"
  sh "wget http://central.maven.org/maven2/io/swagger/swagger-codegen-cli/2.4.8/swagger-codegen-cli-2.4.8.jar -O #{SWAGGER_CODEGEN}"
end

file NPX do
  sh "mkdir -p #{TOOLS_DIR}"
  Dir.chdir(TOOLS_DIR) do
    sh "wget https://nodejs.org/dist/v10.16.3/#{NODE_VER}.tar.xz -O #{TOOLS_DIR}/node.tar.xz"
    sh "tar -Jxf node.tar.xz"
  end
end

file NG => NPX do
  Dir.chdir('ui') do
    sh 'npm install'
  end
end

task :build_ui => [NG, :gen_client] do
  kk_ver = ENV['kk_ver'] || '0.0'
  Dir.chdir('ui') do
    sh "sed -e 's/0\.0/#{kk_ver}/g' src/environments/environment.prod.ts.in > src/environments/environment.prod.ts"
    sh 'npx ng build --prod'
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
  end
end


# BACKEND

file './venv/bin/python3' do
  sh 'python3 -m venv venv'
  sh './venv/bin/pip install -U pip'
end

file './server/venv/bin/python3' do
  sh 'python3 -m venv server/venv'
  sh './server/venv/bin/pip install -U pip'
end

file './agent/venv/bin/python3' do
  sh 'python3 -m venv agent/venv'
  sh './agent/venv/bin/pip install -U pip'
end

def setup_py_develop
  Dir.chdir('server') do
    sh './venv/bin/pip install -r requirements.txt'
    sh './venv/bin/python3 setup.py develop --upgrade'
  end
end

['./server/venv/bin/kkserver', './server/venv/bin/kkscheduler', './server/venv/bin/kkcelery', './server/venv/bin/kkplanner', './server/venv/bin/kkdbmigrate'].each {|f|
  file f => ['./server/venv/bin/python3', './server/requirements.txt'] do
    setup_py_develop
  end
}

task :run_server => './server/venv/bin/kkserver' do
  sh './server/venv/bin/kkserver'
end

task :run_scheduler => './server/venv/bin/kkscheduler' do
  sh './server/venv/bin/kkscheduler'
end

file './agent/venv/bin/kkagent' => './agent/venv/bin/python3' do
  Dir.chdir('agent') do
    sh './venv/bin/python3 setup.py develop --upgrade'
  end
end

task :run_agent => './agent/venv/bin/kkagent' do
  sh 'cp server/kraken/server/consts.py agent/kraken/agent/'
  sh 'cp server/kraken/server/logs.py agent/kraken/agent/'
  sh 'rm -rf /tmp/kk-jobs/'
  sh 'bash -c "source ./agent/venv/bin/activate && kkagent -d /tmp/kk-jobs -s http://localhost:8080/backend"'
end

task :run_agent_container do
  Rake::Task["build_agent"].invoke
  Dir.chdir('agent') do
    sh 'docker build -f docker-agent.txt -t kkagent .'
  end
  sh 'docker run --rm -ti -v `pwd`/agent:/agent -e KRAKEN_SERVER_ADDR=192.168.0.89:8080 kkagent'
end

task :run_celery => './server/venv/bin/kkcelery' do
  sh './server/venv/bin/kkcelery'
end

task :run_planner => './server/venv/bin/kkplanner' do
  sh './server/venv/bin/kkplanner'
end

file './venv/bin/shiv' => ['./venv/bin/python3', 'requirements.txt'] do
    sh './venv/bin/pip install -r requirements.txt'
end

task :build_server => './venv/bin/shiv' do
  Dir.chdir('server') do
    sh 'rm -rf dist'
    sh '../venv/bin/pip install --target dist -r requirements.txt'
    sh '../venv/bin/pip install --target dist --upgrade .'
    sh "../venv/bin/shiv --site-packages dist --compressed -p '/usr/bin/env python3' -o kkgunicorn -c gunicorn"
    sh "../venv/bin/shiv --site-packages dist --compressed -p '/usr/bin/env python3' -o kkserver -c kkserver"
    sh "../venv/bin/shiv --site-packages dist --compressed -p '/usr/bin/env python3' -o kkscheduler -c kkscheduler"
    sh "../venv/bin/shiv --site-packages dist --compressed -p '/usr/bin/env python3' -o kkcelery -c kkcelery"
    sh "../venv/bin/shiv --site-packages dist --compressed -p '/usr/bin/env python3' -o kkplanner -c kkplanner"
    sh "../venv/bin/shiv --site-packages dist --compressed -p '/usr/bin/env python3' -o kkdbmigrate -c kkdbmigrate"
  end
end

task :build_agent => './venv/bin/shiv' do
  sh 'cp server/kraken/server/consts.py agent/kraken/agent/'
  sh 'cp server/kraken/server/logs.py agent/kraken/agent/'
  Dir.chdir('agent') do
    sh 'rm -rf dist'
    sh '../venv/bin/pip install --target dist --upgrade .'
    sh "../venv/bin/shiv --site-packages dist --compressed -p '/usr/bin/env python3' -o kkagent -c kkagent"
    sh "../venv/bin/shiv --site-packages dist --compressed -p '/usr/bin/env python3' -o kktool -c kktool"
  end
end

task :build_py => [:build_agent, :build_server]

task :clean_backend do
  sh 'rm -rf venv'
  sh 'rm -rf server/venv'
  sh 'rm -rf agent/venv'
end

task :build_all => [:build_py, :build_ui]


# DATABASE
task :db_up do
  Dir.chdir('server/migrations') do
    sh 'KRAKEN_DB_URL=postgresql://kraken:kk123@localhost:5433/kraken ../venv/bin/alembic -c alembic.ini upgrade head'
  end
end

task :db_down do
  Dir.chdir('server/migrations') do
    sh 'KRAKEN_DB_URL=postgresql://kraken:kk123@localhost:5433/kraken ../venv/bin/alembic -c alembic.ini downgrade -1'
  end
end


# DOCKER

#task :docker_up => [:build_ui] do
task :docker_up do
  sh "docker-compose down"
  sh "docker-compose build"
  sh "docker-compose up"
end

task :docker_down do
  sh "docker-compose down -v"
end

task :run_elk do
  sh 'docker-compose up kibana logstash elasticsearch'
end

task :run_pgsql do
  sh 'docker run --rm -p 5433:5432 -e POSTGRES_USER=kraken -e POSTGRES_PASSWORD=kk123 -e POSTGRES_DB=kraken postgres:11'
end

task :run_redis do
  sh 'docker run --rm -p 6379:6379 redis:alpine'
end

task :build_docker_deploy do
  sh 'docker-compose -f docker-compose-swarm.yaml config > docker-compose-swarm-deploy.yaml'
end

task :docker_release do
  kk_ver = ENV['kk_ver']
  sh "docker-compose -f docker-compose-swarm.yaml config > kraken-docker-stack-#{kk_ver}.yaml"
  sh "sed -i -e s/kk_ver/#{kk_ver}/g kraken-docker-stack-#{kk_ver}.yaml"
  sh "docker-compose -f docker-compose.yaml config > docker-compose-#{kk_ver}.yaml"
  sh "sed -i -e s/kk_ver/#{kk_ver}/g docker-compose-#{kk_ver}.yaml"
  sh "sed -i -e 's#127.0.0.1:5000#eu.gcr.io/kraken-261806#g' docker-compose-#{kk_ver}.yaml"
  sh "docker-compose -f docker-compose-#{kk_ver}.yaml build"
  sh "docker-compose -f docker-compose-#{kk_ver}.yaml push"
end

task :prepare_swarm do
  sh 'sudo DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io docker-compose gnupg2 pass'
  sh 'docker swarm init || true'
  sh 'docker login --username=godfryd --password=donotchange cloud.canister.io:5000'

end

task :run_swarm => :build_docker_deploy do
  sh 'docker stack deploy --with-registry-auth -c docker-compose-swarm-deploy.yaml kraken'
end

task :run_portainer do
  sh 'docker volume create portainer_data'
  sh 'docker run -d -p 8000:8000 -p 9000:9000 -v /var/run/docker.sock:/var/run/docker.sock -v portainer_data:/data portainer/portainer'
end

task :deploy_lab do
  kk_ver = ENV['kk_ver']
  sh "./venv/bin/fab -e -H lab.kraken.ci upgrade --kk-ver #{kk_ver}"
end

task :release_deploy do
  Rake::Task["build_all"].invoke
  Rake::Task["docker_release"].invoke
  Rake::Task["deploy_lab"].invoke
end
