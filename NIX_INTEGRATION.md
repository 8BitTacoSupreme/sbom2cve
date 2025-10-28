# Nix/Flox SBOM Integration

## Overview

The SBOM2CVE system now supports Nix packages from the nixpkgs and floxhub ecosystems with high-confidence matching using Package URLs (PURLs).

## Key Features

### 1. Nix-Specific SBOM Generation

**File**: `src/producers/nix_sbom_producer.py`

- Generates SPDX 2.3 compliant SBOMs for Nix packages
- Supports two modes:
  - **Flox Environment Mode**: Scans current Flox environment via `flox list`
  - **Sample Mode**: Uses predefined Nix packages for testing

**PURL Format for Nix Packages**:
```
pkg:nix/nixpkgs/{package-name}@{version}
```

Examples:
```
pkg:nix/nixpkgs/openssl@1.1.1k
pkg:nix/nixpkgs/curl@7.79.1
pkg:nix/nixpkgs/git@2.33.0
pkg:nix/nixpkgs/python3@3.9.7
```

**Usage**:
```bash
# Use real Flox environment
python3 src/producers/nix_sbom_producer.py

# Use sample packages for testing
python3 src/producers/nix_sbom_producer.py --use-samples --interval 10
```

### 2. Nix CVE Database

**File**: `src/producers/nix_cve_producer.py`

Contains real CVEs affecting common Nix packages:

| CVE ID | Severity | Package | Description |
|--------|----------|---------|-------------|
| CVE-2022-3786 | HIGH | openssl | X.509 Email Address Buffer Overflow |
| CVE-2022-3602 | HIGH | openssl | X.509 Variable Length Buffer Overflow |
| CVE-2021-22946 | HIGH | curl | TELNET stack contents disclosure |
| CVE-2021-40330 | CRITICAL | git | Remote code execution |
| CVE-2021-23017 | HIGH | nginx | Resolver off-by-one |
| CVE-2021-3711 | CRITICAL | openssl | SM2 Decryption Buffer Overflow |
| CVE-2021-29921 | CRITICAL | python3 | ipaddress leading zeros misinterpretation |
| CVE-2021-44531 | MEDIUM | nodejs | Accepting non-standard HTTP headers |
| CVE-2021-44717 | HIGH | go | net/http header canonicalization cache |
| CVE-2021-3999 | HIGH | glibc | realpath() buffer overflow |
| CVE-2022-1271 | HIGH | gzip | Arbitrary file write |

**Usage**:
```bash
python3 src/producers/nix_cve_producer.py --interval 7
```

### 3. PURL-Based Matching

The existing matcher (`src/matchers/simple_matcher.py`) already supports Nix PURLs through its generic PURL parsing:

**Matching Process**:
1. Parse both SBOM and CVE PURLs
2. Normalize to `type:namespace:name` format
3. Compare normalized PURLs (version-independent)
4. If match found, check version constraints using semantic versioning
5. Generate alert with 95% confidence score

**Example Match**:
```
SBOM: pkg:nix/nixpkgs/curl@7.79.1
CVE:  pkg:nix/nixpkgs/curl with constraint ">=7.0.0 <7.80.0"
Result: MATCH (confidence: 0.95)
```

## Reducing False Positives

### Focus on Nix/Flox Universe

The system reduces false positives by:

1. **PURL Type Filtering**: Only `pkg:nix/*` packages match Nix CVEs
2. **Namespace Isolation**: nixpkgs packages don't match maven/npm/pypi
3. **Semantic Versioning**: Precise version range matching (not fuzzy text)
4. **Flox Environment Scanning**: Real package data from actual environments

### Example: No Cross-Ecosystem Matches

```
❌ pkg:maven/openssl@1.1.1 does NOT match pkg:nix/nixpkgs/openssl
❌ pkg:npm/git@2.33.0 does NOT match pkg:nix/nixpkgs/git
✅ pkg:nix/nixpkgs/curl@7.79.1 DOES match pkg:nix/nixpkgs/curl
```

## Cryptographic Attestation Support

The system is ready for Flox's cryptographic SBOM attestation:

