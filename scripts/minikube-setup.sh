#!/bin/bash
set -e

# SBOM2CVE Minikube Local Development Setup
# For macOS with QEMU driver (no Docker required)

echo "🚀 SBOM2CVE Minikube Local Development Setup"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check prerequisites
echo -e "${BLUE}Step 1: Checking prerequisites${NC}"
echo "----------------------------------------"

if ! command -v minikube &> /dev/null; then
    echo "❌ minikube not found"
    echo "   Install: brew install minikube"
    exit 1
fi
echo "✅ minikube installed: $(minikube version --short)"

if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl not found"
    echo "   Install: brew install kubernetes-cli"
    exit 1
fi
echo "✅ kubectl installed: $(kubectl version --client --short 2>/dev/null || kubectl version --client)"

if ! command -v helm &> /dev/null; then
    echo "❌ helm not found"
    echo "   Install: brew install helm"
    exit 1
fi
echo "✅ helm installed: $(helm version --short)"
echo ""

# Start Minikube
echo -e "${BLUE}Step 2: Starting Minikube cluster${NC}"
echo "----------------------------------------"
echo "📝 Configuration:"
echo "   Driver: qemu (no Docker required)"
echo "   CPUs: 4"
echo "   Memory: 8GB"
echo "   Disk: 40GB"
echo ""

# Check if minikube is already running
if minikube status &> /dev/null; then
    echo "⚠️  Minikube already running"
    echo "   To restart: minikube delete && ./scripts/minikube-setup.sh"
    read -p "   Continue with existing cluster? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Setup cancelled"
        exit 0
    fi
else
    echo "🚀 Starting Minikube..."
    minikube start \
        --driver=qemu \
        --cpus=4 \
        --memory=8192 \
        --disk-size=40g \
        --kubernetes-version=v1.28.0

    echo "✅ Minikube started successfully"
fi
echo ""

# Configure kubectl
echo -e "${BLUE}Step 3: Configuring kubectl${NC}"
echo "----------------------------------------"
kubectl config use-context minikube
echo "✅ kubectl context set to minikube"
echo ""

# Create namespace
echo -e "${BLUE}Step 4: Creating namespace${NC}"
echo "----------------------------------------"
kubectl create namespace sbom2cve --dry-run=client -o yaml | kubectl apply -f -
echo "✅ Namespace 'sbom2cve' ready"
echo ""

# Add Helm repositories
echo -e "${BLUE}Step 5: Adding Helm repositories${NC}"
echo "----------------------------------------"
echo "📦 Adding Strimzi repository..."
helm repo add strimzi https://strimzi.io/charts/ 2>/dev/null || true
echo "📦 Adding Prometheus repository..."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>/dev/null || true
echo "🔄 Updating repositories..."
helm repo update
echo "✅ Helm repositories ready"
echo ""

# Install Strimzi Kafka Operator
echo -e "${BLUE}Step 6: Installing Strimzi Kafka Operator${NC}"
echo "----------------------------------------"
if helm list -n sbom2cve | grep -q kafka-operator; then
    echo "⚠️  Kafka operator already installed"
    echo "   To reinstall: helm uninstall kafka-operator -n sbom2cve"
else
    echo "📥 Installing Strimzi Kafka Operator..."
    helm install kafka-operator strimzi/strimzi-kafka-operator \
        --namespace sbom2cve \
        --set watchNamespaces="{sbom2cve}"

    echo "⏳ Waiting for operator to be ready..."
    kubectl wait deployment/strimzi-cluster-operator \
        --for=condition=Available \
        --timeout=300s \
        -n sbom2cve

    echo "✅ Kafka operator installed"
fi
echo ""

# Deploy Kafka Cluster
echo -e "${BLUE}Step 7: Deploying Kafka cluster${NC}"
echo "----------------------------------------"
echo "📝 Configuration:"
echo "   Brokers: 3"
echo "   Zookeeper: 3"
echo "   Storage: 20Gi per broker (ephemeral for local dev)"
echo ""

