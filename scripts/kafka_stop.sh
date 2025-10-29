#!/bin/bash
# Stop Kafka server

set -e

echo "🛑 Stopping Kafka..."

# Find and kill Kafka process
if pgrep -f "kafka.Kafka" > /dev/null; then
    pkill -f "kafka.Kafka"
    echo "✅ Kafka stopped"
else
    echo "⚠️  Kafka is not running"
fi
