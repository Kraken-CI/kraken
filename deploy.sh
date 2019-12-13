#!/bin/bash
set -e -x
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io docker-compose gnupg2 pass
docker swarm init || true
docker login --username=godfryd --password='donotchange' cloud.canister.io:5000
#docker pull cloud.canister.io:5000/godfryd/kkserver:latest
#docker pull cloud.canister.io:5000/godfryd/kkscheduler:latest
#docker pull cloud.canister.io:5000/godfryd/kkplanner:latest
##docker pull cloud.canister.io:5000/godfryd/kkcelery:latest
#docker pull cloud.canister.io:5000/godfryd/kkagent:latest
#docker pull cloud.canister.io:5000/godfryd/kkui:latest
docker stack deploy --with-registry-auth -c docker-compose-swarm-deploy.yaml kraken
