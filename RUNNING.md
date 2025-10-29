# SBOM2CVE System - Currently Running

## Status: ✅ All Services Operational

The complete SBOM2CVE system is now running with **Nix/Flox integration as the default**, processing vulnerability alerts for your Flox environment in real-time.

## Infrastructure Services (Docker)

- **Kafka Broker** - `localhost:9092` (Confluent Platform 8.0.0 with KRaft mode)
- **Schema Registry** - `http://localhost:8081`
- **Flink JobManager** - `http://localhost:9081`
- **Flink TaskManager** - Running

## Application Services (Python)

All services running in virtual environment (`venv/`)

- **Nix SBOM Producer** - Scanning Flox environment and generating SPDX 2.3 SBOMs every 10 seconds
  - Log: `logs/sbom_producer.log`
  - Topic: `sboms`
  - PURL Format: `pkg:nix/nixpkgs/{package}@{version}`
  - Source: Current Flox environment (via `flox list`)

- **Nix CVE Producer** - Publishing Nix package vulnerabilities every 7 seconds
  - Log: `logs/cve_producer.log`
  - Topic: `cves`
  - Coverage: Real CVEs for common Nix packages (openssl, curl, git, nginx, python3, nodejs, etc.)

- **Python Matcher** - Intelligent PURL-based matching with semantic versioning
  - Log: `logs/matcher.log`
  - Consumes: `sboms`, `cves`
  - Produces: `alerts`

- **Alert Consumer** - Displaying formatted vulnerability alerts
  - Log: `logs/alert_consumer.log`
  - Consumes: `alerts`

- **Monitoring Dashboard** - Real-time message flow visualization
  - URL: **http://localhost:5001**
  - Log: `logs/dashboard.log`

## Kafka Topics

- `sboms` - SPDX JSON format SBOMs (3 partitions)
- `cves` - CVE records with affected products (3 partitions)
- `alerts` - Matched vulnerabilities with severity levels (3 partitions)

## Message Flow

```
Flox Environment (flox list)
       ↓
Nix SBOM Producer ──> sboms topic ──┐
                                     ├──> Python Matcher ──> alerts topic ──> Alert Consumer
Nix CVE Producer  ──> cves topic  ──┘                                    ├──> Dashboard
```

## Matching Logic

The system uses high-confidence PURL-based matching optimized for Nix packages:

1. **Package URL (PURL) normalization** - Matches package type, namespace, and name
   - Nix PURLs: `pkg:nix/nixpkgs/{package}@{version}`
   - Ecosystem isolation: Only Nix packages match Nix CVEs
2. **Semantic version range checking** - Uses Python `packaging` library for version constraints
3. **Confidence scoring** - 95% confidence for PURL + version range matches

## Confirmed Nix Package Matches

The system is successfully detecting vulnerabilities in your Flox environment:

- ✅ CVE-2021-22946 (HIGH) - curl TELNET stack disclosure
- ✅ CVE-2021-40330 (CRITICAL) - git remote code execution
- ✅ CVE-2021-23017 (HIGH) - nginx resolver vulnerability
- ✅ CVE-2021-29921 (CRITICAL) - python3 ipaddress issue
- ✅ CVE-2021-44531 (MEDIUM) - nodejs HTTP headers
- ✅ CVE-2022-3786 (HIGH) - openssl X.509 buffer overflow
- ✅ CVE-2022-3602 (HIGH) - openssl X.509 vulnerability

## Viewing Logs

```bash
# View real-time logs
tail -f logs/matcher.log        # See matching activity
tail -f logs/alert_consumer.log # See formatted alerts
tail -f logs/dashboard.log      # Dashboard activity

# View all logs together
tail -f logs/*.log
```

## Accessing Services

- **Dashboard**: Open http://localhost:5001 in your browser
  - Real-time message counts
  - Severity distribution
  - Recent messages from each topic

- **Flink Dashboard**: http://localhost:9081
  - Job management
  - Task manager status

- **Schema Registry**: http://localhost:8081/subjects
  - View registered schemas

## Stopping Services

```bash
# Stop Python applications
pkill -f 'python3 src/'

# Stop Docker infrastructure
docker compose down

# Stop everything and remove data
docker compose down -v
```

## Restarting Services

```bash
# Start infrastructure
./scripts/start_infrastructure.sh

# Start all Python applications
./scripts/start_all.sh
```

## System Architecture

- **Platform**: Confluent Platform (Kafka 8.0.0 with KRaft - no Zookeeper needed)
- **Stream Processing**: Python-based matcher with threading
- **Data Format**: SPDX 2.3 JSON for SBOMs
- **Primary Use Case**: **Nix/Flox package vulnerability monitoring**
- **Matching**: PURL-based with semantic versioning (optimized for Nix packages, also supports Maven, NPM, PyPI, Golang)
- **Dashboard**: Flask web application with real-time updates

## Why Nix/Flox as Default?

The system is now **optimized for the Nix/Flox ecosystem** with:

1. **High-Confidence Matching**: PURL type filtering prevents cross-ecosystem false positives
   - `pkg:nix/*` only matches Nix CVEs
   - `pkg:maven/*` won't match `pkg:nix/*` packages
2. **Real Flox Environment Scanning**: Directly scans your active Flox environment via `flox list`
3. **Curated CVE Database**: Real vulnerabilities affecting common Nix packages
4. **SBOM Attestation Ready**: SPDX 2.3 format compatible with cryptographic signing

See **[NIX_INTEGRATION.md](NIX_INTEGRATION.md)** for complete technical details.

## Using Other Ecosystems (Optional)

To switch back to multi-ecosystem mode with sample data:

```bash
# Stop current services
pkill -f 'python3 src/'

# Edit scripts/start_all.sh to use:
# python3 src/producers/sbom_producer.py (instead of nix_sbom_producer.py)
# python3 src/producers/cve_producer.py (instead of nix_cve_producer.py)

# Restart
./scripts/start_all.sh
```

## Testing with Sample Nix Data

To test without using your real Flox environment:

```bash
# Stop current producers
pkill -f 'nix_sbom_producer'

# Start with sample data
source venv/bin/activate
python3 src/producers/nix_sbom_producer.py --use-samples --interval 10 &
```

## Next Steps

1. Open **http://localhost:5001** to see the dashboard
2. Watch messages flowing in real-time
3. Check logs to see vulnerabilities being detected
4. Customize CVEs in `src/producers/cve_producer.py`
5. Customize SBOM packages in `src/producers/sbom_producer.py`
