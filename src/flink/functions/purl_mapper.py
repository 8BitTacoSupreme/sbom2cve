#!/usr/bin/env python3
"""
PURL Mapper Function with Broadcast State

Maps upstream ecosystem PURLs (PyPI, npm, Go, Maven, Rust) to Nix PURLs
using broadcast mapping rules from Kafka topic.

This enables cross-ecosystem CVE matching: CVEs published for PyPI packages
can match Nix packages that wrap them.
"""

import re
import yaml
from typing import List, Dict, Optional
from dataclasses import dataclass
from packageurl import PackageURL


@dataclass
class MappingRule:
    """Represents a PURL mapping rule"""
    source_type: str
    target_type: str
    pattern: str
    target_patterns: List[str]
    derivation_rules: Optional[List[Dict]] = None
    transformation_rules: Optional[List[Dict]] = None
    confidence: float = 0.95


class PURLMapper:
    """
    Maps upstream PURLs to Nix PURLs using configurable rules.

    Handles:
    - Direct mappings (PyPI, npm, Rust)
    - Derivation rules (Go modules)
    - Override list for edge cases
    """

    def __init__(self, rules_config: Dict):
        """
        Initialize with rules configuration.

        Args:
            rules_config: Parsed YAML rules configuration
        """
        self.rules = {}
        self.overrides = rules_config.get('overrides', {})
        self.canonicalization_rules = rules_config.get('canonicalization', {}).get('rules', [])

        # Parse rules
        for rule_dict in rules_config.get('rules', []):
            rule = MappingRule(
                source_type=rule_dict['source_type'],
                target_type=rule_dict['target_type'],
                pattern=rule_dict['pattern'],
                target_patterns=rule_dict['target_patterns'],
                derivation_rules=rule_dict.get('derivation_rules'),
                transformation_rules=rule_dict.get('transformation_rules'),
                confidence=rule_dict.get('confidence', 0.95)
            )
            self.rules[rule.source_type] = rule

    def map_purl(self, upstream_purl: str) -> List[Dict]:
        """
        Map an upstream PURL to Nix PURLs.

        Args:
            upstream_purl: Upstream PURL (e.g., pkg:pypi/flask@2.0.0)

        Returns:
            List of mappings with confidence scores:
            [
                {
                    'purl': 'pkg:nix/nixpkgs/python312Packages.flask',
                    'confidence': 0.95,
                    'mapping_type': 'rule'
                },
                ...
            ]
        """
        # Check override list first
        purl_without_version = self._strip_version(upstream_purl)

        if purl_without_version in self.overrides:
            return [
                {
                    'purl': override_purl,
                    'confidence': 1.0,  # Overrides have 100% confidence
                    'mapping_type': 'override'
                }
                for override_purl in self.overrides[purl_without_version]
            ]

        # Parse PURL
        try:
            parsed = PackageURL.from_string(upstream_purl)
        except Exception as e:
            print(f"Failed to parse PURL {upstream_purl}: {e}")
            return []

        # Get mapping rule for this ecosystem
        rule = self.rules.get(parsed.type)
        if not rule:
            return []  # No rule for this ecosystem

        # Apply mapping
        return self._apply_rule(parsed, rule)

    def _apply_rule(self, parsed_purl: PackageURL, rule: MappingRule) -> List[Dict]:
        """Apply mapping rule to generate Nix PURLs"""
        mappings = []

        # Get package name
        package_name = parsed_purl.name

        # Apply transformations if needed
        if rule.transformation_rules:
            package_name = self._apply_transformations(package_name, rule.transformation_rules)

        # Apply derivation rules for complex ecosystems (Go, Maven)
        if rule.derivation_rules:
            derived_names = self._apply_derivation(parsed_purl, rule.derivation_rules)
        else:
            derived_names = [package_name]

        # Generate target PURLs
        for derived_name in derived_names:
            for target_pattern in rule.target_patterns:
                nix_purl = target_pattern.replace('{package}', package_name)
                nix_purl = nix_purl.replace('{derived_name}', derived_name)
                nix_purl = nix_purl.replace('{underscore}', package_name.replace('-', '_'))

                mappings.append({
                    'purl': nix_purl,
                    'confidence': rule.confidence,
                    'mapping_type': 'rule'
                })

        return mappings

    def _apply_derivation(self, parsed_purl: PackageURL, derivation_rules: List[Dict]) -> List[str]:
        """
        Apply derivation rules for complex name transformations.

        Example: golang.org/x/crypto → go-crypto
        """
        derived_names = []
        full_name = parsed_purl.namespace + '/' + parsed_purl.name if parsed_purl.namespace else parsed_purl.name

        for derivation in derivation_rules:
            # Check if rule matches
            if 'match_prefix' in derivation:
                if full_name.startswith(derivation['match_prefix']):
                    # Strip prefix and add new prefix
                    stripped = full_name.replace(derivation['strip_prefix'], '', 1)
                    derived = derivation.get('add_prefix', '') + stripped
                    derived_names.append(derived)

            elif 'match_exact' in derivation and derivation['match_exact']:
                # Direct mapping (e.g., github.com/user/repo → repo)
                if '/' in full_name:
                    derived_names.append(full_name.split('/')[-1])

        return derived_names if derived_names else [parsed_purl.name]

    def _apply_transformations(self, name: str, transformation_rules: List[Dict]) -> str:
        """Apply name transformations (e.g., hyphen to underscore)"""
        transformed = name

        for transform in transformation_rules:
            if transform.get('type') == 'underscore':
                transformed = name.replace(transform['pattern'], transform['replacement'])

        return transformed

    def _strip_version(self, purl: str) -> str:
        """Strip version from PURL for override lookup"""
        if '@' in purl:
            return purl.split('@')[0]
        return purl

    def canonicalize_nix_purl(self, nix_purl: str) -> str:
        """
        Canonicalize Nix PURL variants to standard form.

        Example: python312Packages.flask → python3Packages.flask
        """
        for canon_rule in self.canonicalization_rules:
            if 'pattern' in canon_rule:
                match = re.match(canon_rule['pattern'], nix_purl)
                if match:
                    # Apply canonicalization
                    canonical = canon_rule['canonical']
                    if '{package}' in canonical and len(match.groups()) > 1:
                        canonical = canonical.replace('{package}', match.group(2))
                    return canonical

        return nix_purl


