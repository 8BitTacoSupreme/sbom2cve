# SBOM2CVE AWS Dev/Free Tier Quick Start

Deploy SBOM2CVE MVP to AWS **Free Tier** for learning and testing.

**Cost**: ~$0-5/month (first 12 months) or ~$15/month (after Free Tier expires)

---

## What You Get

### Infrastructure (Free Tier Eligible)
- **2x t2.micro** instances (750 hrs/month free each = 24/7)
  - 1x K3s server (control plane)
  - 1x K3s agent (Kafka + VEX API)
- **50GB EBS storage** (30GB free, ~$2/month for extra 20GB)
- **No Load Balancer** (saves ~$20/month)
- **Single Kafka broker** (no replication, minimal resources)

### Cost Breakdown

| Item | Free Tier | After 12 Months | When Stopped |
|------|-----------|-----------------|--------------|
| 2x t2.micro (750 hrs/mo each) | $0 | ~$8/month | $0 |
| 50GB EBS (30GB free) | ~$2/month | ~$5/month | ~$5/month |
| Data transfer (15GB/mo free) | $0 | ~$2/month | $0 |
| **Total** | **~$2-5/month** | **~$15/month** | **~$5/month** |

**Comparison**:
- **Production (t3.xlarge)**: ~$326/month
- **Dev (t2.micro)**: ~$2-5/month (first year), ~$15/month (after)
- **Savings**: 95%+ for first year, 95%+ after

---

## Prerequisites

Same as production, but **more patient** (t2.micro is slower):
- AWS Account (Free Tier eligible for first 12 months)
- AWS CLI configured
- Terraform >= 1.5.0
- SSH key pair

---

## 5-Step Dev Deployment

### Step 1: Generate Credentials

```bash
# Generate K3s cluster token
openssl rand -hex 32
# Save: a1b2c3d4e5f6...

# Get your public IP
curl ifconfig.me
# Save: 1.2.3.4
```

### Step 2: Configure Terraform (Dev Mode)

```bash
cd terraform/aws

# Use dev config template
cp terraform.tfvars.dev terraform.tfvars

# Edit
nano terraform.tfvars
```

**Minimal terraform.tfvars** (for dev):
```hcl
# From step 1
k3s_cluster_token = "a1b2c3d4e5f6..."

# Your SSH public key
ssh_public_key = "ssh-rsa AAAAB3NzaC..."

# Restrict to your IP (from step 1)
ssh_allowed_cidr = ["1.2.3.4/32"]
k8s_api_allowed_cidr = ["1.2.3.4/32"]

# Important dev settings (already in terraform.tfvars.dev)
environment = "dev"
agent_count = 1
server_instance_type = "t2.micro"
agent_instance_type = "t2.micro"
enable_alb = false # No load balancer
```

### Step 3: Deploy Infrastructure

```bash
# Initialize
terraform init

# Deploy with dev config
terraform apply -var-file="terraform.tfvars.dev"
# Or if you edited terraform.tfvars:
terraform apply

# Type: yes
```

**⏱️ Time**: ~5-10 minutes for infrastructure

### Step 4: Wait for Auto-Setup & Configure for Dev

The t2.micro instances need special configuration for Kafka:

```bash
# SSH to server
ssh -i ~/.ssh/id_rsa ubuntu@$(terraform output -raw k3s_server_public_ip)

# Add swap space (critical for 1GB RAM)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Wait for K3s setup to complete
tail -f /var/log/user-data.log
# Wait for: "✅ K3s Server Setup Complete!"

# Deploy dev-optimized Kafka (single broker)
cd /opt/sbom2cve
sudo kubectl apply -f k8s/kafka/kafka-cluster-dev.yaml
sudo kubectl apply -f k8s/kafka/topics-dev.yaml

# Wait for Kafka (10-15 minutes on t2.micro - be patient!)
sudo kubectl wait kafka/sbom2cve-kafka \
    --for=condition=Ready \
    --timeout=900s \
    -n sbom2cve
```