if kubectl get kafka sbom2cve-kafka -n sbom2cve &> /dev/null; then
    echo "⚠️  Kafka cluster already exists"
    echo "   Status: $(kubectl get kafka sbom2cve-kafka -n sbom2cve -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}')"
else
    echo "📥 Deploying Kafka cluster..."
    kubectl apply -f k8s/kafka/kafka-cluster.yaml

    echo "⏳ Waiting for Kafka to be ready (this may take 3-5 minutes)..."
    kubectl wait kafka/sbom2cve-kafka \
        --for=condition=Ready \
        --timeout=600s \
        -n sbom2cve

    echo "✅ Kafka cluster deployed"
fi
echo ""

# Create Kafka Topics
echo -e "${BLUE}Step 8: Creating Kafka topics${NC}"
echo "----------------------------------------"
echo "📝 Topics:"
echo "   • purl-mapping-rules (1 partition, compacted)"
echo "   • cves-enriched (500 partitions, compacted)"
echo "   • kev-feed (1 partition, compacted)"
echo "   • vex-statements (10 partitions, compacted)"
echo "   • alerts-enriched (100 partitions)"
echo "   • sbom-packages-by-purl (500 partitions, compacted)"
echo "   • cve-rules-by-purl (500 partitions, compacted)"
echo ""

kubectl apply -f k8s/kafka/topics.yaml

echo "⏳ Waiting for topics to be ready..."
sleep 10
echo "✅ Kafka topics created"
echo ""

# Build VEX API Docker image
echo -e "${BLUE}Step 9: Building VEX API Docker image${NC}"
echo "----------------------------------------"
echo "🔧 Setting Minikube Docker environment..."
eval $(minikube docker-env)

echo "🏗️  Building VEX API image..."
docker build -t sbom2cve/vex-api:latest -f docker/Dockerfile.vex-api .
echo "✅ VEX API image built"
echo ""

# Deploy VEX API
echo -e "${BLUE}Step 10: Deploying VEX API${NC}"
echo "----------------------------------------"
kubectl apply -f k8s/apps/vex-api.yaml
echo "⏳ Waiting for VEX API to be ready..."
kubectl wait deployment/vex-api \
    --for=condition=Available \
    --timeout=120s \
    -n sbom2cve
echo "✅ VEX API deployed"
echo ""

# Display cluster information
echo -e "${GREEN}=========================================="
echo "✅ SBOM2CVE Local Development Setup Complete!"
echo -e "==========================================${NC}"
echo ""
echo "📊 Cluster Status:"
kubectl get pods -n sbom2cve
echo ""

echo "🔗 Useful Commands:"
echo ""
echo "  # View all pods"
echo "  kubectl get pods -n sbom2cve"
echo ""
echo "  # Check Kafka status"
echo "  kubectl get kafka -n sbom2cve"
echo ""
echo "  # List Kafka topics"
echo "  kubectl get kafkatopics -n sbom2cve"
echo ""
echo "  # Port forward Kafka (for local producers/consumers)"
echo "  kubectl port-forward svc/sbom2cve-kafka-bootstrap 9092:9092 -n sbom2cve"
echo ""
echo "  # Port forward VEX API"
echo "  kubectl port-forward svc/vex-api 8080:80 -n sbom2cve"
echo ""
echo "  # View VEX API logs"
echo "  kubectl logs -f deployment/vex-api -n sbom2cve"
echo ""
echo "  # Access Minikube dashboard"
echo "  minikube dashboard"
echo ""

echo "🧪 Quick Test:"
echo ""
echo "  # Terminal 1: Port forward VEX API"
echo "  kubectl port-forward svc/vex-api 8080:80 -n sbom2cve"
echo ""
echo "  # Terminal 2: Test health endpoint"
echo "  curl http://localhost:8080/health"
echo ""

echo "🛑 To stop Minikube:"
echo "  minikube stop"
echo ""

echo "🗑️  To delete Minikube cluster:"
echo "  minikube delete"
echo ""

echo -e "${GREEN}Happy testing! 🚀${NC}"
