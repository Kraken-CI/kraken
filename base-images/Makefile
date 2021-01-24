# BUILD #######################################################################
build: bld-python bld-go bld-openjdk bld-ubuntu bld-bld-kraken

# python 3.8.5
bld-python:
	docker build -t krakenci/python:3.8.5 -f docker-python.txt .
	docker tag krakenci/python:3.8.5 krakenci/python:3.8
	docker tag krakenci/python:3.8.5 krakenci/python:3
	docker tag krakenci/python:3.8.5 krakenci/python:latest

# go 1.15.7
bld-go:
	docker build -t krakenci/golang:1.15.7 -f docker-go.txt .
	docker tag krakenci/golang:1.15.7 krakenci/golang:1.15
	docker tag krakenci/golang:1.15.7 krakenci/golang:latest

# openjdk 11.0
bld-openjdk:
	docker build -t krakenci/openjdk:11.0 -f docker-openjdk.txt .
	docker tag krakenci/openjdk:11.0 krakenci/openjdk:11
	docker tag krakenci/openjdk:11.0 krakenci/openjdk:latest

# ubuntu 20.04
bld-ubuntu:
	docker build -t krakenci/ubuntu:20.04 -f docker-ubuntu-20.04.txt .

# for building kraken
bld-bld-kraken:
	docker build -t krakenci/bld-kraken -f docker-bld-kraken.txt .


# PUSH ########################################################################
push: push-python push-go push-openjdk push-ubuntu push-bld-kraken

# python 3.8.5
push-python:
	docker push krakenci/python:3.8.5
	docker push krakenci/python:3.8
	docker push krakenci/python:3
	docker push krakenci/python:latest

# go 1.15.7
push-go:
	docker push krakenci/golang:1.15.7
	docker push krakenci/golang:1.15
	docker push krakenci/golang:latest

# openjdk 11.0
push-openjdk:
	docker push krakenci/openjdk:11.0
	docker push krakenci/openjdk:11
	docker push krakenci/openjdk:latest

# ubuntu 20.04
push-ubuntu:
	docker push krakenci/ubuntu:20.04

# for building kraken
push-bld-kraken:
	docker push krakenci/bld-kraken
