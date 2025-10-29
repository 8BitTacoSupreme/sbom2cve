#!/usr/bin/env python3
"""
CVE Producer - Generates CVE records and sends them to Kafka
"""
import json
import time
import random
from datetime import datetime, timedelta, timezone
from kafka import KafkaProducer
from typing import Dict, List


class CVEGenerator:
    """Generates realistic CVE records matching common vulnerabilities"""

    # CVEs that match our SBOM packages
    KNOWN_CVES = [
        {
            "cve_id": "CVE-2021-44228",
            "description": "Apache Log4j2 JNDI features do not protect against attacker controlled LDAP and other JNDI related endpoints",
            "severity": "CRITICAL",
            "cvss_score": 10.0,
            "affected_products": [
                {
                    "vendor": "apache",
                    "product": "log4j-core",
                    "version_affected": ">=2.0-beta9 <2.15.0",
                    "cpe": "cpe:2.3:a:apache:log4j:*:*:*:*:*:*:*:*",
                    "purl": "pkg:maven/org.apache.logging.log4j/log4j-core"
                }
            ],
            "references": ["https://nvd.nist.gov/vuln/detail/CVE-2021-44228"],
            "published_date": "2021-12-10T10:15:00Z"
        },
        {
            "cve_id": "CVE-2021-45046",
            "description": "Apache Log4j2 Thread Context Message Pattern and Context Lookup Pattern vulnerable to denial of service attack",
            "severity": "HIGH",
            "cvss_score": 9.0,
            "affected_products": [
                {
                    "vendor": "apache",
                    "product": "log4j-core",
                    "version_affected": ">=2.0-beta9 <2.16.0",
                    "cpe": "cpe:2.3:a:apache:log4j:*:*:*:*:*:*:*:*",
                    "purl": "pkg:maven/org.apache.logging.log4j/log4j-core"
                }
            ],
            "references": ["https://nvd.nist.gov/vuln/detail/CVE-2021-45046"],
            "published_date": "2021-12-14T12:30:00Z"
        },
        {
            "cve_id": "CVE-2020-36518",
            "description": "FasterXML jackson-databind allows a Java StackOverflow exception and denial of service via crafted JSON",
            "severity": "HIGH",
            "cvss_score": 7.5,
            "affected_products": [
                {
                    "vendor": "fasterxml",
                    "product": "jackson-databind",
                    "version_affected": ">=2.0.0 <2.12.6",
                    "cpe": "cpe:2.3:a:fasterxml:jackson-databind:*:*:*:*:*:*:*:*",
                    "purl": "pkg:maven/com.fasterxml.jackson.core/jackson-databind"
                }
            ],
            "references": ["https://nvd.nist.gov/vuln/detail/CVE-2020-36518"],
            "published_date": "2022-03-11T08:15:00Z"
        },
        {
            "cve_id": "CVE-2022-42003",
            "description": "FasterXML jackson-databind deep wrapper array nesting can lead to resource exhaustion",
            "severity": "HIGH",
            "cvss_score": 7.5,
            "affected_products": [
                {
                    "vendor": "fasterxml",
                    "product": "jackson-databind",
                    "version_affected": ">=2.0.0 <2.13.4.1",
                    "cpe": "cpe:2.3:a:fasterxml:jackson-databind:*:*:*:*:*:*:*:*",
                    "purl": "pkg:maven/com.fasterxml.jackson.core/jackson-databind"
                }
            ],
            "references": ["https://nvd.nist.gov/vuln/detail/CVE-2022-42003"],
            "published_date": "2022-10-02T05:15:00Z"
        },
        {
            "cve_id": "CVE-2021-3449",
            "description": "OpenSSL TLSv1.2 renegotiation ClientHello message causes denial of service",
            "severity": "HIGH",
            "cvss_score": 7.5,
            "affected_products": [
                {
                    "vendor": "openssl",
                    "product": "openssl",
                    "version_affected": ">=1.1.1 <1.1.1k",
                    "cpe": "cpe:2.3:a:openssl:openssl:*:*:*:*:*:*:*:*",
                    "purl": "pkg:generic/openssl"
                }
            ],
            "references": ["https://nvd.nist.gov/vuln/detail/CVE-2021-3449"],
            "published_date": "2021-03-25T15:15:00Z"
        },
        {
            "cve_id": "CVE-2022-42889",
            "description": "Apache Commons Text StringSubstitutor vulnerable to variable interpolation RCE",
            "severity": "CRITICAL",
            "cvss_score": 9.8,
            "affected_products": [
                {
                    "vendor": "apache",
                    "product": "commons-text",
                    "version_affected": ">=1.5 <1.10.0",
                    "cpe": "cpe:2.3:a:apache:commons_text:*:*:*:*:*:*:*:*",
                    "purl": "pkg:maven/org.apache.commons/commons-text"
                }
            ],
            "references": ["https://nvd.nist.gov/vuln/detail/CVE-2022-42889"],
            "published_date": "2022-10-18T13:15:00Z"
        },
        {
            "cve_id": "CVE-2022-32149",
            "description": "golang.org/x/text vulnerable to denial of service via crafted Accept-Language header",
            "severity": "MEDIUM",
            "cvss_score": 6.5,
            "affected_products": [
                {
                    "vendor": "golang",
                    "product": "text",
                    "version_affected": "<0.3.8",
                    "cpe": "cpe:2.3:a:golang:text:*:*:*:*:*:*:*:*",
                    "purl": "pkg:golang/golang.org/x/text"
                }
            ],
            "references": ["https://nvd.nist.gov/vuln/detail/CVE-2022-32149"],
            "published_date": "2022-10-14T15:15:00Z"
        }
    ]

    def get_random_cve(self) -> Dict:
        """Get a random CVE from the known set"""
        cve = random.choice(self.KNOWN_CVES).copy()

        # Add some dynamic fields
        cve["retrieved_at"] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        cve["source"] = "NVD"

        return cve

    def generate_cve_stream(self) -> Dict:
        """Generate a CVE suitable for streaming"""
        return self.get_random_cve()


