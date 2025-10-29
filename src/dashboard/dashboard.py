#!/usr/bin/env python3
"""
Simple monitoring dashboard for SBOM2CVE message flow
Displays real-time Kafka topic metrics and recent messages
"""
import json
from kafka import KafkaConsumer, TopicPartition
from flask import Flask, render_template, jsonify
from collections import defaultdict, deque
import threading
import time

app = Flask(__name__)

# Store metrics and recent messages
metrics = {
    'sboms': {'count': 0, 'recent': deque(maxlen=10)},
    'cves': {'count': 0, 'recent': deque(maxlen=10)},
    'alerts': {'count': 0, 'recent': deque(maxlen=10)},
}

severity_counts = defaultdict(int)
last_update = time.time()


class DashboardMonitor:
    """Monitor Kafka topics and collect metrics"""

    def __init__(self, bootstrap_servers='localhost:9092'):
        self.bootstrap_servers = bootstrap_servers
        self.running = True

    def get_topic_message_count(self, topic):
        """Get total message count for a topic"""
        try:
            consumer = KafkaConsumer(
                bootstrap_servers=self.bootstrap_servers,
                consumer_timeout_ms=1000
            )

            partitions = consumer.partitions_for_topic(topic)
            if not partitions:
                consumer.close()
                return 0

            topic_partitions = [TopicPartition(topic, p) for p in partitions]
            consumer.assign(topic_partitions)
            consumer.seek_to_end()

            end_offsets = consumer.position(topic_partitions[0]) if topic_partitions else 0
            consumer.close()
            return end_offsets

        except Exception as e:
            print(f"Error getting count for {topic}: {e}")
            return 0

    def monitor_topic(self, topic, process_func=None):
        """Monitor a specific topic"""
        try:
            consumer = KafkaConsumer(
                topic,
                bootstrap_servers=self.bootstrap_servers,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',
                enable_auto_commit=True,
                group_id=f'dashboard-{topic}'
            )

            print(f"📊 Monitoring {topic}...")

            for message in consumer:
                if not self.running:
                    break

                data = message.value
                metrics[topic]['count'] += 1
                metrics[topic]['recent'].append(data)

                if process_func:
                    process_func(data)

                global last_update
                last_update = time.time()

            consumer.close()

        except Exception as e:
            print(f"Error monitoring {topic}: {e}")

    def process_alert(self, alert):
        """Process alert to track severity counts"""
        severity = alert.get('severity', 'UNKNOWN')
        severity_counts[severity] += 1

    def run(self):
        """Start monitoring all topics"""
        threads = [
            threading.Thread(target=self.monitor_topic, args=('sboms',), daemon=True),
            threading.Thread(target=self.monitor_topic, args=('cves',), daemon=True),
            threading.Thread(target=self.monitor_topic, args=('alerts', self.process_alert), daemon=True)
        ]

        for thread in threads:
            thread.start()

        return threads


# Initialize monitor
monitor = DashboardMonitor()


@app.route('/')
def index():
    """Render dashboard page"""
    return render_template('dashboard.html')


@app.route('/api/metrics')
def get_metrics():
    """API endpoint for current metrics"""
    return jsonify({
        'topics': {
            'sboms': {
                'count': metrics['sboms']['count'],
                'recent_count': len(metrics['sboms']['recent'])
            },
            'cves': {
                'count': metrics['cves']['count'],
                'recent_count': len(metrics['cves']['recent'])
            },
            'alerts': {
                'count': metrics['alerts']['count'],
                'recent_count': len(metrics['alerts']['recent'])
            }
        },
        'severity': dict(severity_counts),
        'last_update': last_update
    })


@app.route('/api/recent/<topic>')
def get_recent(topic):
    """Get recent messages for a topic"""
    if topic not in metrics:
        return jsonify({'error': 'Invalid topic'}), 400

    recent_messages = list(metrics[topic]['recent'])
    return jsonify({
        'topic': topic,
        'messages': recent_messages
    })


def start_dashboard(host='0.0.0.0', port=5001):
    """Start the dashboard server"""
    print(f"🚀 Starting dashboard on http://{host}:{port}")

    # Start monitoring in background
    monitor.run()

    # Start Flask app
    app.run(host=host, port=port, debug=False)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='SBOM2CVE Monitoring Dashboard')
    parser.add_argument('--host', default='0.0.0.0', help='Dashboard host')
    parser.add_argument('--port', type=int, default=5001, help='Dashboard port')
    parser.add_argument('--bootstrap-servers', default='localhost:9092',
                        help='Kafka bootstrap servers')

    args = parser.parse_args()

    monitor = DashboardMonitor(bootstrap_servers=args.bootstrap_servers)
    start_dashboard(host=args.host, port=args.port)