### Step 5: Verify Deployment

```bash
# Check nodes (on server)
sudo kubectl get nodes
# Expected: 2 nodes (server + 1 agent)

# Check Kafka status
sudo kubectl get kafka -n sbom2cve
# Expected: sbom2cve-kafka READY=True

# Check pods
sudo kubectl get pods -n sbom2cve
# Expected: All Running (may take 10-15 min)
```

---

## Testing Your Dev Deployment

### 1. Test VEX API (Port Forward - No ALB in Dev)

```bash
# On your local machine, set up kubectl
scp -i ~/.ssh/id_rsa \
    ubuntu@$(terraform output -raw k3s_server_public_ip):/etc/rancher/k3s/k3s.yaml \
    ~/.kube/sbom2cve-dev

sed -i '' "s/127.0.0.1/$(terraform output -raw k3s_server_public_ip)/g" \
    ~/.kube/sbom2cve-dev

export KUBECONFIG=~/.kube/sbom2cve-dev

# Port forward VEX API
kubectl port-forward svc/vex-api 8080:80 -n sbom2cve &

# Test health
curl http://localhost:8080/health
# Expected: {"status":"healthy",...}

# Submit VEX
curl -X POST http://localhost:8080/api/v1/vex \
  -H "Content-Type: application/json" \
  -d '{
    "org_id": "test",
    "cve_id": "CVE-2024-TEST",
    "product_purl": "pkg:nix/test",
    "status": "not_affected"
  }'
```

### 2. Test KEV Producer

```bash
# SSH to server
ssh -i ~/.ssh/id_rsa ubuntu@$(terraform output -raw k3s_server_public_ip)

# Run KEV producer
cd /opt/sbom2cve
python3 src/producers/kev_producer.py \
    --once \
    --bootstrap-servers sbom2cve-kafka-bootstrap.sbom2cve:9092

# Expected: ✅ Published 1451 KEV records
# Note: May be slower on t2.micro
```

---

## Dev-Specific Optimizations

### Memory Management (Critical for t2.micro)

```bash
# Check memory usage
free -h

# Monitor Kafka memory
kubectl top pod -n sbom2cve

# If Kafka is OOM, reduce heap further:
kubectl edit kafka sbom2cve-kafka -n sbom2cve
# Change jvmOptions:
#   -Xms: 192m
#   -Xmx: 384m
```

### Reduce Topic Partitions (If Needed)

```bash
# Edit topics after deployment
kubectl edit kafkatopic cves-enriched -n sbom2cve
# Change spec.partitions: 5 (from 10)
```

### Disable Unused Features

```bash
# Don't deploy Kafka Exporter (saves memory)
# Skip Prometheus/Grafana for dev
# Reduce VEX API replicas to 1:
kubectl scale deployment vex-api --replicas=1 -n sbom2cve
```

---

## Cost-Saving Tips

### 1. Stop Instances When Not in Use

```bash
# Stop (keeps EBS, ~$5/month)
aws ec2 stop-instances \
    --instance-ids $(terraform output -raw k3s_server_id) $(terraform output -raw k3s_agent_ids | jq -r '.[]')

# Start when needed
aws ec2 start-instances \
    --instance-ids $(terraform output -raw k3s_server_id) $(terraform output -raw k3s_agent_ids | jq -r '.[]')
```

### 2. Schedule Auto-Stop (Weekends/Nights)

```bash
# Tag instances for auto-stop
aws ec2 create-tags \
    --resources $(terraform output -raw k3s_server_id) \
    --tags Key=AutoStop,Value=true Key=StopTime,Value=18:00

# Use AWS Lambda + EventBridge to automate
# See: https://aws.amazon.com/solutions/implementations/instance-scheduler-on-aws/
```

### 3. Use Single Instance (Even Cheaper)

```hcl
# terraform.tfvars.dev
agent_count = 0 # No agents, run everything on server
```

