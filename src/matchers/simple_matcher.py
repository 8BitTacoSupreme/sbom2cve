#!/usr/bin/env python3
"""
Simple SBOM-CVE Matcher - Python-based matching without Flink Python API

This script consumes SBOMs and CVEs from Kafka, performs intelligent matching,
and produces alerts using pure Python with Kafka consumer/producer pattern.
"""
import json
import re
from typing import Optional, Tuple, Dict
from kafka import KafkaConsumer, KafkaProducer
from packaging import version
from collections import defaultdict
import threading
import time


class PURLMatcher:
    """
    Intelligent Package URL (PURL) matcher with version range support.
    """

    @staticmethod
    def parse_purl(purl: str) -> Optional[dict]:
        """Parse a Package URL into components."""
        if not purl or not purl.startswith("pkg:"):
            return None

        try:
            purl = purl[4:]  # Remove pkg: prefix

            if "@" in purl:
                package_part, version_part = purl.split("@", 1)
            else:
                package_part = purl
                version_part = None

            if "?" in package_part:
                package_part = package_part.split("?")[0]
            if "#" in package_part:
                package_part = package_part.split("#")[0]

            parts = package_part.split("/")
            pkg_type = parts[0]

            if len(parts) == 2:
                namespace = None
                name = parts[1]
            elif len(parts) >= 3:
                namespace = "/".join(parts[1:-1])
                name = parts[-1]
            else:
                return None

            return {
                "type": pkg_type,
                "namespace": namespace,
                "name": name,
                "version": version_part
            }
        except Exception as e:
            print(f"Error parsing PURL {purl}: {e}")
            return None

    @staticmethod
    def normalize_purl_for_comparison(purl: str) -> Optional[str]:
        """Normalize PURL for comparison (without version)."""
        parsed = PURLMatcher.parse_purl(purl)
        if not parsed:
            return None

        namespace = parsed.get("namespace", "")
        return f"{parsed['type']}:{namespace}:{parsed['name']}"

    @staticmethod
    def matches_version_range(pkg_version: str, version_constraint: str) -> Tuple[bool, float]:
        """Check if a package version matches a version constraint."""
        try:
            try:
                pkg_ver = version.parse(pkg_version)
            except version.InvalidVersion:
                clean_version = re.sub(r'[^0-9.]', '', pkg_version)
                if clean_version:
                    pkg_ver = version.parse(clean_version)
                else:
                    return False, 0.0

            constraints = version_constraint.strip()
            matches = True

            for constraint in constraints.split():
                if constraint.startswith(">="):
                    min_ver = version.parse(constraint[2:])
                    if pkg_ver < min_ver:
                        matches = False
                        break
                elif constraint.startswith(">"):
                    min_ver = version.parse(constraint[1:])
                    if pkg_ver <= min_ver:
                        matches = False
                        break
                elif constraint.startswith("<="):
                    max_ver = version.parse(constraint[2:])
                    if pkg_ver > max_ver:
                        matches = False
                        break
                elif constraint.startswith("<"):
                    max_ver = version.parse(constraint[1:])
                    if pkg_ver >= max_ver:
                        matches = False
                        break
                elif constraint.startswith("=="):
                    exact_ver = version.parse(constraint[2:])
                    if pkg_ver != exact_ver:
                        matches = False
                        break

            return matches, 0.95 if matches else 0.0

        except Exception as e:
            print(f"Error matching version {pkg_version} against {version_constraint}: {e}")
            return False, 0.0


