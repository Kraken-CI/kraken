TOOLS_DIR = File.expand_path('tools')
NODE_VER = 'node-v10.16.3-linux-x64'
ENV['PATH'] = "#{TOOLS_DIR}/#{NODE_VER}/bin:#{ENV['PATH']}"
NPX = "#{TOOLS_DIR}/#{NODE_VER}/bin/npx"
NG = File.expand_path('webui/node_modules/.bin/ng')
SWAGGER_CODEGEN = "#{TOOLS_DIR}/swagger-codegen-cli-2.4.8.jar"
SWAGGER_FILE = File.expand_path("kraken/server/swagger.yml")

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

task :run_server do
  Dir.chdir('kraken/server') do
    sh '../../venv/bin/python ./server.py'
  end
end

task :run_scheduler do
  Dir.chdir('kraken/server') do
    sh '../../venv/bin/python ./scheduler.py'
  end
end

task :run_agent do
  Dir.chdir('kraken/agent') do
    sh 'rm -rf /tmp/kk-jobs/ && ./agent.py -d /tmp/kk-jobs -s http://localhost:5000/backend'
  end
end

task :run_celery do
  Dir.chdir('kraken/server') do
    sh '../../venv/bin/celery -A bg.clry worker -l info'
  end
end

task :run_planner do
  Dir.chdir('kraken/server') do
    sh '../../venv/bin/python ./planner.py'
  end
end

#task :docker_up => [:build_ui] do
task :docker_up do
  sh "docker-compose build"
  sh "docker-compose up"
end

task :docker_down do
  sh "docker-compose down"
end
