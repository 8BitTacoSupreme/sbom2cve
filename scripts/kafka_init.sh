#!/bin/bash
# Initialize Kafka in KRaft mode (no Zookeeper)
# Run this once before starting Kafka for the first time

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "🔧 Initializing Kafka (KRaft mode)..."

# Create necessary directories
mkdir -p data/kafka/logs
mkdir -p logs

# Check if cluster ID exists
if [ -f data/kafka/cluster.id ]; then
    CLUSTER_ID=$(cat data/kafka/cluster.id)
    echo "📋 Using existing cluster ID: $CLUSTER_ID"
else
    # Generate a new cluster ID
    CLUSTER_ID=$(kafka-storage.sh random-uuid)
    echo "$CLUSTER_ID" > data/kafka/cluster.id
    echo "✨ Generated new cluster ID: $CLUSTER_ID"
fi

# Format the log directory
echo "📝 Formatting Kafka log directory..."
kafka-storage.sh format \
    -t "$CLUSTER_ID" \
    -c config/kafka/kraft-server.properties

echo ""
echo "✅ Kafka initialization complete!"
echo ""
echo "Next steps:"
echo "  1. Start Kafka: ./scripts/kafka_start.sh"
echo "  2. Or run full demo: ./scripts/demo_start.sh"