class SBOMCVEMatcher:
    """
    SBOM-CVE Matcher using Kafka consumer/producer pattern.
    """

    def __init__(self, bootstrap_servers="localhost:9092"):
        self.bootstrap_servers = bootstrap_servers
        self.sbom_cache = {}  # app_name -> sbom
        self.cve_cache = {}   # cve_id -> cve
        self.lock = threading.Lock()

        # Producer for alerts
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

        # Consumers
        self.sbom_consumer = KafkaConsumer(
            'sboms',
            bootstrap_servers=bootstrap_servers,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            group_id='matcher-sbom'
        )

        self.cve_consumer = KafkaConsumer(
            'cves',
            bootstrap_servers=bootstrap_servers,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            group_id='matcher-cve'
        )

    def match_sbom_against_cve(self, sbom: dict, cve: dict) -> list:
        """Intelligent matching between SBOM packages and CVE affected products."""
        alerts = []
        sbom_packages = sbom.get("packages", [])
        cve_affected = cve.get("affected_products", [])

        for sbom_pkg in sbom_packages:
            sbom_purl = None
            for ref in sbom_pkg.get("externalRefs", []):
                if ref.get("referenceType") == "purl":
                    sbom_purl = ref.get("referenceLocator")
                    break

            if not sbom_purl:
                continue

            sbom_purl_normalized = PURLMatcher.normalize_purl_for_comparison(sbom_purl)
            if not sbom_purl_normalized:
                continue

            sbom_purl_parsed = PURLMatcher.parse_purl(sbom_purl)
            sbom_version = sbom_purl_parsed.get("version") if sbom_purl_parsed else None

            for affected in cve_affected:
                cve_purl = affected.get("purl")
                if not cve_purl:
                    continue

                cve_purl_normalized = PURLMatcher.normalize_purl_for_comparison(cve_purl)
                if not cve_purl_normalized:
                    continue

                if sbom_purl_normalized != cve_purl_normalized:
                    continue

                version_constraint = affected.get("version_affected", "")
                if sbom_version and version_constraint:
                    is_affected, confidence = PURLMatcher.matches_version_range(
                        sbom_version,
                        version_constraint
                    )

                    if is_affected:
                        alert = {
                            "alert_id": f"{sbom.get('SPDXID', 'unknown')}-{cve.get('cve_id', 'unknown')}",
                            "timestamp": int(time.time() * 1000),
                            "sbom_name": sbom.get("name", "unknown"),
                            "sbom_id": sbom.get("SPDXID", "unknown"),
                            "cve_id": cve.get("cve_id", "unknown"),
                            "severity": cve.get("severity", "UNKNOWN"),
                            "cvss_score": cve.get("cvss_score", 0.0),
                            "affected_package": {
                                "name": sbom_pkg.get("name"),
                                "version": sbom_version,
                                "purl": sbom_purl
                            },
                            "confidence_score": confidence,
                            "match_method": "purl_version_range",
                            "description": cve.get("description", ""),
                            "references": cve.get("references", [])
                        }
                        alerts.append(alert)

        return alerts

    def process_sbom(self, sbom):
        """Process a new SBOM."""
        with self.lock:
            app_name = sbom.get("name", "unknown")
            self.sbom_cache[app_name] = sbom

            # Match against all known CVEs
            for cve_id, cve in self.cve_cache.items():
                alerts = self.match_sbom_against_cve(sbom, cve)
                for alert in alerts:
                    self.send_alert(alert)

    def process_cve(self, cve):
        """Process a new CVE."""
        with self.lock:
            cve_id = cve.get("cve_id", "unknown")
            self.cve_cache[cve_id] = cve

            # Match against all known SBOMs
            for app_name, sbom in self.sbom_cache.items():
                alerts = self.match_sbom_against_cve(sbom, cve)
                for alert in alerts:
                    self.send_alert(alert)

    def send_alert(self, alert):
        """Send alert to Kafka."""
        try:
            self.producer.send('alerts', value=alert)
            print(f"✅ Alert sent: {alert['cve_id']} affects {alert['affected_package']['name']}")
        except Exception as e:
            print(f"❌ Error sending alert: {e}")

    def consume_sboms(self):
        """Consume SBOM messages."""
        print("📥 Consuming SBOMs...")
        for message in self.sbom_consumer:
            sbom = message.value
            print(f"📦 Received SBOM: {sbom.get('name', 'unknown')}")
            self.process_sbom(sbom)

    def consume_cves(self):
        """Consume CVE messages."""
        print("📥 Consuming CVEs...")
        for message in self.cve_consumer:
            cve = message.value
            print(f"🔒 Received CVE: {cve.get('cve_id', 'unknown')}")
            self.process_cve(cve)

    def run(self):
        """Run the matcher with both consumers."""
        print("🚀 Starting SBOM-CVE Matcher...")

        sbom_thread = threading.Thread(target=self.consume_sboms, daemon=True)
        cve_thread = threading.Thread(target=self.consume_cves, daemon=True)

        sbom_thread.start()
        cve_thread.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping matcher...")
            self.producer.close()
            self.sbom_consumer.close()
            self.cve_consumer.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SBOM-CVE Matcher")
    parser.add_argument("--bootstrap-servers", default="localhost:9092",
                        help="Kafka bootstrap servers")

    args = parser.parse_args()

    matcher = SBOMCVEMatcher(bootstrap_servers=args.bootstrap_servers)
    matcher.run()
