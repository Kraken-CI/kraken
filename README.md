# Kraken CI

Kraken CI is a continuous integration and testing system.

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

## Under the your desk

To start demo instance run:

```console
rake docker_up
```

Then open http://0.0.0.0:8080/

# Architecture


![Kraken Architecture](https://i.imgur.com/S11Lyfj.png)
