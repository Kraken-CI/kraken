build:
# python 3.8.5
	docker build -t krakenci/python:3.8.5 -f docker-python.txt .
	docker tag krakenci/python:3.8.5 krakenci/python:3.8
	docker tag krakenci/python:3.8.5 krakenci/python:3
	docker tag krakenci/python:3.8.5 krakenci/python:latest
# ubuntu 20.04
	docker build -t krakenci/ubuntu:20.04 -f docker-ubuntu-20.04.txt .
# for building kraken
	docker build -t krakenci/bld-kraken -f docker-bld-kraken.txt .

push:
# python 3.8.5
	docker push krakenci/python:3.8.5
	docker push krakenci/python:3.8
	docker push krakenci/python:3
	docker push krakenci/python:latest
# ubuntu 20.04
	docker push krakenci/ubuntu:20.04
# for building kraken
	docker push krakenci/bld-kraken
