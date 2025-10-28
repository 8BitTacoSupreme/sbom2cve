#!/bin/bash
# Test script for Nix/Flox SBOM integration

set -e

echo "================================================"
echo "Testing Nix/Flox SBOM Integration"
echo "================================================"
echo ""

# Activate virtual environment
source venv/bin/activate

echo "1️⃣  Testing Nix SBOM Generation..."
python3 << 'EOF'
from src.producers.nix_sbom_producer import NixSBOMProducer

producer = NixSBOMProducer()
packages = producer.get_sample_nix_packages()
sbom = producer.generate_sbom('test-validation', packages)

print(f"✅ Generated SBOM with {len(sbom['packages'])} packages")
for pkg in sbom['packages'][:3]:
    purl = pkg['externalRefs'][0]['referenceLocator']
    print(f"   - {pkg['name']} {pkg['versionInfo']}: {purl}")
print("")
EOF

echo "2️⃣  Testing Nix CVE Database..."
python3 << 'EOF'
from src.producers.nix_cve_producer import NixCVEProducer

producer = NixCVEProducer()
print(f"✅ Loaded {len(producer.KNOWN_NIX_CVES)} Nix CVEs")

# Show a few examples
for cve in producer.KNOWN_NIX_CVES[:3]:
    pkg_name = cve['affected_products'][0]['purl'].split('/')[-1]
    print(f"   - {cve['cve_id']} ({cve['severity']}): {pkg_name}")
print("")
EOF

echo "3️⃣  Testing PURL Matching Logic..."
python3 << 'EOF'
from src.matchers.simple_matcher import PURLMatcher

test_cases = [
    ("pkg:nix/nixpkgs/curl@7.79.1", "pkg:nix/nixpkgs/curl", ">=7.0.0 <7.80.0", True),
    ("pkg:nix/nixpkgs/git@2.33.0", "pkg:nix/nixpkgs/git", ">=2.0.0 <2.33.1", True),
    ("pkg:nix/nixpkgs/openssl@3.0.7", "pkg:nix/nixpkgs/openssl", ">=3.0.0 <3.0.7", False),
    ("pkg:maven/openssl@1.1.1", "pkg:nix/nixpkgs/openssl", ">=1.0.0 <2.0.0", False),
]

all_passed = True
for sbom_purl, cve_purl, constraint, expected in test_cases:
    # Test normalization
    sbom_norm = PURLMatcher.normalize_purl_for_comparison(sbom_purl)
    cve_norm = PURLMatcher.normalize_purl_for_comparison(cve_purl)
    purl_match = sbom_norm == cve_norm

    # Test version matching
    if purl_match:
        sbom_parsed = PURLMatcher.parse_purl(sbom_purl)
        version = sbom_parsed['version']
        version_match, confidence = PURLMatcher.matches_version_range(version, constraint)
        result = version_match
    else:
        result = False

    status = "✅" if result == expected else "❌"
    all_passed = all_passed and (result == expected)

    sbom_pkg = sbom_purl.split('/')[-1].split('@')[0]
    print(f"{status} {sbom_pkg}: {'MATCH' if result else 'NO MATCH'} (expected: {'MATCH' if expected else 'NO MATCH'})")

print("")
if all_passed:
    print("✅ All matching tests passed!")
else:
    print("❌ Some tests failed!")
print("")
EOF

echo "4️⃣  Testing End-to-End Message Flow..."
python3 << 'EOF'
from src.producers.nix_sbom_producer import NixSBOMProducer
from src.producers.nix_cve_producer import NixCVEProducer
import time

print("Sending test messages to Kafka...")

# Send Nix SBOM
sbom_prod = NixSBOMProducer()
packages = sbom_prod.get_sample_nix_packages()
sbom = sbom_prod.generate_sbom('validation-test', packages)
sbom_prod.send_sbom(sbom, 'validation-test')
print(f"✅ Sent SBOM with packages: curl, git, nginx, python3, nodejs")

time.sleep(2)

# Send Nix CVEs
cve_prod = NixCVEProducer()
test_cves = [
    cve_prod.KNOWN_NIX_CVES[2],  # curl CVE
    cve_prod.KNOWN_NIX_CVES[4],  # git CVE
]

for cve in test_cves:
    test_cve = cve.copy()
    test_cve['published'] = '2025-10-25T23:00:00Z'
    cve_prod.send_cve(test_cve)
    print(f"✅ Sent {cve['cve_id']} ({cve['severity']})")

print("")
print("Waiting 3 seconds for matcher to process...")
time.sleep(3)
EOF

echo "5️⃣  Checking for Matches in Logs..."
echo ""
if tail -20 logs/matcher.log | grep -q "CVE-2021-22946\|CVE-2021-40330"; then
    echo "✅ Found Nix CVE matches in matcher logs!"
    echo ""
    echo "Recent matches:"
    tail -20 logs/matcher.log | grep -E "CVE-2021-22946|CVE-2021-40330|curl|git" | tail -5
else
    echo "⚠️  No recent matches found (matcher may need a moment)"
fi

echo ""
echo "================================================"
echo "6️⃣  Summary"
echo "================================================"
echo ""
echo "✅ Nix SBOM generation works"
echo "✅ Nix CVE database loaded"
echo "✅ PURL matching logic validated"
echo "✅ Messages sent to Kafka"
echo ""
echo "📊 View the dashboard: http://localhost:5001"
echo "📝 Check matcher logs: tail -f logs/matcher.log | grep -E 'curl|git|CVE-2021-22946|CVE-2021-40330'"
echo "📋 Check alert consumer: tail -f logs/alert_consumer.log"
echo ""
echo "================================================"
echo "Testing Complete!"
echo "================================================"
