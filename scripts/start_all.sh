#!/bin/bash
# Start all SBOM2CVE components
# NOTE: Run this inside a Flox environment (flox activate)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Ensure logs directory exists
mkdir -p logs

echo "🚀 Starting all SBOM2CVE components..."
echo ""

# Start Nix SBOM Producer (using Flox environment by default)
echo "📦 Starting Nix SBOM Producer (Flox environment mode)..."
python3 src/producers/nix_sbom_producer.py --interval 10 > logs/sbom_producer.log 2>&1 &
SBOM_PID=$!
echo "   PID: $SBOM_PID"

# Start Nix CVE Producer
echo "🔒 Starting Nix CVE Producer..."
python3 src/producers/nix_cve_producer.py --interval 7 > logs/cve_producer.log 2>&1 &
CVE_PID=$!
echo "   PID: $CVE_PID"

# Start Matcher
echo "🔄 Starting Matcher..."
python3 src/matchers/simple_matcher.py > logs/matcher.log 2>&1 &
MATCHER_PID=$!
echo "   PID: $MATCHER_PID"

# Start Alert Consumer
echo "🚨 Starting Alert Consumer..."
python3 src/consumers/alert_consumer.py > logs/alert_consumer.log 2>&1 &
CONSUMER_PID=$!
echo "   PID: $CONSUMER_PID"

# Start Dashboard
echo "📊 Starting Dashboard..."
python3 src/dashboard/dashboard.py > logs/dashboard.log 2>&1 &
DASHBOARD_PID=$!
echo "   PID: $DASHBOARD_PID"

echo ""
echo "✅ All components started!"
echo ""
echo "Services:"
echo "  📊 Dashboard:          http://localhost:5001"
echo "  📨 Kafka:             localhost:9092"
echo ""
echo "Logs:"
echo "  tail -f logs/sbom_producer.log"
echo "  tail -f logs/cve_producer.log"
echo "  tail -f logs/matcher.log"
echo "  tail -f logs/alert_consumer.log"
echo "  tail -f logs/dashboard.log"
echo ""
echo "To stop all services:"
echo "  pkill -f 'python3 src/'"
echo ""
