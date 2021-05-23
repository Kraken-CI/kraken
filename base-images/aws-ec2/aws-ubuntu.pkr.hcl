packer {
  required_plugins {
    amazon = {
      version = ">= 0.0.1"
      source  = "github.com/hashicorp/amazon"
    }
  }
}

source "amazon-ebs" "ubuntu" {
  ami_name      = "kraken-ubuntu-20.04-4"
  instance_type = "t2.micro"
  region        = "ca-central-1"
  source_ami_filter {
    filters = {
      name                = "ubuntu/images/*ubuntu-*-20.04-amd64-server-*"
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
      "curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -",
      "sudo add-apt-repository 'deb [arch=amd64] https://download.docker.com/linux/ubuntu focal stable'",
      "sudo apt update",
      "sudo apt-get install -y docker-ce",

      # Setup kraken agent
      #"wget http://lab.kraken.ci/install/kraken-agent-install.sh",
      #"chmod a+x kraken-agent-install.sh",
      #"./kraken-agent-install.sh",
      #"wget -O kkagent https://lab.kraken.ci/install/agent",
      #"chmod a+x kkagent",
      #"./kkagent install -s https://lab.kraken.ci",
      #"systemctl status kraken-agent"

      # kraken build deps
      "sudo apt-get install -y rake xz-utils openjdk-13-jre-headless apt-transport-https software-properties-common nodejs npm",
      "wget https://github.com/mikefarah/yq/releases/download/v4.2.0/yq_linux_amd64",
      "sudo mv yq_linux_amd64 /usr/bin/yq",
      "sudo chmod a+x /usr/bin/yq",

      # cleanup
      "sudo rm -rf /var/lib/apt/lists/*",
    ]
  }
}
