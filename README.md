# SBOM-to-CVE Vulnerability Matcher

A real-time vulnerability detection system for **Nix and Flox packages** that matches Software Bill of Materials (SBOMs) against CVE data streams using Apache Kafka.

## Overview

This application provides **high-confidence vulnerability monitoring for Flox environments** by:

1. **Scanning Flox environments** - Automatically generates SPDX 2.3 SBOMs from your active Flox environment via `flox list`
2. **Streaming Nix CVE data** - Monitors known vulnerabilities affecting common Nix packages (openssl, curl, git, nginx, python3, nodejs, etc.)
3. **Intelligent PURL-based matching** - Uses Package URL matching with semantic version comparison for zero false positives
4. **Real-time alerting** - Immediate notification when vulnerabilities are detected in your environment

## Key Features

### Optimized for Nix/Flox Ecosystem

The system is specifically designed for Nix packages with:

- **Ecosystem Isolation**: `pkg:nix/nixpkgs/*` PURLs only match Nix CVEs, preventing false positives from other ecosystems
- **Flox Environment Integration**: Direct scanning of your Flox environment via `flox list`
- **Curated Nix CVE Database**: Real vulnerabilities affecting common Nix packages
- **SBOM Attestation Ready**: SPDX 2.3 format compatible with cryptographic signing

### High-Confidence Matching

Unlike simple text-based matching, this system uses:

- **Package URL (PURL) matching**: Structured Nix package identifiers (e.g., `pkg:nix/nixpkgs/openssl@3.0.7`)
- **Semantic version range checking**: Understands version constraints like `>=3.0.0 <3.0.7`
- **Confidence scoring**: Each match includes a confidence score (0.95 for PURL+version range matches)
- **Zero Cross-Ecosystem False Positives**: Maven openssl won't match Nix openssl

### SPDX 2.3 Compliance

SBOMs are generated in the industry-standard SPDX 2.3 JSON format with:
- Document metadata and creation info
- Package definitions with external references (PURLs)
- Relationship descriptions

## Architecture

```
┌─────────────────────┐
│  Flox Environment   │
│   (flox list)       │
└──────────┬──────────┘
           │
           v
┌─────────────────────┐         ┌─────────────────┐
│ Nix SBOM Producer   │────────>│  Kafka: sboms   │
│ pkg:nix/nixpkgs/*   │         └─────────┬───────┘
└─────────────────────┘                   │
                                          │
                                          v
                            ┌──────────────────────────┐
                            │                          │
                            │   PURL Matcher           │
┌─────────────────────┐     │   (Python)               │
│  Nix CVE Producer   │────>│   - Type filtering       │
│  Curated Nix CVEs   │     │   - Semantic versioning  │
└─────────────────────┘     │   - 95% confidence       │
        ^                   └──────────┬───────────────┘
        │                              │
  Kafka: cves                          v
                           ┌─────────────────────┐
                           │  Kafka: alerts      │
                           └──────────┬──────────┘
                                      │
                                      v
                            ┌─────────────────────┐
                            │  Alert Consumer +   │
                            │  Dashboard          │
                            │  (Python/Flask)     │
                            └─────────────────────┘
```

## Prerequisites

This project uses **Flox** for environment management. All dependencies are managed through Flox.

### Installed via Flox:
- Apache Kafka (apacheKafka)
- Apache Flink (flink)
- Python 3.12 (python312)
- OpenJDK (openjdk)

## Setup

### 1. Install Python Dependencies

Since this is a Flox-managed environment, install Python packages using pip within the environment:

```bash
python3 -m pip install -r requirements.txt
```

### 2. Start Kafka

```bash
./scripts/setup_kafka.sh
```

This will:
- Start Zookeeper
- Start Kafka
- Create topics: `sboms`, `cves`, `alerts`

## Quick Start

### 1. Start Infrastructure (Docker)

```bash
./scripts/start_infrastructure.sh
```

This starts Kafka, Schema Registry, and Flink using Docker Compose.

### 2. Start All Services (Nix/Flox mode by default)

```bash
./scripts/start_all.sh
```

This automatically starts:
- **Nix SBOM Producer** - Scans your Flox environment every 10 seconds
- **Nix CVE Producer** - Publishes Nix CVEs every 7 seconds
- **PURL Matcher** - Matches packages against CVEs with 95% confidence
- **Alert Consumer** - Displays vulnerability alerts
- **Dashboard** - Real-time visualization at http://localhost:5001

### 3. View Results

Open http://localhost:5001 to see:
- Real-time message counts
- Vulnerability severity distribution
- Recent alerts and matches

Or view logs:
```bash
tail -f logs/matcher.log          # See matching activity
tail -f logs/alert_consumer.log   # See formatted alerts
```

## Manual Operation (Optional)

If you prefer to run services individually:

### Nix SBOM Producer (Flox Environment Mode)

```bash
python3 src/producers/nix_sbom_producer.py --interval 10
```

This scans your current Flox environment via `flox list`.

### Nix CVE Producer

```bash
python3 src/producers/nix_cve_producer.py --interval 7
```

### Testing with Sample Data

To test without scanning your Flox environment:

```bash
python3 src/producers/nix_sbom_producer.py --use-samples --interval 10
```

## Example Alert Output

