#!/bin/bash
# Stop the complete SBOM2CVE demo

set -e

echo "════════════════════════════════════════════════════════════════"
echo "  Stopping SBOM2CVE Demo..."
echo "════════════════════════════════════════════════════════════════"
echo ""

# Stop Python services
echo "🐍 Stopping Python services..."
pkill -f 'python3 src/' 2>/dev/null || echo "   (no Python services running)"

# Stop Kafka
echo "📦 Stopping Kafka..."
./scripts/kafka_stop.sh

echo ""
echo "✅ Demo stopped"
echo ""
