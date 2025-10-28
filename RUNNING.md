# SBOM2CVE System - Currently Running

## Status: ✅ All Services Operational

The complete SBOM2CVE system is now running and processing messages in real-time.

## Infrastructure Services (Docker)

- **Kafka Broker** - `localhost:9092` (Confluent Platform 8.0.0 with KRaft mode)
- **Schema Registry** - `http://localhost:8081`
- **Flink JobManager** - `http://localhost:9081`
- **Flink TaskManager** - Running

## Application Services (Python)

All services running in virtual environment (`venv/`)

- **SBOM Producer** - Generating SPDX 2.3 SBOMs every 5 seconds
  - Log: `logs/sbom_producer.log`
  - Topic: `sboms`

- **CVE Producer** - Generating CVE records every 3 seconds
  - Log: `logs/cve_producer.log`
  - Topic: `cves`

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
SBOM Producer ──> sboms topic ──┐
                                 ├──> Python Matcher ──> alerts topic ──> Alert Consumer
CVE Producer  ──> cves topic  ──┘                                    ├──> Dashboard
```

## Matching Logic

The system uses high-confidence PURL-based matching:

1. **Package URL (PURL) normalization** - Matches package type, namespace, and name
2. **Semantic version range checking** - Uses Python `packaging` library for version constraints
3. **Confidence scoring** - 95% confidence for PURL + version range matches

## Confirmed Matches

The system is successfully detecting vulnerabilities:

- ✅ CVE-2021-44228 (Log4Shell) affecting log4j-core
- ✅ CVE-2021-45046 affecting log4j-core
- ✅ CVE-2022-42003 affecting jackson-databind
- ✅ CVE-2022-32149 affecting golang.org/x/text
- ✅ CVE-2020-36518 affecting jackson-databind
- ✅ CVE-2022-42889 affecting commons-text

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
- **Matching**: PURL-based with semantic versioning (supports Maven, NPM, PyPI, Golang, **Nix/Flox**)
- **Dashboard**: Flask web application with real-time updates

## Nix/Flox Integration

The system now supports Nix packages from the nixpkgs and floxhub ecosystems! See **[NIX_INTEGRATION.md](NIX_INTEGRATION.md)** for details.

**Nix Producers**:
- `src/producers/nix_sbom_producer.py` - Generate SBOMs from Flox environments or samples
- `src/producers/nix_cve_producer.py` - Real CVEs affecting common Nix packages

**Start Nix Producers**:
```bash
# From venv
source venv/bin/activate

# Nix SBOM producer (sample mode)
python3 src/producers/nix_sbom_producer.py --use-samples --interval 10 &

# Nix CVE producer
python3 src/producers/nix_cve_producer.py --interval 7 &
```

**Verified Nix Matches**:
- ✅ CVE-2021-22946 (HIGH) - curl TELNET disclosure
- ✅ CVE-2021-40330 (CRITICAL) - Git RCE
- ✅ CVE-2021-23017 (HIGH) - nginx resolver vulnerability
- ✅ CVE-2021-29921 (CRITICAL) - Python ipaddress issue
- ✅ CVE-2021-44531 (MEDIUM) - Node.js HTTP headers

## Next Steps

1. Open **http://localhost:5001** to see the dashboard
2. Watch messages flowing in real-time
3. Check logs to see vulnerabilities being detected
4. Customize CVEs in `src/producers/cve_producer.py`
5. Customize SBOM packages in `src/producers/sbom_producer.py`
