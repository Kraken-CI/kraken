#!/bin/bash
set -e -x
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io docker-compose gnupg2 pass

# portainer
docker volume create portainer_data
docker run -d -p 9000:9000 -p 8000:8000 --name portainer --restart always -v /var/run/docker.sock:/var/run/docker.sock -v portainer_data:/data portainer/portainer

# docker swarm
docker swarm init || true

# docker login to google registry by given user
cat kraken-34dc43122cd9.json | docker login -u _json_key --password-stdin https://eu.gcr.io

# start kraken
docker stack deploy --with-registry-auth -c kraken-docker-stack-0.4.yaml kraken
