# SBOM2CVE AWS Infrastructure
# Terraform configuration for EC2-based K3s cluster deployment

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Optional: S3 backend for state storage
  # backend "s3" {
  #   bucket         = "sbom2cve-terraform-state"
  #   key            = "prod/terraform.tfstate"
  #   region         = "us-west-2"
  #   encrypt        = true
  #   dynamodb_table = "sbom2cve-terraform-locks"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "sbom2cve"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Data sources
data "aws_availability_zones" "available" {
  state = "available"
}

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

# VPC
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.cluster_name}-vpc"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.cluster_name}-igw"
  }
}

# Public Subnets (for K3s nodes)
resource "aws_subnet" "public" {
  count = var.az_count

  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.cluster_name}-public-${data.aws_availability_zones.available.names[count.index]}"
  }
}

# Route Table
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "${var.cluster_name}-public-rt"
  }
}

# Route Table Association
resource "aws_route_table_association" "public" {
  count = var.az_count

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# Security Group
resource "aws_security_group" "k3s" {
  name        = "${var.cluster_name}-k3s-sg"
  description = "Security group for K3s cluster nodes"
  vpc_id      = aws_vpc.main.id

  # SSH access (restrict to your IP in production)
  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.ssh_allowed_cidr
  }

  # K3s API server
  ingress {
    description = "Kubernetes API"
    from_port   = 6443
    to_port     = 6443
    protocol    = "tcp"
    cidr_blocks = var.k8s_api_allowed_cidr
  }

  # Kafka (for external producers/consumers)
  ingress {
    description = "Kafka"
    from_port   = 9092
    to_port     = 9092
    protocol    = "tcp"
    cidr_blocks = var.kafka_allowed_cidr
  }

  # VEX API
  ingress {
    description = "VEX API"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # Public API
  }

  # Prometheus/Grafana (if enabled)
  ingress {
    description = "Prometheus"
    from_port   = 9090
    to_port     = 9090
    protocol    = "tcp"
    cidr_blocks = var.monitoring_allowed_cidr
  }

  ingress {
    description = "Grafana"
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = var.monitoring_allowed_cidr
  }

  # Allow all traffic within security group (K3s cluster communication)
  ingress {
    description = "K3s cluster internal"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
  }

  # Outbound traffic
  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.cluster_name}-k3s-sg"
  }
}

# IAM Role for EC2 instances
resource "aws_iam_role" "k3s_node" {
  name = "${var.cluster_name}-k3s-node-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.cluster_name}-k3s-node-role"
  }
}

# IAM Policy for K3s nodes (EBS, CloudWatch, ECR)
resource "aws_iam_role_policy" "k3s_node" {
  name = "${var.cluster_name}-k3s-node-policy"
  role = aws_iam_role.k3s_node.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:DescribeInstances",
          "ec2:DescribeVolumes",
          "ec2:AttachVolume",
          "ec2:DetachVolume",
          "ec2:DescribeSnapshots",
          "ec2:CreateSnapshot",
          "ec2:CreateTags",
          "ec2:DescribeTags"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = "*"
      }
    ]
  })
}

# IAM Instance Profile
resource "aws_iam_instance_profile" "k3s_node" {
  name = "${var.cluster_name}-k3s-node-profile"
  role = aws_iam_role.k3s_node.name
}

# SSH Key Pair
resource "aws_key_pair" "k3s" {
  key_name   = "${var.cluster_name}-key"
  public_key = var.ssh_public_key

  tags = {
    Name = "${var.cluster_name}-key"
  }
}

# K3s Server (Control Plane) Instance
resource "aws_instance" "k3s_server" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.server_instance_type
  key_name               = aws_key_pair.k3s.key_name
  subnet_id              = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.k3s.id]
  iam_instance_profile   = aws_iam_instance_profile.k3s_node.name

  root_block_device {
    volume_size = 100
    volume_type = "gp3"
    encrypted   = true
  }

  user_data = templatefile("${path.module}/user-data-server.sh", {
    cluster_token = var.k3s_cluster_token
    cluster_name  = var.cluster_name
  })

  tags = {
    Name = "${var.cluster_name}-server"
    Role = "server"
  }
}

# K3s Agent (Worker) Instances
resource "aws_instance" "k3s_agent" {
  count = var.agent_count

  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.agent_instance_type
  key_name               = aws_key_pair.k3s.key_name
  subnet_id              = aws_subnet.public[count.index % var.az_count].id
  vpc_security_group_ids = [aws_security_group.k3s.id]
  iam_instance_profile   = aws_iam_instance_profile.k3s_node.name

  root_block_device {
    volume_size = 200 # Larger for Kafka storage
    volume_type = "gp3"
    encrypted   = true
    iops        = 3000
    throughput  = 125
  }

  user_data = templatefile("${path.module}/user-data-agent.sh", {
    server_ip     = aws_instance.k3s_server.private_ip
    cluster_token = var.k3s_cluster_token
    cluster_name  = var.cluster_name
  })

  depends_on = [aws_instance.k3s_server]

  tags = {
    Name = "${var.cluster_name}-agent-${count.index + 1}"
    Role = "agent"
  }
}

# Elastic IPs for stable access
resource "aws_eip" "k3s_server" {
  instance = aws_instance.k3s_server.id
  domain   = "vpc"

  tags = {
    Name = "${var.cluster_name}-server-eip"
  }
}

# Application Load Balancer for VEX API (optional)
resource "aws_lb" "vex_api" {
  count = var.enable_alb ? 1 : 0

  name               = "${var.cluster_name}-vex-api-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.k3s.id]
  subnets            = aws_subnet.public[*].id

  enable_deletion_protection = var.environment == "prod" ? true : false

  tags = {
    Name = "${var.cluster_name}-vex-api-alb"
  }
}

resource "aws_lb_target_group" "vex_api" {
  count = var.enable_alb ? 1 : 0

  name     = "${var.cluster_name}-vex-api-tg"
  port     = 8080
  protocol = "HTTP"
  vpc_id   = aws_vpc.main.id

  health_check {
    enabled             = true
    path                = "/health"
    port                = "8080"
    protocol            = "HTTP"
    healthy_threshold   = 2
    unhealthy_threshold = 2
    timeout             = 5
    interval            = 30
  }

  tags = {
    Name = "${var.cluster_name}-vex-api-tg"
  }
}

resource "aws_lb_listener" "vex_api" {
  count = var.enable_alb ? 1 : 0

  load_balancer_arn = aws_lb.vex_api[0].arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.vex_api[0].arn
  }
}

# Register K3s agents with ALB target group
resource "aws_lb_target_group_attachment" "vex_api" {
  count = var.enable_alb ? var.agent_count : 0

  target_group_arn = aws_lb_target_group.vex_api[0].arn
  target_id        = aws_instance.k3s_agent[count.index].id
  port             = 8080
}
