#!/usr/bin/env python3
"""
Flink Job: SBOM-CVE Matcher with Intelligent Matching

This job consumes SBOMs and CVEs from Kafka, performs intelligent matching
based on Package URLs (PURLs) and version semantics, and produces alerts.
"""
import json
import re
from typing import Optional, Tuple
from packaging import version
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import KafkaSource, KafkaOffsetsInitializer, KafkaSink, KafkaRecordSerializationSchema
from pyflink.common.serialization import SimpleStringSchema
from pyflink.common.typeinfo import Types
from pyflink.datastream.functions import CoProcessFunction
from pyflink.datastream.state import ValueStateDescriptor, MapStateDescriptor


class PURLMatcher:
    """
    Intelligent Package URL (PURL) matcher with version range support.

    This matcher uses structured package identifiers rather than simple string matching,
    providing high-confidence vulnerability detection.
    """

    @staticmethod
    def parse_purl(purl: str) -> Optional[dict]:
        """
        Parse a Package URL into components.

        Format: pkg:type/namespace/name@version?qualifiers#subpath
        Example: pkg:maven/org.apache.logging.log4j/log4j-core@2.14.1
        """
        if not purl or not purl.startswith("pkg:"):
            return None

        try:
            # Remove pkg: prefix
            purl = purl[4:]

            # Split on @ to separate version
            if "@" in purl:
                package_part, version_part = purl.split("@", 1)
            else:
                package_part = purl
                version_part = None

            # Remove qualifiers and subpath if present
            if "?" in package_part:
                package_part = package_part.split("?")[0]
            if "#" in package_part:
                package_part = package_part.split("#")[0]

            # Split package part into type and name
            parts = package_part.split("/")
            pkg_type = parts[0]

            if len(parts) == 2:
                # pkg:pypi/requests
                namespace = None
                name = parts[1]
            elif len(parts) >= 3:
                # pkg:maven/org.apache.logging.log4j/log4j-core
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
        """
        Normalize PURL for comparison (without version).
        Returns: 'type:namespace:name' or 'type::name' if no namespace
        """
        parsed = PURLMatcher.parse_purl(purl)
        if not parsed:
            return None

        namespace = parsed.get("namespace", "")
        return f"{parsed['type']}:{namespace}:{parsed['name']}"

    @staticmethod
    def matches_version_range(pkg_version: str, version_constraint: str) -> Tuple[bool, float]:
        """
        Check if a package version matches a version constraint.

        Returns: (matches: bool, confidence: float)

        Supports constraints like:
        - ">=2.0-beta9 <2.15.0"
        - ">=1.1.1 <1.1.1k"
        - "<2.13.4.1"
        """
        try:
            # Parse the package version
            try:
                pkg_ver = version.parse(pkg_version)
            except version.InvalidVersion:
                # Try to clean up version string
                clean_version = re.sub(r'[^0-9.]', '', pkg_version)
                if clean_version:
                    pkg_ver = version.parse(clean_version)
                else:
                    return False, 0.0

            # Parse constraints
            constraints = version_constraint.strip()

            # Handle multiple constraints (e.g., ">=2.0 <2.15.0")
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

            # High confidence for version range matches (0.95)
            return matches, 0.95 if matches else 0.0

        except Exception as e:
            print(f"Error matching version {pkg_version} against {version_constraint}: {e}")
            return False, 0.0


