# SBOM2CVE AWS Dev/Free Tier Configuration
# Minimal cost deployment for learning and testing

# This file contains dev-specific resource definitions
# Use: terraform apply -var-file="terraform.tfvars.dev"

# Dev-specific variables (override production defaults)
locals {
  is_dev = var.environment == "dev"

  # Dev storage sizes (Free Tier: 30GB EBS free)
  server_disk_size = local.is_dev ? 20 : 100
  agent_disk_size  = local.is_dev ? 30 : 200

  # Dev Kafka replicas (reduce for small instances)
  kafka_replicas     = local.is_dev ? 1 : 3
  zookeeper_replicas = local.is_dev ? 1 : 3
}

# Note: Main resources are in main.tf
# This file is for dev-specific overrides and documentation

# Dev deployment architecture:
# ┌─────────────────────────────────────────┐
# │  AWS VPC (10.0.0.0/16)                  │
# ├─────────────────────────────────────────┤
# │                                          │
# │  ┌─────────────────────────────────┐   │
# │  │ K3s Server (t2.micro)           │   │
# │  │ • Control Plane                 │   │
# │  │ • 20GB EBS                      │   │
# │  │ • Free Tier eligible            │   │
# │  └─────────────────────────────────┘   │
# │             │                            │
# │             │ K3s Cluster                │
# │             │                            │
# │             ▼                            │
# │  ┌─────────────────────────────────┐   │
# │  │ Agent 1 (t2.micro)              │   │
# │  │ • Kafka (single broker)         │   │
# │  │ • VEX API                       │   │
# │  │ • 30GB EBS                      │   │
# │  │ • Free Tier eligible            │   │
# │  └─────────────────────────────────┘   │
# │                                          │
# └─────────────────────────────────────────┘
#
# Cost: ~$0-15/month
# - First 12 months: ~$5/month (EBS only, instances free)
# - After 12 months: ~$15/month (2x t2.micro)

# Dev-specific deployment notes:
#
# 1. Single Kafka Broker:
#    - Edit k8s/kafka/kafka-cluster.yaml after deployment
#    - Set spec.kafka.replicas: 1
#    - Set spec.zookeeper.replicas: 1
#
# 2. Reduced VEX API replicas:
#    - Edit k8s/apps/vex-api.yaml
#    - Set spec.replicas: 1
#    - Remove HPA (or set minReplicas: 1, maxReplicas: 2)
#
# 3. No Application Load Balancer:
#    - Use kubectl port-forward instead:
#      kubectl port-forward svc/vex-api 8080:80 -n sbom2cve
#
# 4. Reduced topic partitions:
#    - Edit k8s/kafka/topics.yaml
#    - Reduce partitions (e.g., cves-enriched: 10 instead of 500)
#
# 5. Memory constraints:
#    - t2.micro has 1GB RAM
#    - Kafka may need memory tuning
#    - Consider swap space for stability

# Dev-specific user-data additions:
#
# Add to user-data-server.sh:
# - Configure swap (1GB)
# - Reduce Kafka memory: KAFKA_HEAP_OPTS="-Xms256m -Xmx512m"
# - Reduce Zookeeper memory
# - Disable unused K3s features

# Cost-saving commands:
#
# Stop instances when not in use (saves ~70%):
#   aws ec2 stop-instances --instance-ids $(terraform output -json | jq -r '.k3s_server_id.value, .k3s_agent_ids.value[]')
#
# Start when needed:
#   aws ec2 start-instances --instance-ids $(terraform output -json | jq -r '.k3s_server_id.value, .k3s_agent_ids.value[]')
#
# Schedule automatic shutdown (weekends):
#   aws ec2 create-tags --resources <instance-id> --tags Key=AutoStop,Value=true
#   # Use Lambda + EventBridge to stop/start on schedule
