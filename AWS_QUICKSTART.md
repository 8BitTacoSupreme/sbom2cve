# SBOM2CVE AWS Quick Start

Deploy SBOM2CVE MVP to AWS in 15 minutes with Terraform.

---

## Prerequisites Checklist

- [ ] **AWS Account** with admin access
- [ ] **AWS CLI** installed and configured (`aws configure`)
- [ ] **Terraform** >= 1.5.0 installed (`brew install terraform`)
- [ ] **SSH key pair** (or generate one: `ssh-keygen -t rsa -b 4096`)
- [ ] **~$326/month** budget (or ~$130/month with spot instances)

---

## 5-Step Deployment

### Step 1: Generate Credentials

```bash
# Generate K3s cluster token
openssl rand -hex 32
# Save this output: a1b2c3d4e5f6...

# Get your public IP (for security group restrictions)
curl ifconfig.me
# Save this output: 1.2.3.4
```

### Step 2: Configure Terraform

```bash
cd terraform/aws

# Copy example config
cp terraform.tfvars.example terraform.tfvars

# Edit configuration
nano terraform.tfvars
```

**Minimal terraform.tfvars**:
```hcl
# Cluster token (from step 1)
k3s_cluster_token = "a1b2c3d4e5f6..."

# Your SSH public key
ssh_public_key = "ssh-rsa AAAAB3NzaC... your-email@example.com"

# Restrict access to your IP (from step 1)
ssh_allowed_cidr = ["1.2.3.4/32"]
k8s_api_allowed_cidr = ["1.2.3.4/32"]
```

### Step 3: Deploy Infrastructure

```bash
# Initialize Terraform
terraform init

# Preview deployment
terraform plan

# Deploy (takes ~5-10 minutes)
terraform apply
# Type: yes
```

**Expected output**:
```
Apply complete! Resources: 20 added, 0 changed, 0 destroyed.

Outputs:

k3s_server_public_ip = "54.123.45.67"
vex_api_alb_url = "http://sbom2cve-vex-api-alb-xyz.us-west-2.elb.amazonaws.com"
ssh_command_server = "ssh -i ~/.ssh/id_rsa ubuntu@54.123.45.67"
```

### Step 4: Wait for Auto-Setup

The user-data scripts are now setting up K3s and Kafka automatically.

```bash
# SSH to server
ssh -i ~/.ssh/id_rsa ubuntu@$(terraform output -raw k3s_server_public_ip)

# Watch setup progress
tail -f /var/log/user-data.log

# Expected: "✅ K3s Server Setup Complete!" (after ~5 minutes)
```

### Step 5: Verify Deployment

```bash
# Check K3s nodes (on server)
sudo kubectl get nodes
# Expected: 4 nodes (1 server + 3 agents) all Ready

# Wait for Kafka to be ready (~5-10 minutes)
sudo kubectl wait kafka/sbom2cve-kafka \
    --for=condition=Ready \
    --timeout=600s \
    -n sbom2cve

# Check Kafka status
sudo kubectl get kafka -n sbom2cve
# Expected: sbom2cve-kafka READY=True
```

---

## Test Your Deployment

### 1. Test VEX API (Public ALB)

```bash
# Get ALB URL
ALB_URL=$(terraform output -raw vex_api_alb_url)

# Health check
curl $ALB_URL/health
# Expected: {"status":"healthy","service":"vex-api","timestamp":"..."}

# Get VEX schema
curl $ALB_URL/api/v1/vex/schema | jq

# Submit test VEX statement
curl -X POST $ALB_URL/api/v1/vex \
  -H "Content-Type: application/json" \
  -d '{
    "org_id": "test_org",
    "cve_id": "CVE-2024-1234",
    "product_purl": "pkg:nix/nixpkgs/openssl@3.0.7",
    "status": "not_affected"
  }'
# Expected: {"status":"accepted","vex_id":"..."}
```

### 2. Set Up Local kubectl Access

```bash
# Copy kubeconfig
scp -i ~/.ssh/id_rsa \
    ubuntu@$(terraform output -raw k3s_server_public_ip):/etc/rancher/k3s/k3s.yaml \
    ~/.kube/sbom2cve-aws

# Update server IP
sed -i '' "s/127.0.0.1/$(terraform output -raw k3s_server_public_ip)/g" \
    ~/.kube/sbom2cve-aws

# Use config
export KUBECONFIG=~/.kube/sbom2cve-aws

# Test
kubectl get nodes
kubectl get pods -n sbom2cve
```

### 3. Test KEV Producer

```bash
# SSH to server
ssh -i ~/.ssh/id_rsa ubuntu@$(terraform output -raw k3s_server_public_ip)

# Run KEV producer
cd /opt/sbom2cve
python3 src/producers/kev_producer.py \
    --once \
    --bootstrap-servers sbom2cve-kafka-bootstrap.sbom2cve:9092

# Expected:
# ✅ Fetched KEV catalog v2025.10.30
# ✅ Published 1451 KEV records to kev-feed
```

---

## What You Just Deployed

### Infrastructure
- **1x t3.large**: K3s server (control plane)
- **3x t3.xlarge**: K3s agents (Kafka brokers + workers)
- **VPC**: 10.0.0.0/16 with 3 availability zones
- **ALB**: Public load balancer for VEX API
- **Security Groups**: Restricted SSH, K3s API, Kafka, monitoring

