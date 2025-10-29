# Setup Guide for SBOM-CVE Matcher

## Overview

This system provides **real-time vulnerability monitoring for Nix/Flox packages**. The default configuration scans your Flox environment and matches against known Nix CVEs.

## Prerequisites

This project uses **Flox** for environment management. The following are already installed via Flox:
- kafka-python (Python Kafka client)
- packaging (Python version parsing for semantic versioning)
- flask (Web dashboard)
- Python 3.12
- OpenJDK

## Infrastructure Setup

### Docker Compose (Recommended)

**Prerequisites**: Docker Desktop must be running

```bash
./scripts/start_infrastructure.sh
```

This starts:
- **Kafka Broker** (localhost:9092) - Using Confluent Platform with KRaft (no Zookeeper)
- **Schema Registry** (localhost:8081) - Schema management
- **Flink JobManager** (localhost:9081) - Stream processing UI
- **Flink TaskManager** - Processing engine

Topics are automatically created:
- `sboms` - SPDX 2.3 format SBOMs (3 partitions)
- `cves` - CVE records with affected products (3 partitions)
- `alerts` - Matched vulnerabilities (3 partitions)

**To stop**:
```bash
docker compose down

# Remove data volumes
docker compose down -v
```

### Alternative: Manual Kafka Installation via Flox

The `apacheKafka` package is installed via Flox, but the scripts need to be located. You can run Kafka manually:

1. Find Kafka installation:
   ```bash
   flox list | grep apacheKafka
   ```

2. Locate Kafka binaries (typically in `/nix/store/...`)

3. Start Zookeeper:
   ```bash
   <kafka-dir>/bin/zookeeper-server-start.sh <kafka-dir>/config/zookeeper.properties
   ```

4. Start Kafka (in another terminal):
   ```bash
   <kafka-dir>/bin/kafka-server-start.sh <kafka-dir>/config/server.properties
   ```

5. Create topics (in another terminal):
   ```bash
   <kafka-dir>/bin/kafka-topics.sh --create --topic sboms --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
   <kafka-dir>/bin/kafka-topics.sh --create --topic cves --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
   <kafka-dir>/bin/kafka-topics.sh --create --topic alerts --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
   ```

## Running the Application

### Quick Start (Nix/Flox Mode - Default)

Once infrastructure is running, start all services:

```bash
./scripts/start_all.sh
```

This automatically starts:
1. **Nix SBOM Producer** - Scans your Flox environment via `flox list` (every 10s)
2. **Nix CVE Producer** - Publishes known Nix CVEs (every 7s)
3. **PURL Matcher** - Matches packages against CVEs with 95% confidence
4. **Alert Consumer** - Displays vulnerability alerts
5. **Dashboard** - Web UI at http://localhost:5001

**View Dashboard**: Open http://localhost:5001

**View Logs**:
```bash
tail -f logs/matcher.log          # Matching activity
tail -f logs/alert_consumer.log   # Formatted alerts
tail -f logs/sbom_producer.log    # SBOM generation
tail -f logs/cve_producer.log     # CVE publishing
```

### Manual Service Control (Optional)

If you prefer to run services individually:

```bash
source venv/bin/activate

# Nix SBOM Producer (scans Flox environment)
python3 src/producers/nix_sbom_producer.py --interval 10 &

# Nix CVE Producer
python3 src/producers/nix_cve_producer.py --interval 7 &

# Matcher
python3 src/matchers/simple_matcher.py &

# Alert Consumer
python3 src/consumers/alert_consumer.py &

# Dashboard
python3 src/dashboard/dashboard.py &
```

### Testing Mode (Sample Data)

To test without scanning your Flox environment:

```bash
python3 src/producers/nix_sbom_producer.py --use-samples --interval 10
```

## Expected Output

You should see:

1. **Nix SBOM Producer**: Scanning Flox environment every 10 seconds
2. **Nix CVE Producer**: Publishing Nix CVEs every 7 seconds
3. **Matcher**: Performing high-confidence PURL-based matching
4. **Alert Consumer**: Displaying vulnerability alerts for your Flox packages
5. **Dashboard**: Real-time visualization at http://localhost:5001

Example alert for Nix package:
```
================================================================================
🚨 VULNERABILITY ALERT - CVE-2021-40330
================================================================================
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
  git_connect_git in connect.c allows repository path to contain newline
  character, resulting in unexpected cross-protocol requests

References:
  - https://nvd.nist.gov/vuln/detail/CVE-2021-40330
================================================================================
```

## Troubleshooting

### Kafka Connection Issues
```bash
# Check Docker containers
docker ps | grep broker

# Check Kafka is listening
lsof -i :9092

# Verify topics exist
docker exec broker kafka-topics --list --bootstrap-server localhost:9092

# Restart infrastructure if needed
docker compose down && ./scripts/start_infrastructure.sh
```

### Python Service Issues
```bash
# Check running services
pgrep -lf "python3 src/"

# Stop all services
pkill -f 'python3 src/'

# Restart services
./scripts/start_all.sh
```

### No Flox Packages Found
```bash
# Verify Flox is available
flox --version

# Check current environment
flox list

# If no environment active, the system will use sample Nix packages
```

### No Alerts Appearing
```bash
# Check matcher logs for errors
tail -50 logs/matcher.log | grep -i error

# Verify messages in topics
docker exec broker kafka-console-consumer --bootstrap-server localhost:9092 \
  --topic sboms --from-beginning --max-messages 1

# Restart matcher
pkill -f simple_matcher
source venv/bin/activate
python3 src/matchers/simple_matcher.py > logs/matcher.log 2>&1 &
```

## Validation

Run the automated test:
```bash
./test_nix_integration.sh
```

Or follow the complete validation guide: **[VALIDATION_GUIDE.md](VALIDATION_GUIDE.md)**

## Next Steps

After verifying the system works:
1. **Monitor your Flox environment**: The system is now scanning your packages automatically
2. **Add custom CVEs**: Edit `src/producers/nix_cve_producer.py`
3. **Integrate with NVD**: Fetch CVEs automatically from NVD API
4. **Enable SBOM signatures**: Add cryptographic verification
5. **Scale up**: Add more Kafka brokers and consumers for production

## Documentation

- **[README.md](README.md)** - System overview and quick start
- **[NIX_INTEGRATION.md](NIX_INTEGRATION.md)** - Technical details on Nix/Flox integration
- **[RUNNING.md](RUNNING.md)** - Current system status
- **[VALIDATION_GUIDE.md](VALIDATION_GUIDE.md)** - Testing procedures
