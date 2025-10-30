# SBOM2CVE AWS One-Command Deployment

Deploy SBOM2CVE to AWS in **one command** with automated setup.

---

## Prerequisites (One-Time Setup)

### 1. Install AWS CLI

```bash
# macOS
brew install awscli

# Linux
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Verify
aws --version
```

### 2. Configure AWS Credentials

```bash
aws configure
```

**You'll need**:
- **AWS Access Key ID**: Get from AWS Console → Security Credentials
- **AWS Secret Access Key**: Get from AWS Console
- **Default region**: `us-east-1` (best for Free Tier) or your preferred region
- **Output format**: `json` (default)

**Verify**:
```bash
aws sts get-caller-identity
# Should show your AWS Account ID
```

### 3. Install Terraform (if not already installed)

```bash
# macOS
brew install terraform

# Linux
wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
unzip terraform_1.6.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/

# Verify
terraform version
```

---

## One-Command Deployment

### For Dev/Free Tier (~$2-5/month):

```bash
./scripts/aws-dev-deploy.sh
```

That's it! The script will:
1. ✅ Check prerequisites (AWS CLI, Terraform, SSH key)
2. ✅ Generate K3s cluster token
3. ✅ Detect your public IP for security groups
4. ✅ Create Terraform configuration
5. ✅ Deploy infrastructure (2x t2.micro + networking)
6. ✅ Wait for instances to boot
7. ✅ Configure swap space (critical for 1GB RAM)
8. ✅ Deploy K3s, Kafka, VEX API
9. ✅ Provide next steps and commands

**Total time**: ~15-20 minutes (mostly waiting for Kafka on t2.micro)

---

## What Gets Deployed

### Infrastructure
- **1x t2.micro** (K3s server) - Free Tier eligible
- **1x t2.micro** (K3s agent + Kafka) - Free Tier eligible
- **VPC** with 3 subnets across AZs
- **Security groups** (SSH, K8s API restricted to your IP)
- **Elastic IP** for server (stable access)
- **20GB + 30GB EBS** (gp2, Free Tier eligible)

### Software Stack
- **K3s** (lightweight Kubernetes)
- **Strimzi Kafka Operator**
- **Kafka** (single broker, dev-optimized)
- **VEX API** (Flask REST API)
- **7 Kafka topics** (reduced partitions for dev)

### Cost
- **First 12 months**: ~$2-5/month (Free Tier)
- **After 12 months**: ~$15/month
- **When stopped**: ~$5/month (EBS only)

---

## After Deployment

The script will print all next steps, including:

### 1. SSH to Server
```bash
ssh -i ~/.ssh/id_rsa ubuntu@<SERVER_IP>
```

### 2. Check Deployment Status
```bash
# On server
sudo kubectl get nodes
sudo kubectl get pods -n sbom2cve
sudo kubectl get kafka -n sbom2cve
```

### 3. Setup Local kubectl
```bash
# On your local machine
scp -i ~/.ssh/id_rsa ubuntu@<SERVER_IP>:/etc/rancher/k3s/k3s.yaml ~/.kube/sbom2cve-dev
sed -i '' 's/127.0.0.1/<SERVER_IP>/g' ~/.kube/sbom2cve-dev
export KUBECONFIG=~/.kube/sbom2cve-dev
kubectl get nodes
```

### 4. Test VEX API
```bash
# Port forward (no ALB in dev)
kubectl port-forward svc/vex-api 8080:80 -n sbom2cve &

# Test health
curl http://localhost:8080/health

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

### 5. Test KEV Producer
```bash
# SSH to server
ssh -i ~/.ssh/id_rsa ubuntu@<SERVER_IP>

# Run KEV producer
cd /opt/sbom2cve
python3 src/producers/kev_producer.py \
    --once \
    --bootstrap-servers sbom2cve-kafka-bootstrap.sbom2cve:9092
```

---

## Cost-Saving Tips

### Stop Instances When Not in Use
```bash
# Get instance IDs
cd terraform/aws
terraform output

# Stop instances (keeps EBS volumes)
aws ec2 stop-instances --instance-ids <server-id> <agent-id>

# Cost when stopped: ~$5/month (EBS only)

# Start when needed
aws ec2 start-instances --instance-ids <server-id> <agent-id>
```

### Schedule Auto-Stop
```bash
# Tag instances for auto-shutdown
aws ec2 create-tags \
    --resources <instance-id> \
    --tags Key=AutoStop,Value=true

# Use AWS Instance Scheduler (free)
# https://aws.amazon.com/solutions/implementations/instance-scheduler-on-aws/
```

---

## Troubleshooting

### Script Fails: "AWS credentials not configured"
```bash
# Configure AWS CLI
aws configure

# Test
aws sts get-caller-identity
```

### Script Fails: "Terraform not found"
```bash
# macOS
brew install terraform

# Linux
wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
unzip terraform_1.6.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/
```

### SSH Connection Fails
```bash
# Wait 2-3 minutes for instance to fully boot
# Then try:
ssh -i ~/.ssh/id_rsa ubuntu@<SERVER_IP>

# Check instance status
aws ec2 describe-instances --instance-ids <instance-id>
```

### Kafka Not Starting (t2.micro OOM)
```bash
# SSH to both server and agent
ssh -i ~/.ssh/id_rsa ubuntu@<SERVER_IP>

# Add swap (if script didn't complete)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Check memory
free -h

# Restart Kafka pod
sudo kubectl delete pod sbom2cve-kafka-0 -n sbom2cve
```

---

## Cleanup

```bash
# Destroy everything
cd terraform/aws
terraform destroy

# Type: yes

# Verify cleanup
aws ec2 describe-instances --filters "Name=tag:Project,Values=sbom2cve"
# Should be empty or terminated
```

**Note**: Destroying removes all resources. EBS volumes are deleted. Data is lost.

---

## Manual Deployment (If Script Fails)

If the script fails, you can deploy manually:

```bash
cd terraform/aws

# 1. Copy dev config
cp terraform.tfvars.dev terraform.tfvars

# 2. Edit manually
nano terraform.tfvars
# Add: cluster token, SSH key, your IP

# 3. Deploy
terraform init
terraform plan
terraform apply

# 4. Follow AWS_DEV_QUICKSTART.md for manual setup
```

---

## What Makes This Different

### vs Production Deployment:
- ✅ **95% cheaper** (~$2-5 vs ~$326/month)
- ✅ **Free Tier eligible** (first 12 months)
- ✅ **Automated setup** (one command vs manual steps)
- ✅ **Dev-optimized** (single broker, reduced resources)
- ⚠️  **Not production-ready** (no HA, no replication)

### vs Local (Minikube):
- ✅ **Real AWS environment** (test production deployment)
- ✅ **Accessible remotely** (share with team)
- ✅ **Stable** (no laptop sleep/restart issues)
- ⚠️  **Costs money** (~$2-5/month vs $0)
- ⚠️  **Slower setup** (15-20 min vs 10 min)

---

## Next Steps

1. **Deploy**: Run `./scripts/aws-dev-deploy.sh`
2. **Test**: Follow the "After Deployment" section
3. **Learn**: Explore Kafka, K3s, Strimzi
4. **Upgrade**: When ready, switch to production config

---

## Support

- **Script issues**: Check `scripts/aws-dev-deploy.sh` for detailed steps
- **AWS issues**: See `AWS_DEV_QUICKSTART.md`
- **Terraform issues**: See `terraform/aws/README.md`

---

**Perfect for**: First-time AWS users, students, demos, learning
**Not for**: Production workloads, high availability requirements

🤖 Generated with [Claude Code](https://claude.com/claude-code)
