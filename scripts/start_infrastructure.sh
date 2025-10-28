#!/bin/bash
# Start SBOM2CVE Infrastructure using Confluent Platform

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🚀 Starting SBOM2CVE Infrastructure..."

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed or not in PATH"
    echo "Please install Docker or use manual Kafka setup"
    exit 1
fi

# Check if Docker Compose is available
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null 2>&1; then
    echo "❌ Docker Compose is not installed"
    echo "Please install Docker Compose"
    exit 1
fi

# Determine which docker compose command to use
if docker compose version &> /dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
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

# Change to project root
cd "$PROJECT_ROOT"

# Start services with Docker Compose
echo ""
echo "📦 Starting Confluent Platform services..."
echo "   1. Kafka Broker (KRaft mode)"
echo "   2. Schema Registry"
echo "   3. Kafka Topics (sboms, cves, alerts)"
echo "   4. Flink JobManager"
echo "   5. Flink TaskManager"
echo ""

$DOCKER_COMPOSE up -d

echo ""
echo "⏳ Waiting for services to be ready..."
echo ""

# Wait for broker to be healthy
echo "⏳ Waiting for Kafka broker..."
for i in {1..30}; do
    if docker exec broker kafka-broker-api-versions --bootstrap-server localhost:9092 &> /dev/null; then
        echo "✅ Kafka broker is ready"
        break
    fi
    sleep 2
    if [ $i -eq 30 ]; then
        echo "❌ Kafka broker failed to become ready"
        exit 1
    fi
done

# Wait for schema registry
echo "⏳ Waiting for Schema Registry..."
for i in {1..20}; do
    if curl -sf http://localhost:8081/subjects &> /dev/null; then
        echo "✅ Schema Registry is ready"
        break
    fi
    sleep 2
    if [ $i -eq 20 ]; then
        echo "❌ Schema Registry failed to become ready"
        exit 1
    fi
done

# Wait for Flink
echo "⏳ Waiting for Flink JobManager..."
for i in {1..20}; do
    if curl -sf http://localhost:9081/overview &> /dev/null; then
        echo "✅ Flink JobManager is ready"
        break
    fi
    sleep 2
    if [ $i -eq 20 ]; then
        echo "❌ Flink JobManager failed to become ready"
        exit 1
    fi
done

echo "⏳ Waiting for Flink TaskManager..."
sleep 5
echo "✅ Flink TaskManager should be ready"

echo ""
echo "📝 Verifying Kafka topics..."
sleep 2

# List topics
TOPICS=$(docker exec broker kafka-topics --list --bootstrap-server localhost:9092 2>/dev/null || echo "")

if echo "$TOPICS" | grep -q "sboms\|cves\|alerts"; then
    echo "✅ Topics verified:"
    echo "$TOPICS" | grep -E "^(sboms|cves|alerts)$" | sed 's/^/   - /'
else
    echo "⚠️  Topics may not be fully created yet. Checking init container..."
    $DOCKER_COMPOSE logs kafka-init
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "✅ SBOM2CVE Infrastructure is ready!"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "Services available at:"
echo "  📊 Flink Dashboard:     http://localhost:9081"
echo "  🔧 Schema Registry:     http://localhost:8081"
echo "  📨 Kafka:              localhost:9092"
echo ""
echo "To view logs:"
echo "  $DOCKER_COMPOSE logs -f [service]"
echo ""
echo "To stop all services:"
echo "  $DOCKER_COMPOSE down"
echo ""
echo "To stop and remove all data:"
echo "  $DOCKER_COMPOSE down -v"
echo "════════════════════════════════════════════════════════════════"
