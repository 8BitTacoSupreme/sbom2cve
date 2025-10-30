# macOS Local Testing Guide

Quick guide for testing SBOM2CVE MVP on macOS without Kubernetes.

---

## Prerequisites

```bash
# Ensure you're on the MVP branch
git checkout future-state-mvp

# Activate Flox environment
flox activate
```

---

## Option 1: Standalone Component Testing (Recommended for macOS)

### Test PURL Mapper

```bash
python3 src/flink/functions/purl_mapper.py
```

**Expected Output**:
```
=== PURL Mapper Test Examples ===

Example 1: PyPI package (Flask)
  Input:  pkg:pypi/flask@2.0.0
  Output:
    → pkg:nix/nixpkgs/python312Packages.flask (confidence: 0.95)
    → pkg:nix/nixpkgs/python311Packages.flask (confidence: 0.95)
    → pkg:nix/nixpkgs/python310Packages.flask (confidence: 0.95)
    → pkg:nix/nixpkgs/python3Packages.flask (confidence: 0.9)
```

### Test Risk Scorer

```bash
python3 src/matchers/risk_scorer.py
```

**Expected Output**:
```
=== Risk Score Calculator Test Scenarios ===

Scenario 1: Worst Case (Critical CVE in Production)
  CVSS: 9.8, KEV: True, Env: prod, Depth: 0
  → Risk Score: 99/100 (P0)
  → Breakdown: {'cvss': 25, 'exploit': 25, 'depth': 15, 'environment': 15, ...}
```

### Run Unit Tests

```bash
# Run all tests
python3 -m pytest tests/unit/ -v

# Run specific test suites
python3 -m pytest tests/unit/test_purl_mapper.py -v     # 25 tests
python3 -m pytest tests/unit/test_risk_scorer.py -v     # 26 tests

# Run with coverage
python3 -m pytest tests/unit/ -v --cov=src
```

**Expected**: `51 passed in ~0.15s ✅`

---

## Option 2: VEX API Dev Mode (No Kafka Required)

### Start VEX API

```bash
# Start in dev mode (Kafka optional)
python3 src/api/vex_api.py --dev --port 8080
```

**Output**:
```
🚀 Starting VEX API on 0.0.0.0:8080
   VEX Topic: vex-statements
   Dev Mode: True (Kafka producer offline)
 * Running on http://0.0.0.0:8080
```

### Test VEX API (New Terminal)

```bash
# Health check
curl http://localhost:8080/health
# Response: {"status":"healthy","service":"vex-api","timestamp":"..."}

# Get VEX schema
curl http://localhost:8080/api/v1/vex/schema | jq

# Submit VEX statement
curl -X POST http://localhost:8080/api/v1/vex \
  -H "Content-Type: application/json" \
  -d '{
    "org_id": "test_org",
    "cve_id": "CVE-2024-1234",
    "product_purl": "pkg:nix/nixpkgs/openssl@3.0.7",
    "status": "not_affected",
    "justification": "vulnerable_code_not_in_execute_path",
    "impact_statement": "TLS 1.0 disabled in our configuration"
  }'

# Response: {"status":"accepted","vex_id":"test_org:CVE-2024-1234:pkg:nix/nixpkgs/openssl@3.0.7",...}
```

---

## Option 3: Docker Compose Kafka (Optional)

For testing Kafka integration on macOS:

### 1. Create Docker Compose Config

```bash
cat > docker-compose-test.yaml << 'EOF'
version: '3.8'
services:
  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000
    ports:
      - "2181:2181"

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
EOF
```

### 2. Start Kafka

```bash
# Start containers
docker-compose -f docker-compose-test.yaml up -d

# Wait for Kafka to be ready (30 seconds)
sleep 30

# Check status
docker-compose -f docker-compose-test.yaml ps
```

### 3. Test KEV Producer

```bash
# Fetch CISA KEV catalog and publish to Kafka
python3 src/producers/kev_producer.py --once --bootstrap-servers localhost:9092
```

**Expected Output**:
```
📥 Fetching KEV catalog from https://www.cisa.gov/...
✅ Fetched KEV catalog v2025.10.30
   Released: 2025-10-30T18:39:31.8373Z
   Vulnerabilities: 1451 CVEs
✅ Published 1451 KEV records to kev-feed
```

### 4. Test VEX API with Kafka

```bash
# Start VEX API connected to Kafka
python3 src/api/vex_api.py --bootstrap-servers localhost:9092 --port 8080

# Submit VEX (will publish to Kafka)
curl -X POST http://localhost:8080/api/v1/vex \
  -H "Content-Type: application/json" \
  -d '{
    "org_id": "test_org",
    "cve_id": "CVE-2024-1234",
    "product_purl": "pkg:nix/nixpkgs/openssl@3.0.7",
    "status": "not_affected"
  }'
```

### 5. Verify Kafka Messages

```bash
# List topics
docker exec -it $(docker ps -qf "name=kafka") kafka-topics \
  --list --bootstrap-server localhost:9092

# Expected topics: kev-feed, vex-statements

# Consume KEV messages
docker exec -it $(docker ps -qf "name=kafka") kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic kev-feed \
  --from-beginning \
  --max-messages 5

# Consume VEX messages
docker exec -it $(docker ps -qf "name=kafka") kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic vex-statements \
  --from-beginning \
  --max-messages 5
```

### 6. Stop Kafka

```bash
docker-compose -f docker-compose-test.yaml down
```

---

## Option 4: Integration Test Example

Create a test script combining components:

