#!/bin/bash
# SBOM2CVE AWS Dev/Free Tier Deployment Script
# Automated deployment to AWS using Terraform

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=========================================="
echo "SBOM2CVE AWS Dev/Free Tier Deployment"
echo -e "==========================================${NC}"
echo ""

# Check prerequisites
echo -e "${BLUE}Step 1: Checking prerequisites${NC}"
echo "----------------------------------------"

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI not found${NC}"
    echo ""
    echo "Install AWS CLI:"
    echo "  macOS:   brew install awscli"
    echo "  Linux:   curl 'https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip' -o 'awscliv2.zip' && unzip awscliv2.zip && sudo ./aws/install"
    echo ""
    exit 1
fi
echo -e "${GREEN}✅ AWS CLI installed: $(aws --version)${NC}"

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}❌ AWS credentials not configured${NC}"
    echo ""
    echo "Configure AWS CLI:"
    echo "  aws configure"
    echo ""
    echo "You'll need:"
    echo "  • AWS Access Key ID"
    echo "  • AWS Secret Access Key"
    echo "  • Default region (e.g., us-east-1)"
    echo ""
    exit 1
fi
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region || echo "us-east-1")
echo -e "${GREEN}✅ AWS credentials configured${NC}"
echo "   Account: $AWS_ACCOUNT"
echo "   Region: $AWS_REGION"

# Check Terraform
if ! command -v terraform &> /dev/null; then
    echo -e "${RED}❌ Terraform not found${NC}"
    echo ""
    echo "Install Terraform:"
    echo "  macOS:   brew install terraform"
    echo "  Linux:   wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip && unzip terraform_1.6.0_linux_amd64.zip && sudo mv terraform /usr/local/bin/"
    echo ""
    exit 1
fi
echo -e "${GREEN}✅ Terraform installed: $(terraform version -json | jq -r .terraform_version)${NC}"

# Check SSH key
if [ ! -f ~/.ssh/id_rsa.pub ]; then
    echo -e "${YELLOW}⚠️  SSH public key not found at ~/.ssh/id_rsa.pub${NC}"
    echo ""
    read -p "Generate SSH key now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ssh-keygen -t rsa -b 4096 -C "sbom2cve-aws" -f ~/.ssh/id_rsa -N ""
        echo -e "${GREEN}✅ SSH key generated${NC}"
    else
        echo -e "${RED}❌ SSH key required for deployment${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✅ SSH key found${NC}"
fi

echo ""

# Generate cluster token
echo -e "${BLUE}Step 2: Generating cluster credentials${NC}"
echo "----------------------------------------"

CLUSTER_TOKEN=$(openssl rand -hex 32)
echo -e "${GREEN}✅ K3s cluster token generated${NC}"
echo "   Token: ${CLUSTER_TOKEN:0:16}... (saved for later)"
echo ""

# Get user's public IP
echo "🔍 Detecting your public IP for security group..."
MY_IP=$(curl -s ifconfig.me || curl -s icanhazip.com || echo "0.0.0.0")
if [ "$MY_IP" = "0.0.0.0" ]; then
    echo -e "${YELLOW}⚠️  Could not detect public IP${NC}"
    read -p "Enter your public IP (or press Enter for 0.0.0.0/0 - NOT recommended): " USER_IP
    MY_IP=${USER_IP:-0.0.0.0}
fi
echo -e "${GREEN}✅ Your public IP: $MY_IP${NC}"
echo ""

# Estimate costs
echo -e "${BLUE}Step 3: Cost Estimation${NC}"
echo "----------------------------------------"
echo "Monthly AWS costs (US East):"
echo "  • 2x t2.micro (Free Tier):  \$0 (first 12 months)"
echo "  • 50GB EBS (30GB free):     ~\$2/month"
echo "  • Data transfer:            \$0 (< 15GB/month)"
echo ""
echo "  ${GREEN}Total: ~\$2-5/month (first year)${NC}"
echo "  ${YELLOW}After Free Tier: ~\$15/month${NC}"
echo ""
read -p "Continue with deployment? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled"
    exit 0
