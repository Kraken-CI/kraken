Vagrant.configure("2") do |config|
  config.vm.box = "ubuntu/focal64"

  config.vm.provider "virtualbox" do |v|
    v.customize ["modifyvm", :id, "--memory", 8192]
    v.customize ["modifyvm", :id, "--cpus", 4]
  end

#  config.vm.provision "file", source: "docker-compose-swarm-deploy.yaml", destination: "docker-compose-swarm-deploy.yaml"
#  config.vm.provision "file", source: "deploy.sh", destination: "deploy.sh"

#  config.vm.network "forwarded_port", guest: 8080, host: 8088
end
