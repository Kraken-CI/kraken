packer {
  required_plugins {
    amazon = {
      version = ">= 0.0.1"
      source  = "github.com/hashicorp/amazon"
    }
  }
}

source "amazon-ebs" "ubuntu" {
  ami_name      = "kraken-ubuntu-22.04-7"
  instance_type = "t2.micro"
  region        = "ca-central-1"
  source_ami_filter {
    filters = {
      name                = "ubuntu/images/*ubuntu-*-22.04-amd64-server-*"
      root-device-type    = "ebs"
      virtualization-type = "hvm"
    }
    most_recent = true
    owners      = ["099720109477"]
  }
  ssh_username = "ubuntu"
}

build {
  sources = [
    "source.amazon-ebs.ubuntu"
  ]

  provisioner "shell" {
    environment_vars = [
      "DEBIAN_FRONTEND=noninteractive",
    ]
    inline = [
      "set -x",
      "sudo systemctl disable apt-daily.timer",
      "sudo systemctl disable apt-daily-upgrade.timer",
      "sudo systemctl stop unattended-upgrades.service",
      "sudo systemctl stop apt-daily.service",
      "sudo systemctl stop apt-daily-upgrade.service",
      #"sudo rm -rf /var/lib/apt/lists/*",
      "cloud-init status --wait",
      "sudo apt-get update -y",
      "sudo apt-get dist-upgrade -y",
      "sudo apt-get install -y --no-install-recommends locales openssh-client ca-certificates sudo git unzip zip gnupg curl wget make net-tools python3 python3-pytest python3-venv python3-docker python3-setuptools",

      # Set timezone to UTC by default
      "sudo ln -sf /usr/share/zoneinfo/Etc/UTC /etc/localtime",

      # Use unicode
      "sudo locale-gen en_US.UTF-8",

      # prepare sudo
      "sudo sed -i 's/^.*requiretty/Defaults !requiretty/' /etc/sudoers",
      "sudo bash -c \"echo 'Defaults !requiretty' >> /etc/sudoers\"",
      "sudo bash -c \"echo 'kraken ALL = NOPASSWD: ALL' > /etc/sudoers.d/kraken\"",

      # install docker stuff
      "sudo install -m 0755 -d /etc/apt/keyrings",
      "curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg",
      "sudo chmod a+r /etc/apt/keyrings/docker.gpg",
      "echo 'deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu jammy stable' | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null",
      "sudo apt update",
      "sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin",

      # Setup kraken agent
      #"wget http://lab.kraken.ci/bk/install/kraken-agent-install.sh",
      #"chmod a+x kraken-agent-install.sh",
      #"./kraken-agent-install.sh",
      #"wget -O kkagent https://lab.kraken.ci/bk/install/agent",
      #"chmod a+x kkagent",
      #"./kkagent install -s https://lab.kraken.ci",
      #"systemctl status kraken-agent"

      # kraken build deps
      "curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash - ",
      "sudo apt-get install -y rake xz-utils openjdk-17-jre-headless apt-transport-https software-properties-common nodejs libpq-dev gcc libpython3-dev python3-dev libldap-dev libsasl2-dev python3-wheel python3-pip cloc",
      "wget https://github.com/mikefarah/yq/releases/download/v4.35.2/yq_linux_amd64",
      "sudo mv yq_linux_amd64 /usr/bin/yq",
      "sudo chmod a+x /usr/bin/yq",

      # cleanup
      "sudo rm -rf /var/lib/apt/lists/*",
    ]
  }
}
