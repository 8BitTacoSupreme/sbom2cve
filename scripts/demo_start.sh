#!/bin/bash
# Start the complete SBOM2CVE demo with one command
# NOTE: Run this inside a Flox environment (flox activate)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "════════════════════════════════════════════════════════════════"
echo "  SBOM2CVE Vulnerability Matcher - Nix/Flox Demo"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Check if we're in a Flox environment
if [ -z "$FLOX_ENV" ]; then
    echo "❌ Not in a Flox environment!"
    echo "   Please run: flox activate"
    exit 1
fi

# Initialize Kafka if needed
if [ ! -f data/kafka/cluster.id ]; then
    echo "🔧 First-time setup: Initializing Kafka..."
    ./scripts/kafka_init.sh
    echo ""
fi

# Start Kafka
echo "📦 Starting Kafka..."
./scripts/kafka_start.sh
echo ""

# Start Python services
echo "🐍 Starting Python services..."
./scripts/start_all.sh
echo ""

echo "════════════════════════════════════════════════════════════════"
echo "  ✅ SBOM2CVE Demo is Running!"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "🌐 Services:"
echo "   📊 Dashboard:  http://localhost:5001"
echo "   📨 Kafka:     localhost:9092"
echo ""
echo "📝 Logs:"
echo "   tail -f logs/kafka.log         # Kafka broker"
echo "   tail -f logs/matcher.log       # Vulnerability matching"
echo "   tail -f logs/alert_consumer.log # Formatted alerts"
echo "   tail -f logs/sbom_producer.log  # SBOM generation"
echo "   tail -f logs/cve_producer.log   # CVE publishing"
echo ""
echo "🛑 To stop:"
echo "   ./scripts/demo_stop.sh"
echo ""
echo "════════════════════════════════════════════════════════════════"