fi
echo ""

# Navigate to terraform directory
cd "$(dirname "$0")/../terraform/aws"

# Create terraform.tfvars
echo -e "${BLUE}Step 4: Creating Terraform configuration${NC}"
echo "----------------------------------------"

cat > terraform.tfvars <<EOF
# SBOM2CVE Dev Deployment - Auto-generated
# Generated: $(date)

# AWS Configuration
aws_region  = "$AWS_REGION"
environment = "dev"

# Cluster Configuration
cluster_name = "sbom2cve-dev"
agent_count  = 1

# Instance Types (Free Tier)
server_instance_type = "t2.micro"
agent_instance_type  = "t2.micro"

# K3s Cluster Token
k3s_cluster_token = "$CLUSTER_TOKEN"

# SSH Public Key
ssh_public_key = "$(cat ~/.ssh/id_rsa.pub)"

# Security (Restrict to your IP)
ssh_allowed_cidr        = ["$MY_IP/32"]
k8s_api_allowed_cidr    = ["$MY_IP/32"]
kafka_allowed_cidr      = ["10.0.0.0/16"]  # VPC only
monitoring_allowed_cidr = ["$MY_IP/32"]

# No ALB for dev (saves ~\$20/month)
enable_alb = false

# Tags
tags = {
  Owner       = "$USER"
  Environment = "dev"
  ManagedBy   = "terraform"
  AutoShutdown = "true"
}
EOF

echo -e "${GREEN}✅ Terraform configuration created${NC}"
echo "   Config: terraform/aws/terraform.tfvars"
echo ""

# Initialize Terraform
echo -e "${BLUE}Step 5: Initializing Terraform${NC}"
echo "----------------------------------------"
terraform init
echo ""

# Plan deployment
echo -e "${BLUE}Step 6: Planning deployment${NC}"
echo "----------------------------------------"
echo "Terraform will create:"
echo "  • 1x VPC with 3 subnets"
echo "  • 2x t2.micro instances"
echo "  • 2x EBS volumes (20GB + 30GB)"
echo "  • Security groups, IAM roles"
echo "  • Elastic IP for server"
echo ""
terraform plan -out=tfplan
echo ""

# Apply deployment
echo -e "${BLUE}Step 7: Deploying to AWS${NC}"
echo "----------------------------------------"
echo -e "${YELLOW}⏱️  This will take ~5-10 minutes${NC}"
echo ""
read -p "Start deployment now? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled (plan saved to tfplan)"
    exit 0
fi

terraform apply tfplan
echo ""

# Get outputs
echo -e "${BLUE}Step 8: Retrieving deployment info${NC}"
echo "----------------------------------------"
SERVER_IP=$(terraform output -raw k3s_server_public_ip)
AGENT_IP=$(terraform output -raw k3s_agent_public_ips | jq -r '.[0]' 2>/dev/null || echo "N/A")

echo -e "${GREEN}✅ Deployment complete!${NC}"
echo ""
echo "Server IP: $SERVER_IP"
echo "Agent IP: $AGENT_IP"
echo ""

# Wait for instances to be ready
echo -e "${BLUE}Step 9: Waiting for instances to boot${NC}"
echo "----------------------------------------"
echo "⏳ Waiting for SSH to be available (may take 2-3 minutes)..."

MAX_RETRIES=30
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if ssh -i ~/.ssh/id_rsa -o StrictHostKeyChecking=no -o ConnectTimeout=5 ubuntu@$SERVER_IP "echo 'SSH ready'" &> /dev/null; then
        echo -e "${GREEN}✅ Server is ready!${NC}"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "   Attempt $RETRY_COUNT/$MAX_RETRIES..."
    sleep 10
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo -e "${YELLOW}⚠️  Could not connect to server via SSH${NC}"
    echo "   Try manually: ssh -i ~/.ssh/id_rsa ubuntu@$SERVER_IP"
    echo "   Instance may still be booting"
    echo ""
fi
echo ""

