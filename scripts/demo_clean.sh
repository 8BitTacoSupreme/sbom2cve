#!/bin/bash
# Clean all SBOM2CVE data and logs

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "🧹 Cleaning SBOM2CVE data and logs..."
echo ""

# Stop services first
echo "1. Stopping services..."
./scripts/demo_stop.sh
echo ""

# Clean logs
echo "2. Cleaning logs..."
rm -f logs/*.log
echo "    ✅ Logs cleaned"

# Clean Kafka data
echo "3. Cleaning Kafka data..."
if [ -d "data/kafka" ]; then
    rm -rf data/kafka/*
    echo "    ✅ Kafka data cleaned"
else
    echo "    ℹ️  No Kafka data to clean"
fi

echo ""
echo "✅ All clean! Ready for fresh start."
echo ""
echo "To start from scratch:"
echo "  ./scripts/demo_start.sh"
