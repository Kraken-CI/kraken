def stage(ctx):
    kk_ver = "#{env.KK_BASE_VER}.#{KK_FLOW_SEQ}"

    return {
        "parent": "Build",
        "triggers": {
            "manual": True,
        },
        "parameters": [],
        "configs": [],
        "jobs": [{
            "name": "publish",
            "timeout": 1200,
            "steps": [{
                "tool": "artifacts",
                "action": "download",
                "source": "kraken.tar.gz"
            }, {
                "tool": "shell",
                "cmd": "tar -zxf kraken.tar.gz",
            }, {
                "tool": "artifacts",
                "action": "download",
                "public": True,
                "source": [
                    "kraken-docker-compose-%s.yaml" % kk_ver,
                    "server/dist/krakenci_server-%s.tar.gz" % kk_ver,
                    "agent/krakenci_agent-%s.tar.gz" % kk_ver,
                    "client/dist/krakenci_client-%s.tar.gz" % kk_ver,
                    "ui/dist/krakenci_ui-%s.tar.gz" % kk_ver,
                    "clickhouse-proxy-%s.tar.gz" % kk_ver,
                ],
                "cwd": "kraken"
            }, {
                "tool": "shell",
                "script": """
                    rake -t prepare_env
                    rake -t publish_client publish_server
                """,
                "cwd": "kraken",
                "timeout": 300,
                "env": {
                    "kk_ver": kk_ver,
                    "PYPI_CLIENT_TOKEN": "#{secrets.pypi_client_token}",
                    "PYPI_SERVER_TOKEN": "#{secrets.pypi_server_token}"
                }
            }, {
                "tool": "shell",
                "cmd": "git config --global user.email 'godfryd@gmail.com'; git config --global user.name 'Michal Nowikowski'"
            }, {
                "tool": "git",
                "checkout": "git@github.com:Kraken-CI/helm-repo.git",
                "access-token": "github_token",
                "branch": "gh-pages"
            }, {
                "tool": "shell",
                "cmd": "echo \"${GOOGLE_KEY}\" | base64 -d > /tmp/key.json",
                "env": {
                    "GOOGLE_KEY": "#{KK_SECRET_SIMPLE_google_key}"
                }
            }, {
                "tool": "shell",
                "cmd": "gcloud auth activate-service-account lab-kraken-ci@kraken-261806.iam.gserviceaccount.com --project=kraken-261806 --key-file=/tmp/key.json"
            }, {
                "tool": "shell",
                "cmd": "rake kk_ver=%s mark_images_as_published" % kk_ver,
                "cwd": "kraken",
                "timeout": 120
            }, {
                "tool": "shell",
                "cmd": "rake kk_ver=%s helm_dest=../helm-repo/charts helm_release" % kk_ver,
                "cwd": "kraken",
                "timeout": 120
            }, {
                "tool": "shell",
                "cmd": "rake kk_ver=%s github_release" % kk_ver,
                "cwd": "kraken",
                "env": {
                    "GITHUB_TOKEN": "#{KK_SECRET_SIMPLE_github_token}"
                },
                "timeout": 300
            }],
            "environments": [{
                "system": "krakenci/bld-kraken-22.04:20231112",
                "executor": "docker",
            	"agents_group": "all",
                "config": "default"
            }]
        }]
    }
