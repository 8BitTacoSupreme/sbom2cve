# Setup Guide for SBOM-CVE Matcher

## Prerequisites

This project uses **Flox** for environment management. The following are already installed via Flox:
- kafka-python (Python Kafka client)
- packaging (Python version parsing)
- Python 3.12
- OpenJDK

## Kafka Setup Options

You have several options to run Kafka:

### Option 1: Docker (Recommended for Testing)

**Prerequisites**: Docker Desktop must be running

```bash
# Make sure Docker Desktop is running, then:
chmod +x scripts/start_kafka_docker.sh
./scripts/start_kafka_docker.sh
```

This will:
- Start Zookeeper and Kafka in Docker containers
- Create topics: `sboms`, `cves`, `alerts`
- Kafka will be available at `localhost:9092`

**To stop**:
```bash
docker stop kafka zookeeper
```

### Option 2: Manual Kafka Installation via Flox

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

### Option 3: Homebrew (macOS)

If you prefer to use Homebrew:

```bash
brew install kafka
brew services start zookeeper
brew services start kafka

# Create topics
kafka-topics --create --topic sboms --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
kafka-topics --create --topic cves --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
kafka-topics --create --topic alerts --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
```

## Running the Application

Once Kafka is running, you need **4 terminal windows**:

### Terminal 1: SBOM Producer
```bash
python3 src/producers/sbom_producer.py
```

### Terminal 2: CVE Producer
```bash
python3 src/producers/cve_producer.py
```

### Terminal 3: Matcher (Python-based, no Flink needed)
```bash
python3 src/matchers/simple_matcher.py
```

### Terminal 4: Alert Consumer
```bash
python3 src/consumers/alert_consumer.py
```

## Expected Output

You should see:

1. **SBOM Producer**: Generating and sending SBOMs every 5 seconds
2. **CVE Producer**: Generating and sending CVEs every 3 seconds
3. **Matcher**: Receiving SBOMs and CVEs, performing matching
4. **Alert Consumer**: Displaying formatted vulnerability alerts when matches are found

Example alert:
```
================================================================================
🚨 VULNERABILITY ALERT - CVE-2021-44228
================================================================================
CVE ID:           CVE-2021-44228
Severity:         CRITICAL
CVSS Score:       10.0
Confidence:       95.0%
Match Method:     purl_version_range

Affected Package:
  Name:           log4j-core
  Version:        2.14.1
  PURL:           pkg:maven/org.apache.logging.log4j/log4j-core@2.14.1
================================================================================
```

## Troubleshooting

### Kafka Connection Issues
- Ensure Kafka is running: `docker ps` (if using Docker)
- Check Kafka is listening on port 9092: `netstat -an | grep 9092`
- Verify topics exist: `docker exec kafka kafka-topics --list --bootstrap-server localhost:9092`

### Python Import Errors
- Verify packages are installed:
  ```bash
  python3 -c "import kafka; import packaging; print('OK')"
  ```
- If needed, check Flox packages:
  ```bash
  flox list | grep python
  ```

### No Alerts Appearing
- Check that all 4 components are running
- Verify the matcher is receiving messages (check its console output)
- Check Kafka topics have data:
  ```bash
  docker exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic sboms --from-beginning --max-messages 1
  ```

## Next Steps

After verifying the system works:
1. Modify CVEs in `src/producers/cve_producer.py` to add more vulnerabilities
2. Modify SBOM packages in `src/producers/sbom_producer.py` to test different scenarios
3. Adjust matching logic in `src/matchers/simple_matcher.py` for custom rules
4. Integrate with real CVE feeds (NVD, OSV, etc.)
