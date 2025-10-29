#!/usr/bin/env python3
"""
SBOM Producer - Generates SPDX JSON SBOMs and sends them to Kafka
"""
import json
import time
import uuid
from datetime import datetime, timezone
from kafka import KafkaProducer
from typing import List, Dict
import random


class SPDXSBOMGenerator:
    """Generates SPDX 2.3 compliant SBOM documents"""

    SAMPLE_PACKAGES = [
        {"name": "log4j-core", "version": "2.14.1", "purl": "pkg:maven/org.apache.logging.log4j/log4j-core@2.14.1"},
        {"name": "log4j-core", "version": "2.17.0", "purl": "pkg:maven/org.apache.logging.log4j/log4j-core@2.17.0"},
        {"name": "spring-core", "version": "5.3.18", "purl": "pkg:maven/org.springframework/spring-core@5.3.18"},
        {"name": "jackson-databind", "version": "2.12.3", "purl": "pkg:maven/com.fasterxml.jackson.core/jackson-databind@2.12.3"},
        {"name": "jackson-databind", "version": "2.13.4", "purl": "pkg:maven/com.fasterxml.jackson.core/jackson-databind@2.13.4"},
        {"name": "openssl", "version": "1.1.1f", "purl": "pkg:generic/openssl@1.1.1f"},
        {"name": "openssl", "version": "3.0.7", "purl": "pkg:generic/openssl@3.0.7"},
        {"name": "commons-text", "version": "1.9", "purl": "pkg:maven/org.apache.commons/commons-text@1.9"},
        {"name": "golang.org/x/text", "version": "v0.3.7", "purl": "pkg:golang/golang.org/x/text@v0.3.7"},
        {"name": "requests", "version": "2.27.1", "purl": "pkg:pypi/requests@2.27.1"},
    ]

    def generate_sbom(self, application_name: str, num_packages: int = 5) -> Dict:
        """Generate a realistic SPDX 2.3 SBOM"""
        sbom_id = f"SPDXRef-DOCUMENT-{uuid.uuid4()}"
        packages = random.sample(self.SAMPLE_PACKAGES, min(num_packages, len(self.SAMPLE_PACKAGES)))

        spdx_packages = []
        for idx, pkg in enumerate(packages):
            pkg_id = f"SPDXRef-Package-{idx}"
            spdx_packages.append({
                "SPDXID": pkg_id,
                "name": pkg["name"],
                "versionInfo": pkg["version"],
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": pkg["purl"]
                    }
                ]
            })

        sbom = {
            "spdxVersion": "SPDX-2.3",
            "dataLicense": "CC0-1.0",
            "SPDXID": sbom_id,
            "name": f"SBOM for {application_name}",
            "documentNamespace": f"https://example.com/sboms/{uuid.uuid4()}",
            "creationInfo": {
                "created": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                "creators": ["Tool: sbom-generator-1.0"],
                "licenseListVersion": "3.19"
            },
            "packages": spdx_packages,
            "relationships": [
                {
                    "spdxElementId": sbom_id,
                    "relationshipType": "DESCRIBES",
                    "relatedSpdxElement": f"SPDXRef-Package-0"
                }
            ]
        }

        return sbom


class SBOMProducer:
    """Kafka producer for SBOM documents"""

    def __init__(self, bootstrap_servers: str = "localhost:9092", topic: str = "sboms"):
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None
        )
        self.topic = topic
        self.generator = SPDXSBOMGenerator()

    def produce_sbom(self, application_name: str, num_packages: int = 5):
        """Generate and send a single SBOM to Kafka"""
        sbom = self.generator.generate_sbom(application_name, num_packages)

        # Use application name as the key for partitioning
        future = self.producer.send(
            self.topic,
            key=application_name,
            value=sbom
        )

        # Wait for send to complete
        record_metadata = future.get(timeout=10)

        print(f"Sent SBOM for {application_name} to {record_metadata.topic}:{record_metadata.partition} @ offset {record_metadata.offset}")
        return sbom

    def produce_continuous(self, interval: int = 5):
        """Continuously produce SBOMs"""
        applications = [
            "web-app-frontend",
            "api-gateway",
            "user-service",
            "payment-service",
            "analytics-engine",
            "mobile-backend"
        ]

        try:
            print(f"Starting continuous SBOM production (interval: {interval}s)")
            count = 0
            while True:
                app = random.choice(applications)
                num_packages = random.randint(3, 8)

                sbom = self.produce_sbom(app, num_packages)
                count += 1

                print(f"[{count}] Produced SBOM for {app} with {len(sbom['packages'])} packages")
                time.sleep(interval)

        except KeyboardInterrupt:
            print("\nStopping SBOM producer...")
        finally:
            self.producer.flush()
            self.producer.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SPDX SBOM Producer")
    parser.add_argument("--bootstrap-servers", default="localhost:9092", help="Kafka bootstrap servers")
    parser.add_argument("--topic", default="sboms", help="Kafka topic for SBOMs")
    parser.add_argument("--interval", type=int, default=5, help="Interval between SBOMs (seconds)")

    args = parser.parse_args()

    producer = SBOMProducer(
        bootstrap_servers=args.bootstrap_servers,
        topic=args.topic
    )

    producer.produce_continuous(interval=args.interval)