# Setup swap and deploy dev Kafka
echo -e "${BLUE}Step 10: Configuring dev environment${NC}"
echo "----------------------------------------"
echo "This will:"
echo "  • Add 2GB swap space (critical for 1GB RAM)"
echo "  • Deploy single-broker Kafka"
echo "  • Deploy VEX API"
echo ""

cat > /tmp/setup-dev.sh <<'SETUPEOF'
#!/bin/bash
set -e

echo "=== Adding swap space ==="
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
echo "✅ Swap enabled"

echo ""
echo "=== Waiting for K3s setup to complete ==="
while [ ! -f /var/log/user-data-complete ]; do
    if [ -f /var/log/user-data.log ]; then
        tail -n 1 /var/log/user-data.log
    fi
    sleep 5
done
echo "✅ K3s setup complete"

echo ""
echo "=== Deploying dev-optimized Kafka ==="
cd /opt/sbom2cve
sudo kubectl apply -f k8s/kafka/kafka-cluster-dev.yaml
sudo kubectl apply -f k8s/kafka/topics-dev.yaml
echo "✅ Kafka manifests applied"

echo ""
echo "=== Waiting for Kafka to be ready (10-15 minutes on t2.micro) ==="
sudo kubectl wait kafka/sbom2cve-kafka \
    --for=condition=Ready \
    --timeout=900s \
    -n sbom2cve || echo "⚠️ Kafka may take longer on t2.micro"

echo ""
echo "=== Deployment status ==="
sudo kubectl get nodes
sudo kubectl get pods -n sbom2cve
sudo kubectl get kafka -n sbom2cve

echo ""
echo "✅ Dev environment ready!"
SETUPEOF

scp -i ~/.ssh/id_rsa -o StrictHostKeyChecking=no /tmp/setup-dev.sh ubuntu@$SERVER_IP:/tmp/
ssh -i ~/.ssh/id_rsa -o StrictHostKeyChecking=no ubuntu@$SERVER_IP "chmod +x /tmp/setup-dev.sh && /tmp/setup-dev.sh"

echo ""
echo -e "${GREEN}=========================================="
echo "✅ SBOM2CVE Dev Deployment Complete!"
echo -e "==========================================${NC}"
echo ""
echo "📊 Deployment Summary:"
echo "   Region: $AWS_REGION"
echo "   Server: $SERVER_IP"
echo "   Agent: $AGENT_IP"
echo "   Cost: ~\$2-5/month (Free Tier)"
echo ""
echo "🔗 Next Steps:"
echo ""
echo "1. SSH to server:"
echo "   ssh -i ~/.ssh/id_rsa ubuntu@$SERVER_IP"
echo ""
echo "2. Check Kafka status:"
echo "   sudo kubectl get kafka -n sbom2cve"
echo ""
echo "3. Setup local kubectl:"
echo "   scp -i ~/.ssh/id_rsa ubuntu@$SERVER_IP:/etc/rancher/k3s/k3s.yaml ~/.kube/sbom2cve-dev"
echo "   sed -i '' 's/127.0.0.1/$SERVER_IP/g' ~/.kube/sbom2cve-dev"
echo "   export KUBECONFIG=~/.kube/sbom2cve-dev"
echo "   kubectl get nodes"
echo ""
echo "4. Access VEX API:"
echo "   kubectl port-forward svc/vex-api 8080:80 -n sbom2cve &"
echo "   curl http://localhost:8080/health"
echo ""
echo "5. Test KEV producer:"
echo "   ssh ubuntu@$SERVER_IP"
echo "   cd /opt/sbom2cve"
echo "   python3 src/producers/kev_producer.py --once --bootstrap-servers sbom2cve-kafka-bootstrap.sbom2cve:9092"
echo ""
echo "💰 Cost-Saving Tips:"
echo "   • Stop instances when not in use: aws ec2 stop-instances --instance-ids <id>"
echo "   • Cost when stopped: ~\$5/month (EBS only)"
echo "   • Free Tier lasts 12 months from AWS account creation"
echo ""
echo "🗑️  To destroy everything:"
echo "   cd terraform/aws"
echo "   terraform destroy"
echo ""
echo -e "${GREEN}Happy testing! 🚀${NC}"
