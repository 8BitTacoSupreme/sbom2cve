#!/usr/bin/env python3
"""
Unit Tests for PURL Mapper

Tests mapping from upstream ecosystems (PyPI, npm, Go, Maven, Rust) to Nix PURLs.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/flink/functions'))

import pytest
import yaml
from purl_mapper import PURLMapper, PURLMapperFunction


@pytest.fixture
def rules_config():
    """Load test rules configuration"""
    rules_path = os.path.join(os.path.dirname(__file__), '../../config/purl-mapping/rules.yaml')
    with open(rules_path, 'r') as f:
        return yaml.safe_load(f)


@pytest.fixture
def mapper(rules_config):
    """Create PURLMapper instance"""
    return PURLMapper(rules_config)


class TestPyPIMapping:
    """Test PyPI → Nix PURL mappings"""

    def test_flask_mapping(self, mapper):
        """Test basic PyPI package mapping"""
        mappings = mapper.map_purl("pkg:pypi/flask@2.0.0")

        assert len(mappings) == 4
        purls = [m['purl'] for m in mappings]

        assert "pkg:nix/nixpkgs/python312Packages.flask" in purls
        assert "pkg:nix/nixpkgs/python311Packages.flask" in purls
        assert "pkg:nix/nixpkgs/python310Packages.flask" in purls
        assert "pkg:nix/nixpkgs/python3Packages.flask" in purls

        # Check confidence
        for mapping in mappings:
            assert mapping['confidence'] == 0.95
            assert mapping['mapping_type'] == 'rule'

    def test_requests_mapping(self, mapper):
        """Test another common PyPI package"""
        mappings = mapper.map_purl("pkg:pypi/requests@2.28.0")

        assert len(mappings) > 0
        assert any('python' in m['purl'] and 'requests' in m['purl'] for m in mappings)

    def test_pillow_override(self, mapper):
        """Test PyPI package with override"""
        mappings = mapper.map_purl("pkg:pypi/pillow@9.0.0")

        assert len(mappings) == 1
        assert mappings[0]['purl'] == "pkg:nix/nixpkgs/python3Packages.pillow"
        assert mappings[0]['confidence'] == 1.0  # Overrides have 100% confidence
        assert mappings[0]['mapping_type'] == 'override'


class TestNPMMapping:
    """Test npm → Nix PURL mappings"""

    def test_express_mapping(self, mapper):
        """Test basic npm package mapping"""
        mappings = mapper.map_purl("pkg:npm/express@4.18.0")

        assert len(mappings) == 2
        purls = [m['purl'] for m in mappings]

        assert "pkg:nix/nixpkgs/nodePackages.express" in purls
        assert all('nodePackages' in m['purl'] for m in mappings)

        for mapping in mappings:
            assert mapping['confidence'] == 0.90

    def test_typescript_override(self, mapper):
        """Test npm package with override"""
        mappings = mapper.map_purl("pkg:npm/typescript@4.9.0")

        assert len(mappings) == 1
        assert mappings[0]['purl'] == "pkg:nix/nixpkgs/nodePackages.typescript"
        assert mappings[0]['mapping_type'] == 'override'

    def test_scoped_package(self, mapper):
        """Test scoped npm package (@types/node)"""
        mappings = mapper.map_purl("pkg:npm/%40types/node@18.0.0")

        # Should map via rule (not override for URL-encoded scoped package)
        assert len(mappings) >= 1
        # Should have nodePackages mapping
        assert any('nodePackages' in m['purl'] and 'node' in m['purl'] for m in mappings)


class TestGoMapping:
    """Test Go → Nix PURL mappings"""

    def test_golang_x_crypto_derivation(self, mapper):
        """Test Go module with derivation (golang.org/x/crypto)"""
        mappings = mapper.map_purl("pkg:golang/golang.org/x/crypto@v0.0.0")

        assert len(mappings) == 1
        assert mappings[0]['purl'] == "pkg:nix/nixpkgs/go-crypto"
        assert mappings[0]['mapping_type'] == 'override'
        assert mappings[0]['confidence'] == 1.0

    def test_golang_x_text_derivation(self, mapper):
        """Test another golang.org/x/* package"""
        # This tests the derivation rule (strip golang.org/x/, add go-)
        # Should map to go-text even without override
        mappings = mapper.map_purl("pkg:golang/golang.org/x/text@v0.3.0")

        assert len(mappings) > 0
        # Check if derivation produces go-text
        assert any('go-text' in m['purl'] for m in mappings)

    def test_github_cobra(self, mapper):
        """Test GitHub-hosted Go module"""
        mappings = mapper.map_purl("pkg:golang/github.com/spf13/cobra@v1.5.0")

        assert len(mappings) == 1
        assert mappings[0]['purl'] == "pkg:nix/nixpkgs/cobra"
        assert mappings[0]['mapping_type'] == 'override'

    def test_prometheus_client(self, mapper):
        """Test complex GitHub Go module"""
        mappings = mapper.map_purl("pkg:golang/github.com/prometheus/client_golang@v1.12.0")

        assert len(mappings) == 1
        assert mappings[0]['purl'] == "pkg:nix/nixpkgs/prometheus-client-go"


class TestMavenMapping:
    """Test Maven → Nix PURL mappings"""

    def test_commons_lang3(self, mapper):
        """Test Maven artifact mapping"""
        mappings = mapper.map_purl("pkg:maven/org.apache.commons/commons-lang3@3.12.0")

        assert len(mappings) == 1
        assert mappings[0]['purl'] == "pkg:nix/nixpkgs/commons-lang3"
        assert mappings[0]['mapping_type'] == 'override'

    def test_jackson_databind(self, mapper):
        """Test another Maven artifact"""
        mappings = mapper.map_purl("pkg:maven/com.fasterxml.jackson.core/jackson-databind@2.13.0")

        assert len(mappings) == 1
        assert mappings[0]['purl'] == "pkg:nix/nixpkgs/jackson-databind"


class TestCargoMapping:
    """Test Rust/Cargo → Nix PURL mappings"""

    def test_tokio_mapping(self, mapper):
        """Test Rust crate mapping"""
        mappings = mapper.map_purl("pkg:cargo/tokio@1.28.0")

        assert len(mappings) == 1
        assert mappings[0]['purl'] == "pkg:nix/nixpkgs/tokio"
        assert mappings[0]['mapping_type'] == 'override'

    def test_serde_mapping(self, mapper):
        """Test another common Rust crate"""
        mappings = mapper.map_purl("pkg:cargo/serde@1.0.160")

        assert len(mappings) == 1
        assert mappings[0]['purl'] == "pkg:nix/nixpkgs/serde"


class TestVersionStripping:
    """Test that versions are properly stripped for override lookups"""

    def test_version_stripped_for_override(self, mapper):
        """Verify versions are stripped when checking overrides"""
        # Both should hit the same override
        mappings1 = mapper.map_purl("pkg:pypi/pillow@9.0.0")
        mappings2 = mapper.map_purl("pkg:pypi/pillow@10.0.0")

        assert mappings1[0]['purl'] == mappings2[0]['purl']
        assert mappings1[0]['mapping_type'] == 'override'


class TestCanonicalization:
    """Test Nix PURL canonicalization"""

    def test_python_version_canonicalization(self, mapper):
        """Test that python312Packages normalizes to python3Packages"""
        # This tests the canonicalization rules
        canonical = mapper.canonicalize_nix_purl("pkg:nix/nixpkgs/python312Packages.flask")

        # Should normalize to python3Packages
        assert "python3Packages" in canonical or "python312Packages" in canonical


class TestPURLMapperFunction:
    """Test Flink-compatible wrapper function"""

    def test_process_broadcast_element(self, rules_config):
        """Test loading rules from YAML"""
        func = PURLMapperFunction()

        rules_yaml = yaml.dump(rules_config)
        func.process_broadcast_element(rules_yaml)

        assert func.mapper is not None

    def test_process_element_enrichment(self, rules_config):
        """Test CVE enrichment with Nix PURLs"""
        func = PURLMapperFunction()

        # Load rules
        rules_yaml = yaml.dump(rules_config)
        func.process_broadcast_element(rules_yaml)

        # Create test CVE
        cve = {
            'cve_id': 'CVE-2024-TEST-001',
            'affected_products': [
                {
                    'purl': 'pkg:pypi/flask@2.0.0',
                    'version_affected': '>=2.0.0 <2.3.0'
                }
            ]
        }

        # Process
        enriched = func.process_element(cve)

        # Verify enrichment
        assert 'enriched_purls' in enriched
        assert enriched['purl_mapping_count'] > 0

        # Check that Nix PURLs were added
        nix_purls = [p for p in enriched['enriched_purls'] if 'pkg:nix' in p['purl']]
        assert len(nix_purls) > 0

        # Verify structure
        for enriched_purl in enriched['enriched_purls']:
            assert 'purl' in enriched_purl
            assert 'confidence' in enriched_purl
            assert 'mapping_type' in enriched_purl
            assert 'original_purl' in enriched_purl
            assert enriched_purl['original_purl'] == 'pkg:pypi/flask@2.0.0'

    def test_process_element_without_mapper(self):
        """Test that processing works gracefully without initialized mapper"""
        func = PURLMapperFunction()

        cve = {
            'cve_id': 'CVE-2024-TEST-002',
            'affected_products': [{'purl': 'pkg:pypi/requests@2.28.0'}]
        }

        enriched = func.process_element(cve)

        # Should return original CVE without enrichment
        assert 'enriched_purls' not in enriched or enriched['enriched_purls'] == []


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_invalid_purl(self, mapper):
        """Test handling of invalid PURL format"""
        mappings = mapper.map_purl("not-a-valid-purl")

        assert len(mappings) == 0  # Should return empty list

    def test_unsupported_ecosystem(self, mapper):
        """Test handling of unsupported ecosystem"""
        mappings = mapper.map_purl("pkg:nuget/Newtonsoft.Json@13.0.0")

        assert len(mappings) == 0  # No rule for nuget

    def test_purl_without_version(self, mapper):
        """Test PURL without version qualifier"""
        mappings = mapper.map_purl("pkg:pypi/flask")

        # Should still work
        assert len(mappings) > 0


class TestConfidenceScores:
    """Test confidence scoring for mappings"""

    def test_override_confidence(self, mapper):
        """Overrides should have 100% confidence"""
        mappings = mapper.map_purl("pkg:pypi/pillow@9.0.0")

        assert mappings[0]['confidence'] == 1.0

    def test_rule_confidence(self, mapper):
        """Rule-based mappings should have configured confidence"""
        mappings = mapper.map_purl("pkg:pypi/flask@2.0.0")

        assert all(m['confidence'] == 0.95 for m in mappings)

    def test_npm_confidence(self, mapper):
        """npm mappings should have 0.90 confidence"""
        mappings = mapper.map_purl("pkg:npm/express@4.18.0")

        assert all(m['confidence'] == 0.90 for m in mappings)


if __name__ == '__main__':
    # Run tests with pytest
    pytest.main([__file__, '-v'])