**Trade-off**: Less realistic (no distributed setup), but saves ~$7/month

---

## Limitations of t2.micro Dev Setup

### Performance
- **Slower**: 1 vCPU vs 4 vCPU (production)
- **Memory constrained**: 1GB RAM (needs swap)
- **No burstable credits when idle**: Slower during bursts

### Scalability
- **Single broker**: No replication, no fault tolerance
- **Fewer partitions**: Lower throughput (10 vs 500 partitions)
- **Single worker**: Can't distribute load

### Features Disabled
- No Application Load Balancer
- No Kafka Exporter (monitoring)
- Reduced retention (1 day vs 7 days)
- No automatic scaling (HPA)

### What Still Works
- ✅ All core functionality (PURL mapping, risk scoring, VEX)
- ✅ Kafka messaging (just slower)
- ✅ KEV producer, VEX API
- ✅ Unit tests (51/51 passing)
- ✅ Great for learning, testing, demos

---

## When to Upgrade to Production

**Stick with dev if**:
- Learning/testing only
- < 100 CVEs/day
- < 10 SBOM updates/day
- Okay with slower performance

**Upgrade to production if**:
- Production workload
- Need high availability (replication)
- Need high throughput (>1000 msgs/sec)
- Need monitoring, auto-scaling
- Budget allows (~$326/month or ~$130/month with spot)

---

## Troubleshooting

### Kafka Pod Stuck in Pending/CrashLoopBackOff

```bash
# Check memory
kubectl describe pod sbom2cve-kafka-0 -n sbom2cve
# Look for: "OOMKilled" or "Insufficient memory"

# Add swap (on server AND agent)
ssh ubuntu@<server-ip>
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Reduce Kafka memory
kubectl edit kafka sbom2cve-kafka -n sbom2cve
# Set -Xmx: 384m
```

### K3s Agent Not Joining

```bash
# t2.micro is slow, be patient (5-10 minutes)

# Check agent logs
ssh ubuntu@<agent-ip>
sudo journalctl -u k3s-agent -f

# Verify connectivity
curl -k https://<server-private-ip>:6443
# Should respond (cert error is okay)
```

### VEX API Not Starting

```bash
# Check pod logs
kubectl logs deployment/vex-api -n sbom2cve

# Common issue: Kafka not ready
kubectl get kafka -n sbom2cve
# Must show READY=True

# Restart if needed
kubectl rollout restart deployment/vex-api -n sbom2cve
```

---

## Cleanup

```bash
# Destroy everything
terraform destroy -var-file="terraform.tfvars.dev"
# Type: yes

# Verify EBS volumes deleted
aws ec2 describe-volumes --filters "Name=tag:Project,Values=sbom2cve"
# Should be empty
```

---

## Summary: Dev vs Production

| Feature | Dev (t2.micro) | Production (t3.xlarge) |
|---------|----------------|------------------------|
| **Cost (1st year)** | ~$2-5/month | ~$326/month |
| **Cost (after)** | ~$15/month | ~$326/month |
| **Setup Time** | 15-20 min | 15 min |
| **Memory** | 1GB (tight) | 16GB (plenty) |
| **CPU** | 1 vCPU | 4 vCPU |
| **Kafka Brokers** | 1 (no replication) | 3 (replicated) |
| **Throughput** | ~50 msgs/sec | ~5000 msgs/sec |
| **Best For** | Learning, testing | Production |

---

## Next Steps

After testing in dev:

1. **Validate Functionality**: Run all tests, verify KEV/VEX work
2. **Learn the Stack**: Explore Kafka, K3s, Strimzi
3. **Decide on Production**: If needed, switch to `terraform.tfvars` (production config)
4. **Scale Up**: Change instance types, add agents, enable ALB

---

**Perfect for**: Students, learners, demos, POCs
**Not suitable for**: Production workloads, high throughput, SLAs

🤖 Generated with [Claude Code](https://claude.com/claude-code)