class SBOMCVEMatcher(CoProcessFunction):
    """
    Flink CoProcessFunction that matches SBOMs against CVEs.

    Maintains state for both streams and performs intelligent matching
    when new data arrives on either stream.
    """

    def __init__(self):
        self.sbom_state = None  # MapState[app_name, sbom_data]
        self.cve_state = None   # MapState[cve_id, cve_data]

    def open(self, runtime_context):
        # Initialize state for storing SBOMs and CVEs
        sbom_state_descriptor = MapStateDescriptor(
            "sbom_state",
            Types.STRING(),
            Types.STRING()
        )
        self.sbom_state = runtime_context.get_map_state(sbom_state_descriptor)

        cve_state_descriptor = MapStateDescriptor(
            "cve_state",
            Types.STRING(),
            Types.STRING()
        )
        self.cve_state = runtime_context.get_map_state(cve_state_descriptor)

    def process_element1(self, sbom_json, ctx):
        """Process SBOM from first stream"""
        try:
            sbom = json.loads(sbom_json)
            app_name = sbom.get("name", "unknown")

            # Store SBOM in state
            self.sbom_state.put(app_name, sbom_json)

            # Check against all known CVEs
            for cve_entry in self.cve_state.items():
                cve_id, cve_json = cve_entry
                cve = json.loads(cve_json)

                # Perform matching
                alerts = self._match_sbom_against_cve(sbom, cve)
                for alert in alerts:
                    yield json.dumps(alert)

        except Exception as e:
            print(f"Error processing SBOM: {e}")

    def process_element2(self, cve_json, ctx):
        """Process CVE from second stream"""
        try:
            cve = json.loads(cve_json)
            cve_id = cve.get("cve_id", "unknown")

            # Store CVE in state
            self.cve_state.put(cve_id, cve_json)

            # Check against all known SBOMs
            for sbom_entry in self.sbom_state.items():
                app_name, sbom_json = sbom_entry
                sbom = json.loads(sbom_json)

                # Perform matching
                alerts = self._match_sbom_against_cve(sbom, cve)
                for alert in alerts:
                    yield json.dumps(alert)

        except Exception as e:
            print(f"Error processing CVE: {e}")

    def _match_sbom_against_cve(self, sbom: dict, cve: dict) -> list:
        """
        Intelligent matching between SBOM packages and CVE affected products.

        Uses PURL-based matching with version range checking for high confidence.
        """
        alerts = []

        sbom_packages = sbom.get("packages", [])
        cve_affected = cve.get("affected_products", [])

        for sbom_pkg in sbom_packages:
            # Extract PURL from SBOM package
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

            # Check against each affected product in the CVE
            for affected in cve_affected:
                cve_purl = affected.get("purl")
                if not cve_purl:
                    continue

                cve_purl_normalized = PURLMatcher.normalize_purl_for_comparison(cve_purl)
                if not cve_purl_normalized:
                    continue

                # Check if PURLs match (package identity)
                if sbom_purl_normalized != cve_purl_normalized:
                    continue

                # Package identity matches - now check version
                version_constraint = affected.get("version_affected", "")
                if sbom_version and version_constraint:
                    is_affected, confidence = PURLMatcher.matches_version_range(
                        sbom_version,
                        version_constraint
                    )

                    if is_affected:
                        alert = {
                            "alert_id": f"{sbom.get('SPDXID', 'unknown')}-{cve.get('cve_id', 'unknown')}",
                            "timestamp": ctx.timestamp() if hasattr(ctx, 'timestamp') else None,
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


def create_flink_job():
    """Create and configure the Flink streaming job"""

    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(1)

    # Kafka configuration
    kafka_servers = "localhost:9092"

    # Source for SBOMs
    sbom_source = KafkaSource.builder() \
        .set_bootstrap_servers(kafka_servers) \
        .set_topics("sboms") \
        .set_group_id("sbom-cve-matcher") \
        .set_starting_offsets(KafkaOffsetsInitializer.latest()) \
        .set_value_only_deserializer(SimpleStringSchema()) \
        .build()

    # Source for CVEs
    cve_source = KafkaSource.builder() \
        .set_bootstrap_servers(kafka_servers) \
        .set_topics("cves") \
        .set_group_id("sbom-cve-matcher") \
        .set_starting_offsets(KafkaOffsetsInitializer.latest()) \
        .set_value_only_deserializer(SimpleStringSchema()) \
        .build()

    # Sink for alerts
    alert_sink = KafkaSink.builder() \
        .set_bootstrap_servers(kafka_servers) \
        .set_record_serializer(
            KafkaRecordSerializationSchema.builder()
                .set_topic("alerts")
                .set_value_serialization_schema(SimpleStringSchema())
                .build()
        ) \
        .build()

    # Create data streams
    sbom_stream = env.from_source(sbom_source, None, "SBOM Source")
    cve_stream = env.from_source(cve_source, None, "CVE Source")

    # Connect streams and apply matching logic
    alerts = sbom_stream.connect(cve_stream).process(SBOMCVEMatcher())

    # Send alerts to Kafka
    alerts.sink_to(alert_sink)

    # Execute the job
    env.execute("SBOM-CVE Matcher")


if __name__ == "__main__":
    create_flink_job()
