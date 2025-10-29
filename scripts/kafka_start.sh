#!/bin/bash
# Start Kafka server in KRaft mode
# NOTE: Run this inside a Flox environment (flox activate)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Check if Kafka is already running
if pgrep -f "kafka.Kafka" > /dev/null; then
    echo "⚠️  Kafka is already running"
    echo "   PID: $(pgrep -f 'kafka.Kafka')"
    exit 0
fi

# Check if Kafka has been initialized
if [ ! -f data/kafka/cluster.id ]; then
    echo "❌ Kafka not initialized. Run ./scripts/kafka_init.sh first"
    exit 1
fi

echo "🚀 Starting Kafka server..."

# Start Kafka in background
$KAFKA_HOME/bin/kafka-server-start.sh \
    config/kafka/kraft-server.properties \
    > logs/kafka.log 2>&1 &

KAFKA_PID=$!
echo "📦 Kafka starting (PID: $KAFKA_PID)"

# Wait for Kafka to be ready
echo "⏳ Waiting for Kafka to be ready..."
for i in {1..30}; do
    if $KAFKA_HOME/bin/kafka-broker-api-versions.sh \
        --bootstrap-server localhost:9092 &> /dev/null; then
        echo "✅ Kafka is ready!"
        break
    fi
    sleep 2
    if [ $i -eq 30 ]; then
        echo "❌ Kafka failed to start within 60 seconds"
        echo "   Check logs/kafka.log for details"
        exit 1
    fi
done

# Create topics
echo "📝 Creating topics..."
$KAFKA_HOME/bin/kafka-topics.sh --create --if-not-exists \
    --topic sboms --bootstrap-server localhost:9092 \
    --partitions 3 --replication-factor 1

$KAFKA_HOME/bin/kafka-topics.sh --create --if-not-exists \
    --topic cves --bootstrap-server localhost:9092 \
    --partitions 3 --replication-factor 1

$KAFKA_HOME/bin/kafka-topics.sh --create --if-not-exists \
    --topic alerts --bootstrap-server localhost:9092 \
    --partitions 3 --replication-factor 1

echo "✅ Topics created"

# List topics
echo ""
echo "📋 Available topics:"
$KAFKA_HOME/bin/kafka-topics.sh --list --bootstrap-server localhost:9092 | grep -E "^(sboms|cves|alerts)$" | sed 's/^/   - /'

echo ""
echo "✅ Kafka is running!"
echo "   📨 Bootstrap server: localhost:9092"
echo "   📝 Logs: tail -f logs/kafka.log"
echo ""
