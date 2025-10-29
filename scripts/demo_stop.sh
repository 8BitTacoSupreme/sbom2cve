#!/bin/bash
# Stop all SBOM2CVE services

echo "🛑 Stopping all SBOM2CVE services..."

# Stop Python services
echo "  Stopping Python services..."
pkill -f 'python3 src/' && echo "    ✅ Python services stopped" || echo "    ℹ️  No Python services running"

# Stop Kafka
echo "  Stopping Kafka..."
./scripts/kafka_stop.sh

echo ""
echo "✅ All services stopped!"
