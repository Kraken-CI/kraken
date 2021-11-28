# Kraken CI

[Kraken CI](https://kraken.ci/)


Features:
- flexible workflow planning using Starlark/Python
- distributed building and testing
- various executors: bare metal, Docker, LXD
- highly scalable to thousands of executors
- sophisticated test results analysis
- integrated with AWS EC2 and ECS, Azure VM, with autoscaling
- supported webhooks from GitHub, GitLab and Gitea
- email and Slack notifications


## Get Repo Info

```console
helm repo add kraken-ci 'https://dl.cloudsmith.io/public/kraken-ci/kraken/helm/charts/'
helm repo update
```

_See [helm repo](https://helm.sh/docs/helm/helm_repo/) for command documentation._

## Install Chart

```console
# Helm 3
$ helm install [RELEASE_NAME] kraken-ci/kraken-ci [flags]
```

_See [configuration](#configuration) below._

_See [helm install](https://helm.sh/docs/helm/helm_install/) for command documentation._

## Uninstall Chart

```console
# Helm 3
$ helm uninstall [RELEASE_NAME]
```

This removes all the Kubernetes components associated with the chart and deletes the release.

_See [helm uninstall](https://helm.sh/docs/helm/helm_uninstall/) for command documentation._

## Upgrade Chart

```console
$ helm upgrade [RELEASE_NAME] kraken-ci/kraken-ci [flags]
```

Example:

```console
$ helm upgrade  --install --create-namespace --namespace kk-1 --debug --wait kraken-ci --set access.external_ips={`minikube ip`} --set access.method='external-ips' kraken-ci/kraken-ci --version 0.753.0
```

_See [helm upgrade](https://helm.sh/docs/helm/helm_upgrade/) for command documentation._


## Configuration

See [Customizing the Chart Before Installing](https://helm.sh/docs/intro/using_helm/#customizing-the-chart-before-installing).
To see all configurable options with detailed comments, visit the chart's [values.yaml](./values.yaml), or run these configuration commands:

```console
# Helm 3
$ helm show values kraken-ci/kraken-ci
```
