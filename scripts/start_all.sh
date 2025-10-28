#!/bin/bash
# Start all SBOM2CVE components

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Activate virtual environment
source venv/bin/activate

echo "🚀 Starting all SBOM2CVE components..."
echo ""

# Start SBOM Producer
echo "📦 Starting SBOM Producer..."
python3 src/producers/sbom_producer.py > logs/sbom_producer.log 2>&1 &
SBOM_PID=$!
echo "   PID: $SBOM_PID"

# Start CVE Producer
echo "🔒 Starting CVE Producer..."
python3 src/producers/cve_producer.py > logs/cve_producer.log 2>&1 &
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
echo "  📊 Dashboard:          http://localhost:5000"
echo "  📊 Flink Dashboard:    http://localhost:9081"
echo "  🔧 Schema Registry:    http://localhost:8081"
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
