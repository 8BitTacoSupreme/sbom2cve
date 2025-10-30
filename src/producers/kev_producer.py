#!/usr/bin/env python3
"""
KEV Feed Producer

Fetches CISA Known Exploited Vulnerabilities (KEV) catalog and publishes to Kafka.
KEV data is used to boost risk scores for actively exploited CVEs.

CISA KEV Catalog: https://www.cisa.gov/known-exploited-vulnerabilities-catalog
API Endpoint: https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json
"""

import requests
import json
from kafka import KafkaProducer
from datetime import datetime, timezone
import time
import argparse


class KEVProducer:
    """
    Fetch CISA KEV (Known Exploited Vulnerabilities) catalog and publish to Kafka.

    KEV catalog contains CVEs with evidence of active exploitation in the wild.
    This is a critical signal for risk scoring (25% weight).
    """

    KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"

    def __init__(self, bootstrap_servers='localhost:9092', topic='kev-feed'):
        """
        Initialize KEV producer.

        Args:
            bootstrap_servers: Kafka broker address
            topic: Kafka topic for KEV records
        """
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.producer = KafkaProducer(
            bootstrap_servers=[bootstrap_servers],
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None
        )

    def fetch_kev_catalog(self):
        """
        Fetch KEV catalog from CISA.

        Returns:
            Dict with 'catalogVersion', 'dateReleased', 'vulnerabilities'
        """
        print(f"📥 Fetching KEV catalog from {self.KEV_URL}...")

        try:
            response = requests.get(self.KEV_URL, timeout=30)
            response.raise_for_status()

            kev_data = response.json()

            print(f"✅ Fetched KEV catalog v{kev_data.get('catalogVersion')}")
            print(f"   Released: {kev_data.get('dateReleased')}")
            print(f"   Vulnerabilities: {kev_data.get('count', len(kev_data.get('vulnerabilities', [])))} CVEs")

            return kev_data

        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to fetch KEV catalog: {e}")
            return None

    def publish_kev_records(self, kev_data):
        """
        Publish KEV records to Kafka.

        Args:
            kev_data: KEV catalog data from CISA

        Returns:
            Number of records published
        """
        if not kev_data or 'vulnerabilities' not in kev_data:
            print("⚠️  No vulnerabilities in KEV data")
            return 0

        vulnerabilities = kev_data['vulnerabilities']
        published_count = 0

        for vuln in vulnerabilities:
            kev_record = {
                # Core KEV fields
                'cve_id': vuln['cveID'],
                'vendor_project': vuln.get('vendorProject'),
                'product': vuln.get('product'),
                'vulnerability_name': vuln.get('vulnerabilityName'),
                'date_added': vuln.get('dateAdded'),
                'short_description': vuln.get('shortDescription'),
                'required_action': vuln.get('requiredAction'),
                'due_date': vuln.get('dueDate'),

                # Enrichment fields
                'kev_listed': True,  # Flag for risk scoring
                'catalog_version': kev_data.get('catalogVersion'),
                'catalog_release_date': kev_data.get('dateReleased'),
                'fetched_at': datetime.now(timezone.utc).isoformat()
            }

            # Use CVE ID as key for compaction (keep latest per CVE)
            key = vuln['cveID']

            try:
                future = self.producer.send(
                    self.topic,
                    key=key,
                    value=kev_record
                )
                future.get(timeout=10)
                published_count += 1

                if published_count % 100 == 0:
                    print(f"   Published {published_count}/{len(vulnerabilities)} KEV records...")

            except Exception as e:
                print(f"❌ Failed to publish {key}: {e}")

        self.producer.flush()
        print(f"✅ Published {published_count} KEV records to {self.topic}")

        return published_count

    def run_once(self):
        """Fetch and publish KEV catalog once"""
        kev_data = self.fetch_kev_catalog()
        if kev_data:
            return self.publish_kev_records(kev_data)
        return 0

    def run_continuous(self, interval_hours=24):
        """
        Continuously fetch and publish KEV catalog.

        Args:
            interval_hours: Hours between KEV catalog updates (default: 24)
        """
        print(f"🔄 Starting KEV producer (update interval: {interval_hours} hours)")

        while True:
            count = self.run_once()

            if count > 0:
                print(f"⏰ Next update in {interval_hours} hours...")

            time.sleep(interval_hours * 3600)

    def close(self):
        """Close Kafka producer"""
        self.producer.close()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='CISA KEV Feed Producer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch once and exit
  python3 kev_producer.py --once

  # Continuous updates every 24 hours
  python3 kev_producer.py --interval 24

  # Custom Kafka broker
  python3 kev_producer.py --bootstrap-servers kafka:9092 --once
        """
    )

    parser.add_argument(
        '--bootstrap-servers',
        default='localhost:9092',
        help='Kafka bootstrap servers (default: localhost:9092)'
    )

    parser.add_argument(
        '--topic',
        default='kev-feed',
        help='Kafka topic for KEV records (default: kev-feed)'
    )

    parser.add_argument(
        '--once',
        action='store_true',
        help='Fetch once and exit (default: continuous)'
    )

    parser.add_argument(
        '--interval',
        type=int,
        default=24,
        help='Update interval in hours for continuous mode (default: 24)'
    )

    args = parser.parse_args()

    # Create producer
    producer = KEVProducer(
        bootstrap_servers=args.bootstrap_servers,
        topic=args.topic
    )

    try:
        if args.once:
            # Run once and exit
            count = producer.run_once()
            print(f"\n📊 Summary: {count} KEV records published")
        else:
            # Continuous mode
            producer.run_continuous(interval_hours=args.interval)

    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")

    finally:
        producer.close()
        print("👋 KEV producer stopped")


if __name__ == '__main__':
    main()