class PURLMapperFunction:
    """
    Flink-compatible PURL Mapper function.

    This would be used in a Flink KeyedBroadcastProcessFunction:

    ```python
    class FlinkPURLMapper(KeyedBroadcastProcessFunction):
        def __init__(self):
            self.mapper = None

        def process_broadcast_element(self, value, ctx):
            # Load rules from broadcast stream
            rules = yaml.safe_load(value)
            self.mapper = PURLMapper(rules)

        def process_element(self, cve, ctx):
            # Map CVE PURLs to Nix
            enriched_purls = []

            for affected in cve['affected_products']:
                upstream_purl = affected['purl']
                mappings = self.mapper.map_purl(upstream_purl)

                for mapping in mappings:
                    enriched_purls.append({
                        'purl': mapping['purl'],
                        'confidence': mapping['confidence'],
                        'original_purl': upstream_purl
                    })

            cve['enriched_purls'] = enriched_purls
            yield cve
    ```
    """

    def __init__(self):
        self.mapper: Optional[PURLMapper] = None

    def process_broadcast_element(self, rules_yaml: str):
        """Process mapping rules from broadcast stream"""
        try:
            rules = yaml.safe_load(rules_yaml)
            self.mapper = PURLMapper(rules)
            print(f"Loaded PURL mapping rules version {rules.get('version')}")
        except Exception as e:
            print(f"Failed to load PURL mapping rules: {e}")

    def process_element(self, cve: Dict) -> Dict:
        """
        Process CVE and enrich with Nix PURLs.

        Args:
            cve: CVE record with affected_products containing upstream PURLs

        Returns:
            Enriched CVE with mapped Nix PURLs
        """
        if not self.mapper:
            print("WARNING: PURL mapper not initialized, skipping enrichment")
            return cve

        enriched_purls = []

        for affected in cve.get('affected_products', []):
            upstream_purl = affected.get('purl')
            if not upstream_purl:
                continue

            # Map to Nix PURLs
            mappings = self.mapper.map_purl(upstream_purl)

            for mapping in mappings:
                enriched_purls.append({
                    'purl': mapping['purl'],
                    'confidence': mapping['confidence'],
                    'mapping_type': mapping['mapping_type'],
                    'original_purl': upstream_purl,
                    'version_constraint': affected.get('version_affected')
                })

        # Add enriched PURLs to CVE
        cve['enriched_purls'] = enriched_purls
        cve['purl_mapping_count'] = len(enriched_purls)

        return cve


def test_purl_mapper():
    """Test PURL mapper with sample rules"""

    # Load test rules
    with open('/Users/jhogan/sbom2cve/config/purl-mapping/rules.yaml', 'r') as f:
        rules = yaml.safe_load(f)

    mapper = PURLMapper(rules)

    # Test cases
    test_cases = [
        "pkg:pypi/flask@2.0.0",
        "pkg:npm/express@4.18.0",
        "pkg:golang/golang.org/x/crypto@v0.0.0",
        "pkg:maven/org.apache.commons/commons-lang3@3.12.0",
        "pkg:cargo/tokio@1.28.0"
    ]

    for test_purl in test_cases:
        print(f"\n{test_purl}")
        mappings = mapper.map_purl(test_purl)
        for mapping in mappings:
            print(f"  → {mapping['purl']} (confidence: {mapping['confidence']}, type: {mapping['mapping_type']})")


if __name__ == '__main__':
    test_purl_mapper()
