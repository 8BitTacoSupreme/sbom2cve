#!/bin/bash
# K3s Server (Control Plane) User Data Script
# Automatically installs K3s and deploys SBOM2CVE stack

set -e

# Logging
exec > >(tee /var/log/user-data.log)
exec 2>&1

echo "=========================================="
echo "SBOM2CVE K3s Server Setup"
echo "=========================================="
echo "Started: $(date)"
echo ""

# Update system
echo "📦 Updating system packages..."
apt-get update
apt-get upgrade -y

# Install dependencies
echo "📦 Installing dependencies..."
apt-get install -y \
    curl \
    wget \
    git \
    jq \
    unzip \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release

# Install K3s server
echo "🚀 Installing K3s server..."
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server \
    --cluster-init \
    --write-kubeconfig-mode 644 \
    --disable traefik \
    --node-name ${cluster_name}-server \
    --token ${cluster_token}" sh -

# Wait for K3s to be ready
echo "⏳ Waiting for K3s to be ready..."
sleep 10
until kubectl get nodes | grep -q Ready; do
    echo "Waiting for K3s..."
    sleep 5
done

echo "✅ K3s server ready!"
echo ""

# Install Helm
echo "📦 Installing Helm..."
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Add Helm repositories
echo "📦 Adding Helm repositories..."
helm repo add strimzi https://strimzi.io/charts/
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Clone SBOM2CVE repository
echo "📥 Cloning SBOM2CVE repository..."
cd /opt
git clone https://github.com/8BitTacoSupreme/sbom2cve.git
cd sbom2cve
git checkout future-state-mvp

# Create namespace
echo "📦 Creating sbom2cve namespace..."
kubectl create namespace sbom2cve

# Install Strimzi Kafka Operator
echo "📦 Installing Strimzi Kafka Operator..."
helm install kafka-operator strimzi/strimzi-kafka-operator \
    --namespace sbom2cve \
    --set watchNamespaces="{sbom2cve}"

# Wait for operator to be ready
echo "⏳ Waiting for Kafka operator..."
kubectl wait deployment/strimzi-cluster-operator \
    --for=condition=Available \
    --timeout=300s \
    -n sbom2cve

echo "✅ Kafka operator ready!"
echo ""

# Deploy Kafka cluster
echo "📦 Deploying Kafka cluster..."
kubectl apply -f k8s/kafka/kafka-cluster.yaml

# Deploy Kafka topics (will be created once Kafka is ready)
echo "📦 Creating Kafka topics..."
kubectl apply -f k8s/kafka/topics.yaml

# Note: Kafka deployment takes 5-10 minutes
# VEX API deployment will be manual after Kafka is ready

echo ""
echo "=========================================="
echo "✅ K3s Server Setup Complete!"
echo "=========================================="
echo "Completed: $(date)"
echo ""
echo "Next steps:"
echo "1. Wait for Kafka to be ready (5-10 minutes):"
echo "   kubectl wait kafka/sbom2cve-kafka --for=condition=Ready -n sbom2cve --timeout=600s"
echo ""
echo "2. Build and deploy VEX API:"
echo "   docker build -t sbom2cve/vex-api:latest -f docker/Dockerfile.vex-api ."
echo "   kubectl apply -f k8s/apps/vex-api.yaml"
echo ""
echo "3. Access from local machine:"
echo "   scp ubuntu@$(ec2-metadata --public-ipv4 | cut -d' ' -f2):/etc/rancher/k3s/k3s.yaml ~/.kube/sbom2cve-config"
echo ""
