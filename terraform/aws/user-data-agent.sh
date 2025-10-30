#!/bin/bash
# K3s Agent (Worker) User Data Script
# Automatically joins K3s cluster

set -e

# Logging
exec > >(tee /var/log/user-data.log)
exec 2>&1

echo "=========================================="
echo "SBOM2CVE K3s Agent Setup"
echo "=========================================="
echo "Started: $(date)"
echo ""

# Update system
echo "📦 Updating system packages..."
apt-get update
apt-get upgrade -y

# Install dependencies
echo "📦 Installing dependencies..."
apt-get install -y curl wget git jq

# Wait for server to be ready (K3s API must be accessible)
echo "⏳ Waiting for K3s server to be ready..."
until curl -k --silent --max-time 5 https://${server_ip}:6443 > /dev/null 2>&1; do
    echo "Waiting for K3s server at ${server_ip}:6443..."
    sleep 10
done

echo "✅ K3s server is reachable!"
echo ""

# Install K3s agent
echo "🚀 Installing K3s agent..."
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="agent \
    --server https://${server_ip}:6443 \
    --token ${cluster_token} \
    --node-name ${cluster_name}-agent-$(ec2-metadata --instance-id | cut -d' ' -f2)" sh -

# Wait for agent to join
echo "⏳ Waiting for agent to join cluster..."
sleep 10

echo ""
echo "=========================================="
echo "✅ K3s Agent Setup Complete!"
echo "=========================================="
echo "Completed: $(date)"
echo ""
echo "Agent should now be visible on server:"
echo "  kubectl get nodes"
echo ""
