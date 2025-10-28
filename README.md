# SBOM-to-CVE Vulnerability Matcher

A real-time vulnerability detection system that matches Software Bill of Materials (SBOMs) against CVE data streams using Apache Kafka and Apache Flink.

## Overview

This application demonstrates intelligent vulnerability matching by:

1. **Generating SPDX-compliant SBOMs** - Produces realistic SBOM documents with Package URLs (PURLs)
2. **Streaming CVE data** - Simulates CVE feed with known vulnerabilities
3. **Intelligent matching with Flink** - Uses PURL-based matching with semantic version comparison for high-confidence alerts
4. **Real-time alerting** - Sends vulnerability alerts to a Kafka topic for downstream processing

## Key Features

### High-Confidence Matching

Unlike simple text-based matching, this system uses:

- **Package URL (PURL) matching**: Structured package identifiers (e.g., `pkg:maven/org.apache.logging.log4j/log4j-core@2.14.1`)
- **Semantic version range checking**: Understands version constraints like `>=2.0 <2.15.0`
- **Confidence scoring**: Each match includes a confidence score (0.95 for PURL+version range matches)

### SPDX 2.3 Compliance

SBOMs are generated in the industry-standard SPDX 2.3 JSON format with:
- Document metadata and creation info
- Package definitions with external references (PURLs)
- Relationship descriptions

## Architecture

```
┌─────────────────┐         ┌─────────────────┐
│  SBOM Producer  │────────>│  Kafka: sboms   │
│  (Python)       │         └─────────┬───────┘
└─────────────────┘                   │
                                      │
                                      v
                            ┌──────────────────────┐
                            │                      │
                            │   Flink Job          │
┌─────────────────┐         │   SBOM-CVE Matcher   │
│  CVE Producer   │────────>│   (PURL + Version)   │
│  (Python)       │         │                      │
└─────────────────┘         └──────────┬───────────┘
        ^                              │
        │                              v
  Kafka: cves              ┌─────────────────────┐
                           │  Kafka: alerts      │
                           └──────────┬──────────┘
                                      │
                                      v
                            ┌─────────────────────┐
                            │  Alert Consumer     │
                            │  (Python)           │
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

## Running the Application

You'll need **4 terminal windows** (all within the Flox environment):

### Terminal 1: SBOM Producer

```bash
python3 src/producers/sbom_producer.py
```

Options:
- `--bootstrap-servers`: Kafka servers (default: localhost:9092)
- `--topic`: Topic name (default: sboms)
- `--interval`: Seconds between SBOMs (default: 5)

### Terminal 2: CVE Producer

```bash
python3 src/producers/cve_producer.py
```

Options:
- `--bootstrap-servers`: Kafka servers (default: localhost:9092)
- `--topic`: Topic name (default: cves)
- `--interval`: Seconds between CVEs (default: 3)

### Terminal 3: Flink Matching Job

```bash
python3 src/flink_jobs/sbom_cve_matcher.py
```

This starts the Flink job that:
- Consumes from `sboms` and `cves` topics
- Performs intelligent PURL+version matching
- Produces alerts to `alerts` topic

### Terminal 4: Alert Consumer

```bash
python3 src/consumers/alert_consumer.py
```

Options:
- `--bootstrap-servers`: Kafka servers (default: localhost:9092)
- `--topic`: Topic name (default: alerts)

## Example Alert Output

```
================================================================================
🚨 VULNERABILITY ALERT - CVE-2021-44228
================================================================================
Alert ID:         SPDXRef-DOCUMENT-abc123-CVE-2021-44228
Timestamp:        1634567890000
SBOM:             SBOM for web-app-frontend

CVE ID:           CVE-2021-44228
Severity:         CRITICAL
CVSS Score:       10.0
Confidence:       95.0%
Match Method:     purl_version_range

Affected Package:
  Name:           log4j-core
  Version:        2.14.1
  PURL:           pkg:maven/org.apache.logging.log4j/log4j-core@2.14.1

Description:
  Apache Log4j2 JNDI features do not protect against attacker controlled
  LDAP and other JNDI related endpoints

References:
  - https://nvd.nist.gov/vuln/detail/CVE-2021-44228
================================================================================
```

## How the Matching Works

### 1. Package Identity Matching

The system normalizes PURLs for comparison:

```
pkg:maven/org.apache.logging.log4j/log4j-core@2.14.1
  → maven:org.apache.logging.log4j:log4j-core
```

### 2. Version Range Checking

CVEs specify affected version ranges:
- `>=2.0-beta9 <2.15.0` - Affected versions
- `2.14.1` - Package version from SBOM
- **Result**: MATCH ✓ (confidence: 0.95)

### 3. Alert Generation

Only high-confidence matches generate alerts, including:
- CVE details (ID, severity, CVSS score)
- Affected package information
- Confidence score
- References for remediation

## Stopping the Application

1. Stop all Python processes (Ctrl+C in each terminal)
2. Stop Kafka and Zookeeper:
   ```bash
   # Use PIDs from setup_kafka.sh output
   kill <KAFKA_PID> <ZOOKEEPER_PID>
   ```

## Development

### Project Structure

```
sbom2cve/
├── src/
│   ├── producers/
│   │   ├── sbom_producer.py    # SPDX SBOM generator
│   │   └── cve_producer.py     # CVE data generator
│   ├── flink_jobs/
│   │   └── sbom_cve_matcher.py # Flink matching logic
│   └── consumers/
│       └── alert_consumer.py   # Alert display
├── scripts/
│   └── setup_kafka.sh          # Kafka setup script
├── config/                     # Configuration files
├── data/                       # Data files
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

### Adding New CVEs

Edit `src/producers/cve_producer.py` and add entries to the `KNOWN_CVES` list with:
- CVE ID
- Affected products with PURLs
- Version ranges
- Severity and CVSS score

### Adding New SBOM Packages

Edit `src/producers/sbom_producer.py` and add entries to `SAMPLE_PACKAGES` with:
- Package name
- Version
- PURL (Package URL)

## Technology Stack

- **Apache Kafka**: Distributed streaming platform
- **Apache Flink**: Stream processing framework
- **Python 3.12**: Implementation language
- **SPDX 2.3**: SBOM format standard
- **Package URLs (PURL)**: Package identifier specification
- **Flox**: Environment and dependency management

## Future Enhancements

- [ ] Integration with real NVD CVE feeds
- [ ] Support for additional SBOM formats (CycloneDX)
- [ ] Machine learning for fuzzy package matching
- [ ] Web dashboard for alert visualization
- [ ] Alert deduplication and aggregation
- [ ] Integration with ticketing systems
- [ ] Historical trend analysis

## License

This is a demonstration project for educational purposes.

## References

- [SPDX Specification](https://spdx.dev/specifications/)
- [Package URL Specification](https://github.com/package-url/purl-spec)
- [Apache Kafka Documentation](https://kafka.apache.org/documentation/)
- [Apache Flink Documentation](https://flink.apache.org/documentation/)
- [NVD CVE Database](https://nvd.nist.gov/vuln)