class CVEProducer:
    """Kafka producer for CVE records"""

    def __init__(self, bootstrap_servers: str = "localhost:9092", topic: str = "cves"):
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None
        )
        self.topic = topic
        self.generator = CVEGenerator()

    def produce_cve(self):
        """Generate and send a single CVE to Kafka"""
        cve = self.generator.generate_cve_stream()

        # Use CVE ID as the key
        future = self.producer.send(
            self.topic,
            key=cve["cve_id"],
            value=cve
        )

        # Wait for send to complete
        record_metadata = future.get(timeout=10)

        print(f"Sent CVE {cve['cve_id']} to {record_metadata.topic}:{record_metadata.partition} @ offset {record_metadata.offset}")
        return cve

    def produce_continuous(self, interval: int = 3):
        """Continuously produce CVE records"""
        try:
            print(f"Starting continuous CVE production (interval: {interval}s)")
            count = 0
            while True:
                cve = self.produce_cve()
                count += 1

                print(f"[{count}] Produced CVE {cve['cve_id']} (Severity: {cve['severity']}, CVSS: {cve['cvss_score']})")
                time.sleep(interval)

        except KeyboardInterrupt:
            print("\nStopping CVE producer...")
        finally:
            self.producer.flush()
            self.producer.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CVE Producer")
    parser.add_argument("--bootstrap-servers", default="localhost:9092", help="Kafka bootstrap servers")
    parser.add_argument("--topic", default="cves", help="Kafka topic for CVEs")
    parser.add_argument("--interval", type=int, default=3, help="Interval between CVEs (seconds)")

    args = parser.parse_args()

    producer = CVEProducer(
        bootstrap_servers=args.bootstrap_servers,
        topic=args.topic
    )

    producer.produce_continuous(interval=args.interval)
