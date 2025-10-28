#!/bin/bash
# Start Kafka using Docker (simpler approach)

set -e

echo "🚀 Starting Kafka with Docker..."

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed or not in PATH"
    echo "Please install Docker or use manual Kafka setup"
    exit 1
fi

# Check if Docker daemon is running, if not start Docker Desktop
if ! docker info &> /dev/null; then
    echo "🐳 Docker daemon not running, starting Docker Desktop..."

    # Start Docker Desktop (macOS)
    if [[ "$OSTYPE" == "darwin"* ]]; then
        open -a Docker
        echo "⏳ Waiting for Docker Desktop to start..."

        # Wait up to 60 seconds for Docker to be ready
        for i in {1..60}; do
            if docker info &> /dev/null; then
                echo "✅ Docker Desktop is ready!"
                break
            fi
            sleep 1
            if [ $i -eq 60 ]; then
                echo "❌ Docker Desktop failed to start within 60 seconds"
                exit 1
            fi
        done
    else
        echo "❌ Docker daemon is not running. Please start Docker manually."
        exit 1
    fi
fi

# Create a Docker network
docker network create kafka-network 2>/dev/null || true

# Start Zookeeper
echo "📦 Starting Zookeeper..."
docker run -d --name zookeeper \
    --network kafka-network \
    -p 2181:2181 \
    -e ZOOKEEPER_CLIENT_PORT=2181 \
    confluentinc/cp-zookeeper:latest 2>/dev/null || docker start zookeeper

sleep 5

# Start Kafka
echo "📦 Starting Kafka..."
docker run -d --name kafka \
    --network kafka-network \
    -p 9092:9092 \
    -e KAFKA_ZOOKEEPER_CONNECT=zookeeper:2181 \
    -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://localhost:9092 \
    -e KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1 \
    confluentinc/cp-kafka:latest 2>/dev/null || docker start kafka

echo "⏳ Waiting for Kafka to be ready..."
sleep 15

# Create topics
echo "📝 Creating Kafka topics..."
docker exec kafka kafka-topics --create --topic sboms --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1 --if-not-exists
docker exec kafka kafka-topics --create --topic cves --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1 --if-not-exists
docker exec kafka kafka-topics --create --topic alerts --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1 --if-not-exists

# List topics
echo "✅ Topics created:"
docker exec kafka kafka-topics --list --bootstrap-server localhost:9092

echo ""
echo "✅ Kafka setup complete!"
echo ""
echo "To stop Kafka:"
echo "  docker stop kafka zookeeper"
echo ""
echo "To remove Kafka containers:"
echo "  docker rm kafka zookeeper"
echo "  docker network rm kafka-network"
