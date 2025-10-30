# SBOM2CVE AWS Deployment with Terraform

Deploy SBOM2CVE MVP to AWS EC2 with K3s, Kafka, and VEX API.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  AWS VPC (10.0.0.0/16)                                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────┐         ┌─────────────────┐           │
│  │ K3s Server      │         │ Application LB  │           │
│  │ (t3.large)      │◀────────│ (VEX API)       │──────▶ 🌐 │
│  │ • Control Plane │         └─────────────────┘           │
│  │ • 100GB EBS     │                                        │
│  └─────────────────┘                                        │
│         │                                                    │
│         │ K3s Cluster                                       │
│         │                                                    │
│  ┌──────┴────────────────────────────────────┐             │
│  │                                             │             │
│  ▼                   ▼                   ▼                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │ Agent 1     │  │ Agent 2     │  │ Agent 3     │       │
│  │ (t3.xlarge) │  │ (t3.xlarge) │  │ (t3.xlarge) │       │
│  │ • Kafka 1   │  │ • Kafka 2   │  │ • Kafka 3   │       │
│  │ • VEX API   │  │ • VEX API   │  │ • VEX API   │       │
│  │ • 200GB EBS │  │ • 200GB EBS │  │ • 200GB EBS │       │
│  └─────────────┘  └─────────────┘  └─────────────┘       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Components**:
- **1x t3.large** (K3s server): 2 vCPU, 8GB RAM, 100GB EBS
- **3x t3.xlarge** (K3s agents): 4 vCPU, 16GB RAM, 200GB EBS each
- **Application Load Balancer**: Public access to VEX API
- **VPC**: 10.0.0.0/16 with 3 availability zones
- **Security Groups**: SSH, K3s API, Kafka, VEX API, Prometheus/Grafana

---

## Prerequisites

### 1. Install Terraform

```bash
# macOS
brew install terraform

# Verify
terraform version  # Should be >= 1.5.0
```

### 2. Configure AWS Credentials

```bash
# Option A: AWS CLI
aws configure

# Option B: Environment variables
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-west-2"

# Verify
aws sts get-caller-identity
```

### 3. Generate SSH Key Pair (if you don't have one)

```bash
ssh-keygen -t rsa -b 4096 -C "sbom2cve-aws" -f ~/.ssh/sbom2cve-aws
```

### 4. Generate K3s Cluster Token

```bash
openssl rand -hex 32
# Example output: a1b2c3d4e5f6...
```

---

## Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/8BitTacoSupreme/sbom2cve.git
cd sbom2cve
git checkout future-state-mvp
cd terraform/aws
```

### 2. Create terraform.tfvars

```bash
# Copy example
cp terraform.tfvars.example terraform.tfvars

# Edit with your values
nano terraform.tfvars
```

**Required variables**:
```hcl
# Generate with: openssl rand -hex 32
k3s_cluster_token = "your-32-byte-hex-token"

# Paste your public key
ssh_public_key = "ssh-rsa AAAAB3NzaC... your-email@example.com"

# Restrict access (replace 0.0.0.0/0 with your IP)
ssh_allowed_cidr = ["1.2.3.4/32"]
k8s_api_allowed_cidr = ["1.2.3.4/32"]
```

### 3. Initialize Terraform

```bash
terraform init
```

**Expected output**:
```
Initializing the backend...
Initializing provider plugins...
- Finding hashicorp/aws versions matching "~> 5.0"...
- Installing hashicorp/aws v5.x.x...

Terraform has been successfully initialized!
```

### 4. Plan Deployment

```bash
terraform plan
```

**Review**:
- 4 EC2 instances (1 server + 3 agents)
- 1 VPC with 3 subnets
- 1 Application Load Balancer
- Security groups, IAM roles, etc.

### 5. Deploy Infrastructure

```bash
terraform apply
```

**Confirmation**: Type `yes` when prompted

**Deployment time**: ~5-10 minutes for infrastructure
**K3s + Kafka setup**: Additional 10-15 minutes via user-data scripts

### 6. Get Outputs

```bash
terraform output
```

**Important outputs**:
```
k3s_server_public_ip = "54.123.45.67"
vex_api_alb_url = "http://sbom2cve-vex-api-alb-123456789.us-west-2.elb.amazonaws.com"
ssh_command_server = "ssh -i ~/.ssh/id_rsa ubuntu@54.123.45.67"
```

---

## Post-Deployment Setup

### 1. SSH to K3s Server

```bash
# Use output from terraform
ssh -i ~/.ssh/id_rsa ubuntu@$(terraform output -raw k3s_server_public_ip)
```

### 2. Check K3s Status

```bash
# On server
sudo kubectl get nodes