```bash
cat > test_integration.py << 'EOF'
#!/usr/bin/env python3
"""
Integration test: PURL Mapper + Risk Scorer
"""

import sys
sys.path.insert(0, 'src/flink/functions')
sys.path.insert(0, 'src/matchers')

from purl_mapper import PURLMapper
from risk_scorer import RiskScoreCalculator, AlertSignals
import yaml

# Load PURL mapping rules
with open('config/purl-mapping/rules.yaml', 'r') as f:
    rules = yaml.safe_load(f)

purl_mapper = PURLMapper(rules)
risk_calculator = RiskScoreCalculator()

print("=" * 80)
print("Integration Test: CVE → PURL Mapping → Risk Scoring")
print("=" * 80)

# Step 1: Map upstream CVE to Nix PURLs
upstream_cve_purl = "pkg:pypi/flask@2.0.0"
print(f"\n1. Upstream CVE PURL: {upstream_cve_purl}")

mappings = purl_mapper.map_purl(upstream_cve_purl)
print(f"   Mapped to {len(mappings)} Nix PURLs:")
for mapping in mappings[:3]:
    print(f"   → {mapping['purl']} (confidence: {mapping['confidence']})")

# Step 2: Calculate risk scores
print(f"\n2. Risk Scoring Scenarios:\n")

scenarios = [
    ("Production + Direct Dependency", AlertSignals(
        cvss_score=7.5, kev_listed=False, epss_score=0.3,
        exploit_available=True, dependency_depth=0,
        environment_tag='prod', vex_reachable=None
    )),
    ("Development + Transitive", AlertSignals(
        cvss_score=7.5, kev_listed=False, epss_score=0.3,
        exploit_available=True, dependency_depth=3,
        environment_tag='dev', vex_reachable=None
    )),
    ("Production + VEX Not Affected", AlertSignals(
        cvss_score=7.5, kev_listed=False, epss_score=0.3,
        exploit_available=True, dependency_depth=0,
        environment_tag='prod', vex_status='not_affected'
    ))
]

for name, signals in scenarios:
    result = risk_calculator.calculate(signals)
    print(f"   {name}:")
    print(f"   → Risk Score: {result.risk_score}/100 ({result.priority})")
    print(f"   → Breakdown: {result.breakdown}")
    print()

print("=" * 80)
print("✅ Integration test complete!")
print("=" * 80)
EOF

python3 test_integration.py
```

---

## Troubleshooting

### Python Import Errors

```bash
# Make sure you're in Flox environment
flox activate

# If still missing packages:
pip install --break-system-packages pyyaml packageurl-python flask requests pytest
```

### Port Already in Use

```bash
# Check what's using port 8080
lsof -i :8080

# Kill the process
kill -9 <PID>

# Or use a different port
python3 src/api/vex_api.py --dev --port 8081
```

### Docker Not Running

```bash
# Check Docker status
docker ps

# Start Docker Desktop on macOS
open -a Docker
```

---

## Recommended Testing Flow for macOS

```bash
# 1. Ensure correct environment
git checkout future-state-mvp
flox activate

# 2. Run unit tests (fastest validation)
python3 -m pytest tests/unit/ -v
# Expected: 51 passed ✅

# 3. Test PURL mapper
python3 src/flink/functions/purl_mapper.py

# 4. Test risk scorer
python3 src/matchers/risk_scorer.py

# 5. Start VEX API in dev mode
python3 src/api/vex_api.py --dev &
VEX_PID=$!

# 6. Test VEX API
sleep 2
curl http://localhost:8080/health
curl http://localhost:8080/api/v1/vex/schema | jq .version

# 7. Stop VEX API
kill $VEX_PID

# 8. (Optional) Docker Compose Kafka testing
docker-compose -f docker-compose-test.yaml up -d
python3 src/producers/kev_producer.py --once
docker-compose -f docker-compose-test.yaml down

echo "✅ All macOS local tests complete!"
```

---

## For K8s Testing (Requires Linux VM)

If you need to test K8s deployment on macOS:

### Option A: Use Docker Desktop Kubernetes

```bash
# Enable Kubernetes in Docker Desktop settings
# Then run:
./scripts/k8s-dev-setup.sh
```

### Option B: Use Multipass VM

```bash
# Install Multipass
brew install --cask multipass

# Create Ubuntu VM
multipass launch --name k3s-dev --cpus 4 --memory 8G --disk 50G

# Shell into VM
multipass shell k3s-dev

# Run setup inside VM
git clone https://github.com/8BitTacoSupreme/sbom2cve.git
cd sbom2cve
git checkout future-state-mvp
./scripts/k8s-dev-setup.sh
```

### Option C: Use Colima

```bash
# Install Colima (Docker Desktop alternative)
brew install colima

# Start with Kubernetes
colima start --cpu 4 --memory 8 --kubernetes

# Run setup
./scripts/k8s-dev-setup.sh
```

---

## Summary

**For macOS local testing, use Option 1 (Standalone) or Option 2 (VEX API Dev Mode).**

K3s setup script (`./scripts/k8s-dev-setup.sh`) requires Linux and is designed for:
- Linux workstations
- CI/CD environments
- Production deployment prep
- Linux VMs (Multipass, Colima, etc.)

**Most effective macOS workflow**:
1. ✅ Run unit tests (`pytest`)
2. ✅ Test components standalone (PURL mapper, risk scorer)
3. ✅ Test VEX API in dev mode (no Kafka)
4. ⏭️ (Optional) Docker Compose for Kafka integration testing

---

**Last Updated**: 2025-10-30
**Platform**: macOS
**Python**: 3.12+

🤖 Generated with [Claude Code](https://claude.com/claude-code)
