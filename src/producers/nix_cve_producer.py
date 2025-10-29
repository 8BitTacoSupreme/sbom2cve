#!/usr/bin/env python3
"""
Nix CVE Producer

Generates CVE records for Nix packages with PURL references.
Focuses on real CVEs that affect packages in the nixpkgs ecosystem.

This helps narrow false positives to the nixpkgs and floxhub universe
by using proper Nix PURLs.
"""

import json
import random
from datetime import datetime
from kafka import KafkaProducer
import time


class NixCVEProducer:
    """Produces CVE records with Nix package references"""

    # Real CVEs affecting common Nix packages
    KNOWN_NIX_CVES = [
        {
            "cve_id": "CVE-2022-3786",
            "severity": "HIGH",
            "cvss_score": 7.5,
            "description": "OpenSSL X.509 Email Address Buffer Overflow",
            "affected_products": [
                {
                    "purl": "pkg:nix/nixpkgs/openssl",
                    "version_affected": ">=3.0.0 <3.0.7"
                }
            ],
            "references": [
                "https://nvd.nist.gov/vuln/detail/CVE-2022-3786",
                "https://www.openssl.org/news/secadv/20221101.txt"
            ]
        },
        {
            "cve_id": "CVE-2022-3602",
            "severity": "HIGH",
            "cvss_score": 7.5,
            "description": "OpenSSL X.509 Email Address Variable Length Buffer Overflow",
            "affected_products": [
                {
                    "purl": "pkg:nix/nixpkgs/openssl",
                    "version_affected": ">=3.0.0 <3.0.7"
                }
            ],
            "references": [
                "https://nvd.nist.gov/vuln/detail/CVE-2022-3602"
            ]
        },
        {
            "cve_id": "CVE-2021-22946",
            "severity": "HIGH",
            "cvss_score": 7.5,
            "description": "curl TELNET stack contents disclosure",
            "affected_products": [
                {
                    "purl": "pkg:nix/nixpkgs/curl",
                    "version_affected": ">=7.0.0 <7.80.0"
                }
            ],
            "references": [
                "https://nvd.nist.gov/vuln/detail/CVE-2021-22946",
                "https://curl.se/docs/CVE-2021-22946.html"
            ]
        },
        {
            "cve_id": "CVE-2021-22947",
            "severity": "MEDIUM",
            "cvss_score": 5.9,
            "description": "curl STARTTLS protocol injection via MITM",
            "affected_products": [
                {
                    "purl": "pkg:nix/nixpkgs/curl",
                    "version_affected": ">=7.0.0 <7.80.0"
                }
            ],
            "references": [
                "https://nvd.nist.gov/vuln/detail/CVE-2021-22947"
            ]
        },
        {
            "cve_id": "CVE-2021-40330",
            "severity": "CRITICAL",
            "cvss_score": 9.8,
            "description": "Git remote code execution vulnerability",
            "affected_products": [
                {
                    "purl": "pkg:nix/nixpkgs/git",
                    "version_affected": ">=2.0.0 <2.33.1"
                }
            ],
            "references": [
                "https://nvd.nist.gov/vuln/detail/CVE-2021-40330",
                "https://github.blog/2021-09-17-git-vulnerability-announced/"
            ]
        },
        {
            "cve_id": "CVE-2021-23017",
            "severity": "HIGH",
            "cvss_score": 7.7,
            "description": "nginx resolver off-by-one in ngx_resolver_copy()",
            "affected_products": [
                {
                    "purl": "pkg:nix/nixpkgs/nginx",
                    "version_affected": ">=0.6.18 <1.21.0"
                }
            ],
            "references": [
                "https://nvd.nist.gov/vuln/detail/CVE-2021-23017",
                "http://mailman.nginx.org/pipermail/nginx-announce/2021/000300.html"
            ]
        },
        {
            "cve_id": "CVE-2021-3711",
            "severity": "CRITICAL",
            "cvss_score": 9.8,
            "description": "OpenSSL SM2 Decryption Buffer Overflow",
            "affected_products": [
                {
                    "purl": "pkg:nix/nixpkgs/openssl",
                    "version_affected": ">=1.1.1 <1.1.1l"
                }
            ],
            "references": [
                "https://nvd.nist.gov/vuln/detail/CVE-2021-3711"
            ]
        },
        {
            "cve_id": "CVE-2021-3712",
            "severity": "HIGH",
            "cvss_score": 7.4,
            "description": "OpenSSL Read buffer overruns processing ASN.1 strings",
            "affected_products": [
                {
                    "purl": "pkg:nix/nixpkgs/openssl",
                    "version_affected": ">=1.1.1 <1.1.1l"
                }
            ],
            "references": [
                "https://nvd.nist.gov/vuln/detail/CVE-2021-3712"
            ]
        },
        {
            "cve_id": "CVE-2020-28928",
            "severity": "MEDIUM",
            "cvss_score": 5.3,
            "description": "Musl libc wcsnrtombs() out-of-bounds read",
            "affected_products": [
                {
                    "purl": "pkg:nix/nixpkgs/musl",
                    "version_affected": "<1.2.2"
                }
            ],
            "references": [
                "https://nvd.nist.gov/vuln/detail/CVE-2020-28928"
            ]
        },
        {
            "cve_id": "CVE-2021-33560",
            "severity": "HIGH",
            "cvss_score": 7.5,
            "description": "libgcrypt ElGamal encryption allows plaintext recovery",
            "affected_products": [
                {
                    "purl": "pkg:nix/nixpkgs/libgcrypt",
                    "version_affected": "<1.9.4"
                }
            ],
            "references": [
                "https://nvd.nist.gov/vuln/detail/CVE-2021-33560"
            ]
        },
        {
            "cve_id": "CVE-2021-36084",
            "severity": "MEDIUM",
            "cvss_score": 6.1,
            "description": "libsepol CIL compiler use-after-free",
            "affected_products": [
                {
                    "purl": "pkg:nix/nixpkgs/libsepol",
                    "version_affected": "<3.3"
                }
            ],
            "references": [
                "https://nvd.nist.gov/vuln/detail/CVE-2021-36084"
            ]
        },
        {
            "cve_id": "CVE-2021-44717",
            "severity": "HIGH",
            "cvss_score": 7.5,
            "description": "Go net/http: limit growth of header canonicalization cache",
            "affected_products": [
                {
                    "purl": "pkg:nix/nixpkgs/go",
                    "version_affected": "<1.16.12"
                },
                {
                    "purl": "pkg:nix/nixpkgs/go",
                    "version_affected": ">=1.17.0 <1.17.5"
                }
            ],
            "references": [
                "https://nvd.nist.gov/vuln/detail/CVE-2021-44717"
            ]
        },
        {
            "cve_id": "CVE-2021-3999",
            "severity": "HIGH",
            "cvss_score": 7.8,
            "description": "glibc realpath() buffer overflow via chdir()",
            "affected_products": [
                {
                    "purl": "pkg:nix/nixpkgs/glibc",
                    "version_affected": "<2.34"
                }
            ],
            "references": [
                "https://nvd.nist.gov/vuln/detail/CVE-2021-3999"
            ]
        },
        {
            "cve_id": "CVE-2022-1271",
            "severity": "HIGH",
            "cvss_score": 7.8,
            "description": "gzip arbitrary file write vulnerability",
            "affected_products": [
                {
                    "purl": "pkg:nix/nixpkgs/gzip",
                    "version_affected": "<1.12"
                }
            ],
            "references": [
                "https://nvd.nist.gov/vuln/detail/CVE-2022-1271"
            ]
        },
        {
            "cve_id": "CVE-2021-3520",
            "severity": "MEDIUM",
            "cvss_score": 6.5,
            "description": "lz4 memory corruption on crafted input",
            "affected_products": [
                {
                    "purl": "pkg:nix/nixpkgs/lz4",
                    "version_affected": "<1.9.4"
                }
            ],
            "references": [
                "https://nvd.nist.gov/vuln/detail/CVE-2021-3520"
            ]
        },
        # Python-related Nix CVEs
        {
            "cve_id": "CVE-2021-29921",
            "severity": "CRITICAL",
            "cvss_score": 9.8,
            "description": "Python ipaddress leading zeros misinterpretation",
            "affected_products": [
                {
                    "purl": "pkg:nix/nixpkgs/python3",
                    "version_affected": "<3.9.5"
                }
            ],
            "references": [
                "https://nvd.nist.gov/vuln/detail/CVE-2021-29921"
            ]
        },
        # Node.js CVEs in Nix
        {
            "cve_id": "CVE-2021-44531",
            "severity": "MEDIUM",
            "cvss_score": 5.9,
            "description": "Node.js accepting non-standard HTTP headers",
            "affected_products": [
                {
                    "purl": "pkg:nix/nixpkgs/nodejs",
                    "version_affected": ">=12.0.0 <12.22.9"
                },
                {
                    "purl": "pkg:nix/nixpkgs/nodejs",
                    "version_affected": ">=14.0.0 <14.18.3"
                },
                {
                    "purl": "pkg:nix/nixpkgs/nodejs",
                    "version_affected": ">=16.0.0 <16.13.2"
                }
            ],
            "references": [
                "https://nvd.nist.gov/vuln/detail/CVE-2021-44531"
            ]
        }
    ]

    def __init__(self, bootstrap_servers: str = 'localhost:9092'):
        self.producer = KafkaProducer(
            bootstrap_servers=[bootstrap_servers],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        self.topic = 'cves'

    def send_cve(self, cve: dict):
        """Send CVE to Kafka topic"""
        try:
            future = self.producer.send(self.topic, value=cve)
            metadata = future.get(timeout=10)
            print(f"Sent CVE {cve['cve_id']} to {self.topic}:{metadata.partition} @ offset {metadata.offset}")
        except Exception as e:
            print(f"Error sending CVE: {e}")

    def run_continuous(self, interval: int = 5):
        """
        Continuously produce CVEs from the known list

        Args:
            interval: Seconds between CVE publications
        """
        print(f"Starting Nix CVE production (interval: {interval}s)")

        count = 0
        while True:
            count += 1

            # Pick a random CVE from our known list
            cve = random.choice(self.KNOWN_NIX_CVES).copy()

            # Add timestamp
            cve['published'] = datetime.now(datetime.UTC).isoformat().replace('+00:00', 'Z')

            self.send_cve(cve)
            print(f"[{count}] Produced Nix CVE: {cve['cve_id']} ({cve['severity']})")

            time.sleep(interval)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Nix CVE Producer')
    parser.add_argument('--interval', type=int, default=5,
                       help='Interval between CVE generations (seconds)')
    parser.add_argument('--bootstrap-servers', default='localhost:9092',
                       help='Kafka bootstrap servers')

    args = parser.parse_args()

    producer = NixCVEProducer(bootstrap_servers=args.bootstrap_servers)
    producer.run_continuous(interval=args.interval)


if __name__ == '__main__':
    main()
