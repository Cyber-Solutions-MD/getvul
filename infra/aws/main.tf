# GetVul — Amazon Web Services infrastructure
# Single EC2 instance running Docker Compose with auto-update

terraform {
  required_version = ">= 1.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

# ── Default VPC ──

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
  filter {
    name   = "default-for-az"
    values = ["true"]
  }
}

# ── Latest Ubuntu 22.04 LTS AMI ──

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# ── Security Group ──

resource "aws_security_group" "getvul" {
  name        = "getvul"
  description = "GetVul — HTTP, HTTPS, and SSH access"
  vpc_id      = data.aws_vpc.default.id

  tags = {
    Name      = "getvul"
    ManagedBy = "terraform"
  }
}

resource "aws_security_group_rule" "http" {
  type              = "ingress"
  from_port         = 80
  to_port           = 80
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.getvul.id
  description       = "HTTP"
}

resource "aws_security_group_rule" "https" {
  type              = "ingress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.getvul.id
  description       = "HTTPS"
}

resource "aws_security_group_rule" "ssh" {
  type              = "ingress"
  from_port         = 22
  to_port           = 22
  protocol          = "tcp"
  cidr_blocks       = var.ssh_allowed_cidrs
  security_group_id = aws_security_group.getvul.id
  description       = "SSH"
}

resource "aws_security_group_rule" "egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.getvul.id
  description       = "Allow all outbound"
}

# ── Key Pair ──

resource "aws_key_pair" "getvul" {
  key_name   = "getvul"
  public_key = var.ssh_public_key

  tags = {
    Name      = "getvul"
    ManagedBy = "terraform"
  }
}

# ── EC2 Instance ──

resource "aws_instance" "getvul" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  key_name               = aws_key_pair.getvul.key_name
  vpc_security_group_ids = [aws_security_group.getvul.id]
  subnet_id              = data.aws_subnets.default.ids[0]

  root_block_device {
    volume_size = var.disk_size_gb
    volume_type = "gp3"
  }

  user_data = templatefile("${path.module}/startup.sh", {
    app_name    = "getvul"
    github_repo = var.github_repo
    deploy_key  = var.deploy_key
  })

  tags = {
    Name      = "getvul"
    ManagedBy = "terraform"
  }
}

# ── Elastic IP ──

resource "aws_eip" "getvul" {
  instance = aws_instance.getvul.id
  domain   = "vpc"

  tags = {
    Name      = "getvul"
    ManagedBy = "terraform"
  }
}
