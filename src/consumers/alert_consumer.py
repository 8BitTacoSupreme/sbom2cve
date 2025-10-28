#!/usr/bin/env python3
"""
Alert Consumer - Consumes vulnerability alerts from Kafka and displays them
"""
import json
from kafka import KafkaConsumer
from datetime import datetime
from typing import Dict


class AlertConsumer:
    """Kafka consumer for vulnerability alerts"""

    def __init__(self, bootstrap_servers: str = "localhost:9092", topic: str = "alerts"):
        self.consumer = KafkaConsumer(
            topic,
            bootstrap_servers=bootstrap_servers,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='latest',
            enable_auto_commit=True,
            group_id='alert-consumer-group'
        )
        self.topic = topic

    def format_alert(self, alert: Dict) -> str:
        """Format an alert for display"""
        lines = []
        lines.append("=" * 80)
        lines.append(f"🚨 VULNERABILITY ALERT - {alert.get('cve_id', 'UNKNOWN')}")
        lines.append("=" * 80)
        lines.append(f"Alert ID:         {alert.get('alert_id', 'N/A')}")
        lines.append(f"Timestamp:        {alert.get('timestamp', 'N/A')}")
        lines.append(f"SBOM:             {alert.get('sbom_name', 'N/A')}")
        lines.append(f"")
        lines.append(f"CVE ID:           {alert.get('cve_id', 'N/A')}")
        lines.append(f"Severity:         {alert.get('severity', 'UNKNOWN')}")
        lines.append(f"CVSS Score:       {alert.get('cvss_score', 'N/A')}")
        lines.append(f"Confidence:       {alert.get('confidence_score', 0) * 100:.1f}%")
        lines.append(f"Match Method:     {alert.get('match_method', 'N/A')}")
        lines.append(f"")

        pkg = alert.get('affected_package', {})
        lines.append(f"Affected Package:")
        lines.append(f"  Name:           {pkg.get('name', 'N/A')}")
        lines.append(f"  Version:        {pkg.get('version', 'N/A')}")
        lines.append(f"  PURL:           {pkg.get('purl', 'N/A')}")
        lines.append(f"")

        desc = alert.get('description', 'No description available')
        lines.append(f"Description:")
        lines.append(f"  {desc}")
        lines.append(f"")

        refs = alert.get('references', [])
        if refs:
            lines.append(f"References:")
            for ref in refs:
                lines.append(f"  - {ref}")
        lines.append("=" * 80)
        lines.append("")

        return "\n".join(lines)

    def consume_alerts(self):
        """Consume and display alerts continuously"""
        print(f"🔍 Listening for alerts on topic '{self.topic}'...")
        print(f"Waiting for vulnerability matches...\n")

        try:
            count = 0
            for message in self.consumer:
                count += 1
                alert = message.value

                # Print formatted alert
                print(self.format_alert(alert))

                # Print summary
                severity = alert.get('severity', 'UNKNOWN')
                cve_id = alert.get('cve_id', 'UNKNOWN')
                pkg_name = alert.get('affected_package', {}).get('name', 'UNKNOWN')

                color_code = {
                    'CRITICAL': '\033[91m',  # Red
                    'HIGH': '\033[93m',       # Yellow
                    'MEDIUM': '\033[94m',     # Blue
                    'LOW': '\033[92m',        # Green
                }.get(severity, '\033[0m')

                reset_code = '\033[0m'

                print(f"[{count}] {color_code}{severity}{reset_code} - {cve_id} affects {pkg_name}")
                print()

        except KeyboardInterrupt:
            print("\n\nStopping alert consumer...")
        finally:
            self.consumer.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Alert Consumer")
    parser.add_argument("--bootstrap-servers", default="localhost:9092", help="Kafka bootstrap servers")
    parser.add_argument("--topic", default="alerts", help="Kafka topic for alerts")

    args = parser.parse_args()

    consumer = AlertConsumer(
        bootstrap_servers=args.bootstrap_servers,
        topic=args.topic
    )

    consumer.consume_alerts()