# Expected output:
# NAME                   STATUS   ROLES                  AGE   VERSION
# sbom2cve-server        Ready    control-plane,master   5m    v1.28.x+k3s1
# sbom2cve-agent-xxx-1   Ready    <none>                 4m    v1.28.x+k3s1
# sbom2cve-agent-xxx-2   Ready    <none>                 4m    v1.28.x+k3s1
# sbom2cve-agent-xxx-3   Ready    <none>                 4m    v1.28.x+k3s1
```

### 3. Wait for Kafka to be Ready

```bash
# On server
sudo kubectl wait kafka/sbom2cve-kafka \
    --for=condition=Ready \
    --timeout=600s \
    -n sbom2cve

# Check status
sudo kubectl get kafka -n sbom2cve
# NAME             DESIRED KAFKA REPLICAS   DESIRED ZK REPLICAS   READY
# sbom2cve-kafka   3                        3                     True
```

### 4. Set Up Local kubectl Access

```bash
# Copy kubeconfig from server
scp -i ~/.ssh/id_rsa \
    ubuntu@$(terraform output -raw k3s_server_public_ip):/etc/rancher/k3s/k3s.yaml \
    ~/.kube/sbom2cve-config

# Update server IP
sed -i '' "s/127.0.0.1/$(terraform output -raw k3s_server_public_ip)/g" \
    ~/.kube/sbom2cve-config

# Set environment variable
export KUBECONFIG=~/.kube/sbom2cve-config

# Verify
kubectl get nodes
```

---

## Testing the Deployment

### 1. Test VEX API via Load Balancer

```bash
# Get ALB URL
ALB_URL=$(terraform output -raw vex_api_alb_url)

# Health check
curl $ALB_URL/health

# Expected: {"status":"healthy","service":"vex-api","timestamp":"..."}

# Get VEX schema
curl $ALB_URL/api/v1/vex/schema | jq
```

### 2. Test Kafka with KEV Producer

```bash
# SSH to server
ssh -i ~/.ssh/id_rsa ubuntu@$(terraform output -raw k3s_server_public_ip)

# Clone repo (if not already done by user-data)
cd /opt/sbom2cve

# Run KEV producer
python3 src/producers/kev_producer.py \
    --once \
    --bootstrap-servers sbom2cve-kafka-bootstrap:9092

# Expected:
# ✅ Published 1451 KEV records to kev-feed
```

### 3. Verify Kafka Messages

```bash
# Exec into Kafka pod
kubectl exec -it sbom2cve-kafka-0 -n sbom2cve -- bash

# List topics
bin/kafka-topics.sh --bootstrap-server localhost:9092 --list

# Consume KEV feed
bin/kafka-console-consumer.sh \
    --bootstrap-server localhost:9092 \
    --topic kev-feed \
    --from-beginning \
    --max-messages 5
```

---

## Cost Estimation

**Monthly AWS Cost (us-west-2)**:

| Resource | Type | Quantity | Monthly Cost |
|----------|------|----------|--------------|
| EC2 (Server) | t3.large | 1 | ~$60 |
| EC2 (Agents) | t3.xlarge | 3 | ~$180 |
| EBS (Server) | 100GB gp3 | 1 | ~$8 |
| EBS (Agents) | 200GB gp3 | 3 | ~$48 |
| ALB | Application LB | 1 | ~$20 |
| Data Transfer | Outbound | Varies | ~$10 |
| **Total** | | | **~$326/month** |

**Cost Optimization**:
- Use **t3 Spot instances**: ~60% savings (~$130/month)
- Reduce agent count to 1: Save ~$76/month
- Remove ALB: Save ~$20/month
- **Dev/staging**: ~$80-100/month with spot + single agent

---

## Scaling

### Horizontal Scaling (Add More Workers)

```bash
# Edit terraform.tfvars
agent_count = 5  # Increase from 3 to 5

