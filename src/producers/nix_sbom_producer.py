#!/usr/bin/env python3
"""
Nix/Flox SBOM Producer

Generates SPDX 2.3 SBOMs for Nix packages from:
1. Flox environment packages (via `flox list --json`)
2. Nix store paths (optional)

Uses PURL format: pkg:nix/nixpkgs/{pname}@{version}

This producer focuses on the nixpkgs and floxhub universe to reduce
false positives when matching against CVEs.
"""

import json
import subprocess
import re
from datetime import datetime
from typing import List, Dict, Optional
from kafka import KafkaProducer
import time
import sys


class NixSBOMProducer:
    """Produces SBOMs from Nix/Flox package information"""

    def __init__(self, bootstrap_servers: str = 'localhost:9092'):
        self.producer = KafkaProducer(
            bootstrap_servers=[bootstrap_servers],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        self.topic = 'sboms'

    def get_flox_packages(self) -> List[Dict[str, str]]:
        """Get packages from current Flox environment"""
        try:
            # Run `flox list` and parse output
            result = subprocess.run(
                ['flox', 'list'],
                capture_output=True,
                text=True,
                check=True
            )

            packages = []
            for line in result.stdout.strip().split('\n'):
                if not line or line.startswith('warning:'):
                    continue

                # Parse format: "kafka-python: python312Packages.kafka-python (2.2.3)"
                # or: "python312: python312 (python3-3.12.11)"
                parts = line.split(':', 1)
                if len(parts) != 2:
                    continue

                install_id = parts[0].strip()
                rest = parts[1].strip()

                # Extract package name and version
                # Format: "package_name (version)" or "package_name (alias-version)"
                match = re.search(r'([\w\.\-]+)\s+\(([^\)]+)\)', rest)
                if match:
                    pkg_name = match.group(1)
                    version_str = match.group(2)

                    # Handle alias formats like "python3-3.12.11"
                    version_match = re.search(r'([\d\.]+(?:-[\w\.]+)?)$', version_str)
                    if version_match:
                        version = version_match.group(1)
                    else:
                        version = version_str

                    # Determine namespace (nixpkgs or python packages)
                    if 'python' in pkg_name.lower() and 'Packages' in rest:
                        namespace = 'nixpkgs'
                        # Use the install_id as the actual package name for python packages
                        pname = install_id
                    else:
                        namespace = 'nixpkgs'
                        pname = install_id

                    packages.append({
                        'name': pname,
                        'version': version,
                        'purl': f'pkg:nix/{namespace}/{pname}@{version}',
                        'source': 'flox'
                    })

            return packages

        except subprocess.CalledProcessError as e:
            print(f"Error getting Flox packages: {e}", file=sys.stderr)
            return []
        except Exception as e:
            print(f"Unexpected error: {e}", file=sys.stderr)
            return []

    def get_sample_nix_packages(self) -> List[Dict[str, str]]:
        """
        Sample Nix packages with known vulnerabilities for testing.
        This represents packages commonly found in Nix environments.
        """
        return [
            {
                'name': 'openssl',
                'version': '1.1.1k',
                'purl': 'pkg:nix/nixpkgs/openssl@1.1.1k',
                'source': 'sample'
            },
            {
                'name': 'curl',
                'version': '7.79.1',
                'purl': 'pkg:nix/nixpkgs/curl@7.79.1',
                'source': 'sample'
            },
            {
                'name': 'git',
                'version': '2.33.0',
                'purl': 'pkg:nix/nixpkgs/git@2.33.0',
                'source': 'sample'
            },
            {
                'name': 'nginx',
                'version': '1.20.1',
                'purl': 'pkg:nix/nixpkgs/nginx@1.20.1',
                'source': 'sample'
            },
            {
                'name': 'python3',
                'version': '3.9.7',
                'purl': 'pkg:nix/nixpkgs/python3@3.9.7',
                'source': 'sample'
            },
            {
                'name': 'nodejs',
                'version': '16.13.0',
                'purl': 'pkg:nix/nixpkgs/nodejs@16.13.0',
                'source': 'sample'
            },
        ]

    def generate_sbom(self, env_name: str, packages: List[Dict[str, str]]) -> dict:
        """
        Generate SPDX 2.3 compliant SBOM for Nix/Flox environment

        Args:
            env_name: Name of the environment (e.g., "sbom2cve-flox-env")
            packages: List of package dictionaries with name, version, purl

        Returns:
            SPDX 2.3 SBOM dictionary
        """
        timestamp = datetime.utcnow().isoformat() + "Z"

        # Create SPDX packages
        spdx_packages = []
        for pkg in packages:
            pkg_id = f"SPDXRef-Package-{pkg['name']}-{pkg['version']}"

            spdx_pkg = {
                "SPDXID": pkg_id,
                "name": pkg['name'],
                "versionInfo": pkg['version'],
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": pkg['purl']
                    }
                ]
            }

            # Add source information
            if pkg.get('source'):
                spdx_pkg['comment'] = f"Source: {pkg['source']}"

            spdx_packages.append(spdx_pkg)

        # Create SBOM document
        sbom = {
            "spdxVersion": "SPDX-2.3",
            "dataLicense": "CC0-1.0",
            "SPDXID": "SPDXRef-DOCUMENT",
            "name": f"{env_name}-sbom",
            "documentNamespace": f"https://floxhub.com/sbom/{env_name}/{timestamp}",
            "creationInfo": {
                "created": timestamp,
                "creators": [
                    "Tool: nix-sbom-producer",
                    "Organization: FloxHub"
                ]
            },
            "packages": spdx_packages
        }

        return sbom

    def send_sbom(self, sbom: dict, env_name: str):
        """Send SBOM to Kafka topic"""
        try:
            future = self.producer.send(self.topic, value=sbom)
            metadata = future.get(timeout=10)
            print(f"Sent SBOM for {env_name} to {self.topic}:{metadata.partition} @ offset {metadata.offset}")
        except Exception as e:
            print(f"Error sending SBOM: {e}", file=sys.stderr)

    def run_continuous(self, interval: int = 10, use_real_flox: bool = True):
        """
        Continuously produce SBOMs

        Args:
            interval: Seconds between SBOM generations
            use_real_flox: If True, use real Flox packages; otherwise use samples
        """
        print(f"Starting Nix SBOM production (interval: {interval}s, real_flox: {use_real_flox})")

        count = 0
        while True:
            count += 1

            # Get packages from either Flox or samples
            if use_real_flox:
                packages = self.get_flox_packages()
                env_name = "flox-current-env"
            else:
                packages = self.get_sample_nix_packages()
                env_name = "nix-sample-env"

            if packages:
                sbom = self.generate_sbom(env_name, packages)
                self.send_sbom(sbom, env_name)
                print(f"[{count}] Produced Nix SBOM for {env_name} with {len(packages)} packages")
            else:
                print(f"[{count}] No packages found, skipping SBOM generation")

            time.sleep(interval)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Nix/Flox SBOM Producer')
    parser.add_argument('--interval', type=int, default=10,
                       help='Interval between SBOM generations (seconds)')
    parser.add_argument('--bootstrap-servers', default='localhost:9092',
                       help='Kafka bootstrap servers')
    parser.add_argument('--use-samples', action='store_true',
                       help='Use sample Nix packages instead of real Flox env')

    args = parser.parse_args()

    producer = NixSBOMProducer(bootstrap_servers=args.bootstrap_servers)
    producer.run_continuous(
        interval=args.interval,
        use_real_flox=not args.use_samples
    )


if __name__ == '__main__':
    main()
