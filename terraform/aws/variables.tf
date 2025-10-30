# SBOM2CVE Terraform Variables

variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-west-2"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "cluster_name" {
  description = "Name of the K3s cluster"
  type        = string
  default     = "sbom2cve"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "az_count" {
  description = "Number of availability zones to use"
  type        = number
  default     = 3
}

variable "server_instance_type" {
  description = "EC2 instance type for K3s server (control plane)"
  type        = string
  default     = "t3.large" # 2 vCPU, 8GB RAM
}

variable "agent_instance_type" {
  description = "EC2 instance type for K3s agents (workers)"
  type        = string
  default     = "t3.xlarge" # 4 vCPU, 16GB RAM (for Kafka)
}

variable "agent_count" {
  description = "Number of K3s agent nodes (workers)"
  type        = number
  default     = 3
}

variable "k3s_cluster_token" {
  description = "K3s cluster token for node authentication"
  type        = string
  sensitive   = true
  default     = "" # Generate with: openssl rand -hex 32
}

variable "ssh_public_key" {
  description = "SSH public key for EC2 instances"
  type        = string
  # Set via environment variable: TF_VAR_ssh_public_key="$(cat ~/.ssh/id_rsa.pub)"
}

variable "ssh_allowed_cidr" {
  description = "CIDR blocks allowed to SSH to instances"
  type        = list(string)
  default     = ["0.0.0.0/0"] # CHANGE THIS IN PRODUCTION
}

variable "k8s_api_allowed_cidr" {
  description = "CIDR blocks allowed to access Kubernetes API"
  type        = list(string)
  default     = ["0.0.0.0/0"] # CHANGE THIS IN PRODUCTION
}

variable "kafka_allowed_cidr" {
  description = "CIDR blocks allowed to access Kafka"
  type        = list(string)
  default     = ["0.0.0.0/0"] # CHANGE THIS IN PRODUCTION
}

variable "monitoring_allowed_cidr" {
  description = "CIDR blocks allowed to access Prometheus/Grafana"
  type        = list(string)
  default     = ["0.0.0.0/0"] # CHANGE THIS IN PRODUCTION
}

variable "enable_alb" {
  description = "Enable Application Load Balancer for VEX API"
  type        = bool
  default     = true
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