```
================================================================================
🚨 VULNERABILITY ALERT - CVE-2021-40330
================================================================================
Alert ID:         flox-current-env-CVE-2021-40330
Timestamp:        2024-10-29T14:32:15Z
SBOM:             SBOM for flox-current-env

CVE ID:           CVE-2021-40330
Severity:         CRITICAL
CVSS Score:       9.8
Confidence:       95.0%
Match Method:     purl_version_range

Affected Package:
  Name:           git
  Version:        2.33.0
  PURL:           pkg:nix/nixpkgs/git@2.33.0

Description:
  git_connect_git in connect.c in Git before 2.30.1 allows a repository
  path to contain a newline character, which may result in unexpected
  cross-protocol requests, as demonstrated by the git://localhost:1234/%0d%0a
  in a submodule URL

References:
  - https://nvd.nist.gov/vuln/detail/CVE-2021-40330
  - https://github.com/git/git/security/advisories/GHSA-r87g-vxf6-wm4w
================================================================================
```

## How the Matching Works

### 1. Ecosystem Isolation (PURL Type Filtering)

The system normalizes PURLs for comparison, preserving ecosystem types:

```
pkg:nix/nixpkgs/git@2.33.0
  → nix:nixpkgs:git

pkg:maven/org.apache/git@2.33.0
  → maven:org.apache:git
```

These won't match because `nix:nixpkgs:git ≠ maven:org.apache:git`

### 2. Version Range Checking (Semantic Versioning)

CVEs specify affected version ranges:
- `>=2.0.0 <2.30.1` - Affected versions
- `2.33.0` - Package version from SBOM
- **Result**: NO MATCH (version 2.33.0 is >= 2.30.1)

- `>=2.30.0 <2.34.0` - Affected versions
- `2.33.0` - Package version from SBOM
- **Result**: MATCH ✓ (confidence: 0.95)

### 3. Alert Generation

Only high-confidence matches generate alerts, including:
- CVE details (ID, severity, CVSS score)
- Affected package information from your Flox environment
- Confidence score (95% for PURL+version matches)
- References for remediation

### Why This Prevents False Positives

Traditional vulnerability scanners often match by package name alone, leading to false positives like:
- ❌ Maven's `git` library matching CVEs for the Git VCS
- ❌ PyPI's `openssl` wrapper matching CVEs for the C library

This system uses PURLs to ensure:
- ✅ Only `pkg:nix/nixpkgs/git` matches Nix git CVEs
- ✅ Only `pkg:nix/nixpkgs/openssl` matches Nix openssl CVEs
- ✅ Semantic version ranges ensure precise matching

## Stopping the Application

```bash
# Stop all Python services
pkill -f 'python3 src/'

# Stop Docker infrastructure
docker compose down

# Stop everything and remove data
docker compose down -v
```

## Development

### Project Structure

```
sbom2cve/
├── src/
│   ├── producers/
│   │   ├── nix_sbom_producer.py    # Nix/Flox SBOM generator (DEFAULT)
│   │   ├── nix_cve_producer.py     # Nix CVE database (DEFAULT)
│   │   ├── sbom_producer.py        # Multi-ecosystem SBOM samples
│   │   └── cve_producer.py         # Multi-ecosystem CVE samples
│   ├── matchers/
│   │   └── simple_matcher.py       # Python-based PURL matcher
│   ├── consumers/
│   │   └── alert_consumer.py       # Alert display
│   └── dashboard/
│       └── dashboard.py            # Flask web dashboard
├── scripts/
│   ├── start_infrastructure.sh     # Start Docker services
│   └── start_all.sh                # Start all Python services (Nix mode)
├── logs/                           # Application logs
├── requirements.txt                # Python dependencies
├── NIX_INTEGRATION.md              # Nix/Flox documentation
├── RUNNING.md                      # System status
└── README.md                       # This file
```

### Adding New Nix CVEs

Edit `src/producers/nix_cve_producer.py` and add entries to the CVE list with:
- CVE ID
- Affected Nix packages with PURLs (`pkg:nix/nixpkgs/{package}`)
- Version ranges using semantic versioning
- Severity and CVSS score

### Customizing SBOM Generation

The Nix SBOM producer automatically scans your Flox environment. To customize:
- Modify `get_flox_packages()` in `src/producers/nix_sbom_producer.py`
- Or use `--use-samples` flag for testing with predefined packages

## Technology Stack

- **Apache Kafka**: Distributed streaming platform for real-time data
- **Python 3.12**: Implementation language (via Flox)
- **SPDX 2.3**: Industry-standard SBOM format
- **Package URLs (PURL)**: Structured package identifiers with ecosystem isolation
- **Flox**: Environment and dependency management
- **Flask**: Web dashboard framework

## Documentation

- **[NIX_INTEGRATION.md](NIX_INTEGRATION.md)** - Complete technical documentation of Nix/Flox integration
- **[RUNNING.md](RUNNING.md)** - Current system status and service details
- **[VALIDATION_GUIDE.md](VALIDATION_GUIDE.md)** - Testing and validation procedures
- **[test_nix_integration.sh](test_nix_integration.sh)** - Automated test script

## Future Enhancements

- [ ] Integration with NVD API for automatic Nix CVE updates
- [ ] Vulnix integration for cross-referencing
- [ ] FloxHub-specific package metadata support
- [ ] Cryptographic SBOM signature verification
- [ ] Support for CycloneDX format
- [ ] Alert deduplication and aggregation
- [ ] Historical vulnerability trend analysis
- [ ] Slack/Discord webhook notifications

## License

This is a demonstration project for educational purposes.

## References

- [SPDX Specification](https://spdx.dev/specifications/)
- [Package URL Specification](https://github.com/package-url/purl-spec)
- [Apache Kafka Documentation](https://kafka.apache.org/documentation/)
- [Apache Flink Documentation](https://flink.apache.org/documentation/)
- [NVD CVE Database](https://nvd.nist.gov/vuln)