### Software Stack
- **K3s v1.28**: Lightweight Kubernetes
- **Strimzi Kafka Operator**: Manages Kafka cluster
- **Kafka 3.6**: 3 brokers + 3 Zookeeper nodes
- **7 Kafka Topics**: purl-mapping-rules, cves-enriched, kev-feed, etc.
- **VEX API**: Flask REST API (3-10 replicas with HPA)
- **Kafka Exporter**: Prometheus metrics

### Monthly Cost
- **Regular instances**: ~$326/month
- **Spot instances**: ~$130/month (60% savings)
- **Dev/staging (1 agent)**: ~$80-100/month

---

## Next Steps

### 1. Deploy PURL Mapper (Future Work)

```bash
# Build Flink job Docker image
docker build -t sbom2cve/purl-mapper:latest -f docker/Dockerfile.purl-mapper .

# Deploy to K8s
kubectl apply -f k8s/flink/purl-mapper-job.yaml
```

### 2. Connect Flox Environments

```bash
# Configure Flox SBOM producer to publish to Kafka
# Point to: sbom2cve-kafka-bootstrap:9092
```

### 3. Add Monitoring

```bash
# Install Prometheus + Grafana
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus prometheus-community/kube-prometheus-stack \
    --namespace sbom2cve

# Access Grafana
kubectl port-forward svc/prometheus-grafana 3000:80 -n sbom2cve
# Open http://localhost:3000 (admin/prom-operator)
```

### 4. Enable HTTPS

```bash
# Request ACM certificate
aws acm request-certificate \
    --domain-name vex-api.your-domain.com \
    --validation-method DNS

# Update ALB to use HTTPS listener
# See: terraform/aws/README.md "Security Best Practices"
```

---

## Troubleshooting

### Terraform Apply Fails

**Error**: "InvalidKeyPair.NotFound"
```bash
# Make sure ssh_public_key is set in terraform.tfvars
# Or set via environment variable:
export TF_VAR_ssh_public_key="$(cat ~/.ssh/id_rsa.pub)"
terraform apply
```

**Error**: "InsufficientInstanceCapacity"
```bash
# Try different availability zone or instance type
# Edit terraform.tfvars:
aws_region = "us-east-1"  # Try different region
agent_instance_type = "t3a.xlarge"  # AMD-based (sometimes more available)
```

### K3s Nodes Not Joining

```bash
# Check server logs
ssh ubuntu@<server-ip>
sudo journalctl -u k3s -f

# Check agent logs
ssh ubuntu@<agent-ip>
sudo journalctl -u k3s-agent -f

# Verify cluster token matches
sudo cat /var/lib/rancher/k3s/server/node-token  # On server
```

### Kafka Not Ready

```bash
# Check pod status
kubectl get pods -n sbom2cve

# Check logs
kubectl logs sbom2cve-kafka-0 -n sbom2cve

# Check storage
kubectl get pvc -n sbom2cve
# All PVCs should be Bound
```

### VEX API Not Accessible via ALB

```bash
# Check ALB target health
aws elbv2 describe-target-health \
    --target-group-arn $(terraform output -raw alb_target_group_arn)

# Should show "healthy" status

# Check security group allows port 8080
aws ec2 describe-security-groups \
    --group-ids $(terraform output -raw security_group_id) \
    | jq '.SecurityGroups[0].IpPermissions'
```

---

## Cleanup

```bash
# Destroy all resources (WARNING: Deletes everything!)
terraform destroy
# Type: yes

# Estimated time: 5 minutes
```

**Cost of forgetting to destroy**: ~$11/day (~$326/month)

---

## Cost Optimization Tips

### 1. Use Spot Instances (60% Savings)

Edit `main.tf`:
```hcl
resource "aws_instance" "k3s_agent" {
  # Add:
  instance_market_options {
    market_type = "spot"
    spot_options {
      max_price = "0.10"  # Adjust based on region
    }
  }
}
```

### 2. Reduce Agent Count

Edit `terraform.tfvars`:
```hcl
agent_count = 1  # Reduce from 3 to 1 (saves ~$120/month)
```

### 3. Use Smaller Instances (Dev/Staging)

Edit `terraform.tfvars`:
```hcl
server_instance_type = "t3.medium"  # 2 vCPU, 4GB RAM
agent_instance_type = "t3.large"    # 2 vCPU, 8GB RAM
```

### 4. Stop Instances When Not in Use

```bash
# Stop instances (keeps EBS volumes)
aws ec2 stop-instances --instance-ids $(terraform output -json k3s_agent_instance_ids | jq -r '.[]')

# Start when needed
aws ec2 start-instances --instance-ids $(terraform output -json k3s_agent_instance_ids | jq -r '.[]')

# Cost when stopped: ~$56/month (EBS volumes only)
```

---

## Comparison: AWS vs Local

| Feature | AWS (Terraform) | Local (Minikube) |
|---------|-----------------|------------------|
| **Setup Time** | 15 minutes | 10 minutes |
| **Monthly Cost** | ~$326 | $0 |
| **Performance** | High (dedicated HW) | Limited (VM overhead) |
| **Scalability** | Horizontal + Vertical | Limited by laptop |
| **Public Access** | Yes (ALB) | No (port-forward only) |
| **Best For** | Production, staging | Development, testing |

---

## Support

- **Terraform Issues**: See `terraform/aws/README.md`
- **K3s Issues**: https://docs.k3s.io/
- **Strimzi/Kafka**: https://strimzi.io/docs/
- **Project Docs**: See `DEPLOYMENT.md`, `MVP_README.md`

---

**Deployment Time**: 15 minutes (infrastructure) + 10 minutes (auto-setup)
**Total Time to Production**: ~25 minutes
**Monthly Cost**: ~$326 (regular) or ~$130 (spot)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
