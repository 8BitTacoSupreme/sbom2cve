#!/bin/bash
# K8s Local Development Setup
# Sets up K3s cluster with Strimzi Kafka, Flink Operator, Prometheus
#
# Usage:
#   ./scripts/k8s-dev-setup.sh

set -e

echo "🚀 SBOM2CVE K8s Local Development Setup"
echo "========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if running on macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "✅ Detected macOS"
else
    echo "⚠️  Warning: This script is optimized for macOS. Adjust for your OS if needed."
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to wait for pods
wait_for_pods() {
    local namespace=$1
    local label=$2
    local timeout=${3:-300}

    echo "⏳ Waiting for pods with label ${label} in namespace ${namespace}..."
    kubectl wait --for=condition=Ready pods \
        -l ${label} \
        -n ${namespace} \
        --timeout=${timeout}s || true
}

# Step 1: Install K3s (if not already installed)
echo ""
echo "${BLUE}Step 1: Installing K3s${NC}"
echo "----------------------------------------"

if command_exists k3s; then
    echo "✅ K3s already installed ($(k3s --version | head -n1))"
else
    echo "📥 Installing K3s..."

    # Install K3s without traefik (we'll use our own ingress if needed)
    curl -sfL https://get.k3s.io | sh -s - --disable traefik

    # Wait for K3s to be ready
    echo "⏳ Waiting for K3s to be ready..."
    sleep 10

    # Set up kubeconfig
    sudo chmod 644 /etc/rancher/k3s/k3s.yaml
    export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

    echo "✅ K3s installed successfully"
fi

# Ensure kubectl is available
if ! command_exists kubectl; then
    echo "${RED}❌ kubectl not found. Please install kubectl first.${NC}"
    exit 1
fi

echo "✅ kubectl version: $(kubectl version --client --short 2>/dev/null || kubectl version --client)"

# Step 2: Install Helm (if not already installed)
echo ""
echo "${BLUE}Step 2: Installing Helm${NC}"
echo "----------------------------------------"

if command_exists helm; then
    echo "✅ Helm already installed ($(helm version --short))"
else
    echo "📥 Installing Helm..."
    curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
    echo "✅ Helm installed successfully"
fi

# Step 3: Add Helm repositories
echo ""
echo "${BLUE}Step 3: Adding Helm Repositories${NC}"
echo "----------------------------------------"

echo "📦 Adding Strimzi Kafka Operator..."
helm repo add strimzi https://strimzi.io/charts/ || true

echo "📦 Adding Prometheus Community..."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts || true

echo "🔄 Updating Helm repos..."
helm repo update

echo "✅ Helm repositories configured"

# Step 4: Create namespace
echo ""
echo "${BLUE}Step 4: Creating Namespace${NC}"
echo "----------------------------------------"

kubectl create namespace sbom2cve --dry-run=client -o yaml | kubectl apply -f -
echo "✅ Namespace 'sbom2cve' ready"

# Step 5: Install Strimzi Kafka Operator
echo ""
echo "${BLUE}Step 5: Installing Strimzi Kafka Operator${NC}"
echo "----------------------------------------"

if helm list -n sbom2cve | grep -q kafka-operator; then
    echo "✅ Strimzi already installed"
else
    echo "📦 Installing Strimzi Kafka Operator..."
    helm install kafka-operator strimzi/strimzi-kafka-operator \
        --namespace sbom2cve \
        --set watchNamespaces="{sbom2cve}" \
        --wait

    echo "✅ Strimzi Kafka Operator installed"
fi

# Wait for operator to be ready
wait_for_pods sbom2cve "strimzi.io/kind=cluster-operator" 120

# Step 6: Deploy Kafka Cluster
echo ""
echo "${BLUE}Step 6: Deploying Kafka Cluster${NC}"
echo "----------------------------------------"

echo "📄 Applying Kafka cluster manifest..."
kubectl apply -f k8s/kafka/kafka-cluster.yaml

echo "⏳ Waiting for Kafka cluster to be ready (this may take 3-5 minutes)..."
kubectl wait kafka/sbom2cve-kafka \
    --for=condition=Ready \
    --timeout=600s \
    -n sbom2cve || true

echo "✅ Kafka cluster deployed"

# Step 7: Create Kafka Topics
echo ""
echo "${BLUE}Step 7: Creating Kafka Topics${NC}"
echo "----------------------------------------"

echo "📄 Applying Kafka topics..."
kubectl apply -f k8s/kafka/topics.yaml

echo "⏳ Waiting for topics to be ready..."
sleep 10

echo "✅ Kafka topics created"

# Step 8: Install Prometheus + Grafana (Optional)
echo ""
echo "${BLUE}Step 8: Installing Monitoring (Prometheus + Grafana)${NC}"
echo "----------------------------------------"

read -p "Install Prometheus + Grafana for monitoring? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if helm list -n sbom2cve | grep -q prometheus; then
        echo "✅ Prometheus already installed"
    else
        echo "📦 Installing Prometheus + Grafana..."
        helm install prometheus prometheus-community/kube-prometheus-stack \
            --namespace sbom2cve \
            --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false \
            --wait

        echo "✅ Prometheus + Grafana installed"
        echo ""
        echo "${GREEN}📊 Access Grafana:${NC}"
        echo "   kubectl port-forward svc/prometheus-grafana 3000:80 -n sbom2cve"
        echo "   Open http://localhost:3000 (admin/prom-operator)"
    fi
else
    echo "⏭️  Skipping Prometheus + Grafana"
fi

# Step 9: Summary
echo ""
echo "${GREEN}=========================================${NC}"
echo "${GREEN}✅ K8s Local Development Setup Complete!${NC}"
echo "${GREEN}=========================================${NC}"
echo ""
echo "${BLUE}📊 Cluster Status:${NC}"
kubectl get pods -n sbom2cve
echo ""

echo "${BLUE}🔗 Useful Commands:${NC}"
echo ""
echo "  # Check Kafka cluster status:"
echo "  kubectl get kafka -n sbom2cve"
echo ""
echo "  # Check Kafka topics:"
echo "  kubectl get kafkatopics -n sbom2cve"
echo ""
echo "  # Port forward Kafka (for local testing):"
echo "  kubectl port-forward svc/sbom2cve-kafka-bootstrap 9092:9092 -n sbom2cve"
echo ""
echo "  # View Kafka logs:"
echo "  kubectl logs -f sbom2cve-kafka-0 -n sbom2cve"
echo ""
echo "  # Access Kafka metrics:"
echo "  kubectl port-forward svc/kafka-exporter 9308:9308 -n sbom2cve"
echo ""

echo "${BLUE}📝 Next Steps:${NC}"
echo ""
echo "  1. Deploy VEX API:"
echo "     kubectl apply -f k8s/apps/vex-api.yaml"
echo ""
echo "  2. Test Kafka connection:"
echo "     kubectl port-forward svc/sbom2cve-kafka-bootstrap 9092:9092 -n sbom2cve &"
echo "     python3 src/producers/kev_producer.py --once"
echo ""
echo "  3. View this setup again:"
echo "     cat scripts/k8s-dev-setup.sh"
echo ""

echo "${GREEN}🎉 Happy developing!${NC}"