1. **SPDX 2.3 Format**: Industry standard for SBOMs
2. **PURL References**: Unique package identification
3. **Document Namespace**: Allows for signed document verification
4. **Creation Info**: Tracks tool and organization metadata

Future enhancement: Add signature verification in SBOM consumer.

## Testing the Integration

### 1. Test Nix SBOM Generation

```bash
source venv/bin/activate
python3 -c "
from src.producers.nix_sbom_producer import NixSBOMProducer
producer = NixSBOMProducer()
packages = producer.get_sample_nix_packages()
sbom = producer.generate_sbom('test-env', packages)
print(f'Generated SBOM with {len(sbom[\"packages\"])} packages')
"
```

### 2. Test End-to-End Matching

```bash
# Terminal 1: Start infrastructure
./scripts/start_infrastructure.sh

# Terminal 2: Start all services
./scripts/start_all.sh

# Terminal 3: Start Nix producers
source venv/bin/activate
python3 src/producers/nix_sbom_producer.py --use-samples --interval 10 &
python3 src/producers/nix_cve_producer.py --interval 7 &

# Monitor matcher logs
tail -f logs/matcher.log | grep -E "curl|git|openssl|nodejs"
```

### 3. Verify Matches

```bash
# Check recent alerts
tail -f logs/alert_consumer.log

# Check matcher logs
tail -f logs/matcher.log | grep "Alert sent"

# View dashboard
open http://localhost:5001
```

## Verified Matches

The following Nix package vulnerabilities have been successfully detected:

```
✅ CVE-2021-22946 (HIGH) affects curl@7.79.1
✅ CVE-2021-40330 (CRITICAL) affects git@2.33.0
✅ CVE-2021-23017 (HIGH) affects nginx@1.20.1
✅ CVE-2021-29921 (CRITICAL) affects python3@3.9.7
✅ CVE-2021-44531 (MEDIUM) affects nodejs@16.13.0
```

## Architecture

```
Flox Environment
       ↓
  flox list
       ↓
Nix SBOM Producer → sboms topic
       ↓                ↓
   Kafka           Matcher (PURL-based)
       ↓                ↓
Nix CVE Producer → cves topic
       ↓
   alerts topic → Alert Consumer
       ↓
   Dashboard (http://localhost:5001)
```

## Files Added

- `src/producers/nix_sbom_producer.py` - Nix/Flox SBOM generator
- `src/producers/nix_cve_producer.py` - Nix CVE database and producer
- `NIX_INTEGRATION.md` - This documentation

## Files Modified

None! The existing matcher already supports Nix PURLs through its generic PURL implementation.

## Benefits for Flox Users

1. **High-Confidence Matching**: 95% confidence using PURLs + semantic versioning
2. **No False Positives from Other Ecosystems**: Nix packages only match Nix CVEs
3. **Real-Time Monitoring**: Continuous scanning of Flox environments
4. **SPDX Standard**: Compatible with SBOM tools and attestation systems
5. **Scalable**: Handles large numbers of packages efficiently via Kafka
6. **Observable**: Dashboard and logs provide full visibility

## Next Steps

1. **Integrate with Flox SBOM Generation**: Replace sample data with real Flox SBOMs
2. **Add Signature Verification**: Validate cryptographic attestations
3. **NVD Integration**: Auto-populate Nix CVEs from NVD database
4. **Vulnix Integration**: Cross-reference with existing Nix vulnerability tools
5. **FloxHub Support**: Add support for FloxHub-specific package metadata

## Example Output

```
Starting Nix SBOM production (interval: 10s, real_flox: False)
Sent SBOM for nix-sample-env to sboms:0 @ offset 368
[1] Produced Nix SBOM for nix-sample-env with 6 packages

Starting Nix CVE production (interval: 7s)
Sent CVE CVE-2021-22946 to cves:0 @ offset 703
[1] Produced Nix CVE: CVE-2021-22946 (HIGH)

Matcher Output:
📦 Received SBOM: nix-sample-env-sbom
🔒 Received CVE: CVE-2021-22946
✅ Alert sent: CVE-2021-22946 affects curl
```