# Apply changes
terraform apply
```

### Vertical Scaling (Larger Instances)

```bash
# Edit terraform.tfvars
agent_instance_type = "t3.2xlarge"  # 8 vCPU, 32GB RAM

# Apply changes
terraform apply
```

### Scale Kafka Brokers

```bash
# Edit k8s/kafka/kafka-cluster.yaml on server
spec:
  kafka:
    replicas: 5  # Increase from 3 to 5

# Apply
kubectl apply -f k8s/kafka/kafka-cluster.yaml
```

---

## Monitoring

### Access Prometheus (if enabled)

```bash
# Port forward from local machine
kubectl port-forward svc/prometheus-server 9090:80 -n sbom2cve

# Open http://localhost:9090
```

### Access Grafana (if enabled)

```bash
# Port forward
kubectl port-forward svc/grafana 3000:80 -n sbom2cve

# Open http://localhost:3000
# Default login: admin/prom-operator
```

### View Logs

```bash
# VEX API logs
kubectl logs -f deployment/vex-api -n sbom2cve

# Kafka logs
kubectl logs -f sbom2cve-kafka-0 -n sbom2cve

# All sbom2cve logs
kubectl logs -f -l app=sbom2cve -n sbom2cve --all-containers
```

---

## Troubleshooting

### K3s Nodes Not Joining

```bash
# Check server logs
ssh ubuntu@<server-ip>
sudo journalctl -u k3s -f

# Check agent logs
ssh ubuntu@<agent-ip>
sudo journalctl -u k3s-agent -f
```

### Kafka Not Starting

```bash
# Check pod status
kubectl get pods -n sbom2cve

# Check logs
kubectl logs sbom2cve-kafka-0 -n sbom2cve

# Check PVC status
kubectl get pvc -n sbom2cve
```

### VEX API Not Accessible

```bash
# Check ALB target health
aws elbv2 describe-target-health \
    --target-group-arn <target-group-arn>

# Check security group rules
aws ec2 describe-security-groups \
    --group-ids $(terraform output -raw security_group_id)
```

---

## Cleanup

### Destroy Infrastructure

```bash
# Preview what will be destroyed
terraform destroy -dry-run

# Destroy everything
terraform destroy

# Type 'yes' to confirm
```

**Warning**: This will:
- Delete all EC2 instances
- Delete all EBS volumes
- Delete VPC, subnets, security groups
- Delete Application Load Balancer

**Data backup**: Before destroying, back up:
- Kafka topics (if needed)
- VEX statements
- Application logs

---

## Security Best Practices

### 1. Restrict Access

```hcl
# terraform.tfvars
ssh_allowed_cidr = ["YOUR_IP/32"]  # Your office/home IP only
k8s_api_allowed_cidr = ["YOUR_IP/32"]
kafka_allowed_cidr = ["10.0.0.0/16"]  # VPC only
```

### 2. Enable HTTPS for VEX API

```bash
# Use AWS Certificate Manager
# Add HTTPS listener to ALB
# See: https://docs.aws.amazon.com/elasticloadbalancing/latest/application/create-https-listener.html
```

### 3. Enable Kafka TLS

```yaml
# k8s/kafka/kafka-cluster.yaml
spec:
  kafka:
    listeners:
      - name: tls
        port: 9093
        type: internal
        tls: true
```

### 4. Rotate K3s Cluster Token

```bash
# Generate new token
openssl rand -hex 32

# Update terraform.tfvars
# Run: terraform apply
```

---

## Next Steps

1. **Deploy Flink Jobs**: Add PURL mapper and matcher Flink jobs
2. **NVD Integration**: Auto-fetch CVEs from NVD API
3. **SBOM Ingestion**: Connect real Flox environments
4. **CI/CD Pipeline**: Automate deployments with GitHub Actions
5. **Production Hardening**: Enable TLS, setup monitoring, backups

---

## Support

- **Terraform Docs**: https://registry.terraform.io/providers/hashicorp/aws/latest/docs
- **K3s Docs**: https://docs.k3s.io/
- **Strimzi Docs**: https://strimzi.io/docs/

---

**Last Updated**: 2025-10-30
**Terraform Version**: >= 1.5.0
**AWS Provider**: ~> 5.0

🤖 Generated with [Claude Code](https://claude.com/claude-code)
