#!/bin/bash
# Setup Kafka - Start Zookeeper and Kafka, create topics

set -e

echo "🚀 Setting up Kafka..."

# Find Kafka installation
KAFKA_DIR=$(dirname $(dirname $(which kafka-server-start.sh)))

echo "📁 Kafka directory: $KAFKA_DIR"

# Start Zookeeper in background
echo "🔧 Starting Zookeeper..."
zookeeper-server-start.sh $KAFKA_DIR/config/zookeeper.properties > /tmp/zookeeper.log 2>&1 &
ZOOKEEPER_PID=$!
echo "Zookeeper PID: $ZOOKEEPER_PID"

# Wait for Zookeeper to start
sleep 5

# Start Kafka in background
echo "🔧 Starting Kafka..."
kafka-server-start.sh $KAFKA_DIR/config/server.properties > /tmp/kafka.log 2>&1 &
KAFKA_PID=$!
echo "Kafka PID: $KAFKA_PID"

# Wait for Kafka to start
sleep 10

# Create topics
echo "📝 Creating Kafka topics..."
kafka-topics.sh --create --topic sboms --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1 --if-not-exists
kafka-topics.sh --create --topic cves --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1 --if-not-exists
kafka-topics.sh --create --topic alerts --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1 --if-not-exists

# List topics
echo "✅ Topics created:"
kafka-topics.sh --list --bootstrap-server localhost:9092

echo ""
echo "✅ Kafka setup complete!"
echo "Zookeeper PID: $ZOOKEEPER_PID"
echo "Kafka PID: $KAFKA_PID"
echo ""
echo "To stop Kafka and Zookeeper:"
echo "  kill $KAFKA_PID $ZOOKEEPER_PID"
