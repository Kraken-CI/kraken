TOOLS_DIR = File.expand_path('tools')
NODE_VER = 'node-v10.16.3-linux-x64'
ENV['PATH'] = "#{TOOLS_DIR}/#{NODE_VER}/bin:#{ENV['PATH']}"
NPX = "#{TOOLS_DIR}/#{NODE_VER}/bin/npx"
NG = File.expand_path('webui/node_modules/.bin/ng')
SWAGGER_CODEGEN = "#{TOOLS_DIR}/swagger-codegen-cli-2.4.8.jar"
SWAGGER_FILE = File.expand_path("server/kraken/server/swagger.yml")

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
  Dir.chdir('ui') do
    sh 'npx ng build --prod'
  end
end

task :serve_ui => [NG, :gen_client] do
  Dir.chdir('ui') do
    sh 'npx ng serve --disable-host-check --proxy-config proxy.conf.json'
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

file ['./server/venv/bin/kkserver', './server/venv/bin/kkscheduler', './server/venv/bin/kkcelery', './server/venv/bin/kkplanner'] => ['./server/venv/bin/python3', './server/requirements.txt'] do
  Dir.chdir('server') do
    sh './venv/bin/pip install -r requirements.txt'
    sh './venv/bin/python3 setup.py develop --upgrade'
  end
end

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
  sh './agent/venv/bin/kkagent -d /tmp/kk-jobs -s http://localhost:8080/backend'
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
    sh "../venv/bin/shiv --site-packages dist --compressed -p '/usr/bin/env python3' -o kkserver -c kkserver"
    sh "../venv/bin/shiv --site-packages dist --compressed -p '/usr/bin/env python3' -o kkscheduler -c kkscheduler"
    sh "../venv/bin/shiv --site-packages dist --compressed -p '/usr/bin/env python3' -o kkcelery -c kkcelery"
    sh "../venv/bin/shiv --site-packages dist --compressed -p '/usr/bin/env python3' -o kkplanner -c kkplanner"
  end
end

task :build_agent => './venv/bin/shiv' do
  sh 'cp server/kraken/server/consts.py agent/kraken/agent/'
  sh 'cp server/kraken/server/logs.py agent/kraken/agent/'
  Dir.chdir('agent') do
    sh 'rm -rf dist'
    sh '../venv/bin/pip install --target dist --upgrade .'
    sh "../venv/bin/shiv --site-packages dist --compressed -p '/usr/bin/env python3' -o kkagent -c kkagent"
  end
end

task :build_py => [:build_agent, :build_server]

task :clean_backend do
  sh 'rm -rf venv'
  sh 'rm -rf server/venv'
  sh 'rm -rf agent/venv'
end


# DOCKER

#task :docker_up => [:build_ui] do
task :docker_up do
  sh "docker-compose down"
  sh "docker-compose build"
  sh "docker-compose up"
end

task :docker_down do
  sh "docker-compose down"
end

task :run_elk do
  sh 'docker-compose up kibana logstash elasticsearch'
end
