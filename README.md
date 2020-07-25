# Kraken CI

Kraken CI is a continuous integration and testing system.

[Features](#features)<br>
[Demo](#Demo)<br>
[Entities & Terminology](#Entities)<br>
[Architecture](#Architecture)<br>

# Features

- distributes builds and tests execution to multiple machines
- supports massive testing: hunderds tousands of unit tests
- stores build artifacts internally
- shows regressions and fixes beside failures and passes
- executors:
  - direct
  - Docker
  - LXD
- and much more

# Demo 

## Online

Online demo version can be visited on: http://lab.kraken.ci/

## Under your desk

To start demo instance run:

```console
rake docker_up
```

Then open http://0.0.0.0:8080/

# Entities & Terminology

### Project
`Project` separates things from other `projects`, it contains multiple `branches`.

### Branch
`Branch` can map to source code repository branch. In a `branch` there are defined `stages`. 
Each `stage` has its own workflow schema. An execution of stages form a flow. `Branch` contains two kinds of `flows` lists: 
- `CI flows` - they are triggered by e.g. commits to production source repository branch eg. to master
- `dev flows` - they are triggered by e.g. commits to developer branches

### Flow
`Flow` is an execution instance of in a `branch`. It contains one or more `runs` of `stages` ie. execution instances of `stages`.

### Stage

### Run

### Step

### Job

![Kraken Entities](https://i.imgur.com/P5xc8PL.png)

# Architecture

![Kraken Architecture](https://i.imgur.com/S11Lyfj.png)

## Server
`Server` exposes Kraken ReST API

## UI
`UI` is an Angular application that can be served by NGINX. Unicorn can be used to maintain `Server` instances.

## Controller
`Controller` is made of 4 services:

- `Planner` - it triggers new flows based on indicated rule in given project's branch
- `Scheduler` - it assigns jobs to executors
- `Watchdog` - it checks runs and their jobs if they are in their time limits, it also monitors executors health
- `Storage` - it stores and serves artifacts which can be uploaded or downloaded by agents

## Celery
`Celery` executes background tasks like processing results reported by an agent. Any service in `Controller`
or `Celery` tasks can enqueue new `Celery` tasks. Current tasks:

- analyze_results_history
- notify_about_completed_run
- trigger_stages
- job_completed
- trigger_run
- trigger_flow

## ELK
This is `ELK` stack ie. `Elasticsearch`, `Logstash` and `Kibana`. `Logstash` is used for collecting logs from all agents,
`Elasticsearch` is used for storing these logs and exposing them to the `Server` for example for presentin in `UI`.
`Kibana` is an internal dashboard to `Elasticsearch`.

## Agent
Agent is a service that is run on a machine that is expected to execute jobs. Agent can execute jobs directly on the system,
or it can encapulate them in e.g. container. Currently there are executors for:

- direct/bare
- Docker
- LXD
