# Local Testing Guide

Complete guide for testing SBOM2CVE components locally without Kubernetes.

---

## Quick Start (No Infrastructure)

### 1. Test PURL Mapper

```bash
# Test PURL mapping rules
python3 src/flink/functions/purl_mapper.py
```

**Output**: Shows mappings for PyPI/npm/Go/Maven/Rust → Nix

### 2. Test Risk Scorer

```bash
# Test risk scoring scenarios
python3 src/matchers/risk_scorer.py
```

**Output**: 5 scenarios with risk scores and breakdowns

### 3. Run All Unit Tests

```bash
# Run all 51 tests
python3 -m pytest tests/unit/ -v

# Expected: 51 passed ✅
```

---

## Test VEX API (Dev Mode)

### Start VEX API (No Kafka Required)

```bash
# Start in dev mode (Kafka optional)
python3 src/api/vex_api.py --dev --port 8080

# Output:
# 🚀 Starting VEX API on 0.0.0.0:8080
#    VEX Topic: vex-statements
#    Dev Mode: True
```

### Test VEX API Endpoints

Open a new terminal and run:

```bash
# 1. Health check
curl http://localhost:8080/health

# Expected:
# {"status":"healthy","service":"vex-api","timestamp":"..."}

# 2. Get VEX schema
curl http://localhost:8080/api/v1/vex/schema | jq

# Expected: Complete schema with examples

# 3. Submit VEX statement
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

# Expected (dev mode):
# {
#   "status": "accepted",
#   "vex_id": "test_org:CVE-2024-1234:pkg:nix/nixpkgs/openssl@3.0.7",
#   "message": "VEX statement received (Kafka producer offline - dev mode)",
#   ...
# }
```

---

## Test with Local Kafka (Docker)

If you want to test Kafka integration without K8s:

### 1. Start Kafka with Docker Compose

Create `docker-compose-test.yaml`:

```yaml
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
```

```bash
# Start Kafka
docker-compose -f docker-compose-test.yaml up -d

# Wait for Kafka to be ready
sleep 10

# Check logs
docker-compose -f docker-compose-test.yaml logs kafka
```

### 2. Test KEV Producer

```bash
# Fetch KEV catalog and publish to local Kafka
python3 src/producers/kev_producer.py --once --bootstrap-servers localhost:9092

# Expected output:
# 📥 Fetching KEV catalog from https://www.cisa.gov/...
# ✅ Fetched KEV catalog v2025.10.29
#    Released: 2025-10-29T18:39:31.8373Z
#    Vulnerabilities: 1451 CVEs
# ✅ Published 1451 KEV records to kev-feed
```

### 3. Test VEX API with Kafka

```bash
# Start VEX API connected to local Kafka
python3 src/api/vex_api.py --bootstrap-servers localhost:9092 --port 8080

# Submit VEX statement (will publish to Kafka)
curl -X POST http://localhost:8080/api/v1/vex \
  -H "Content-Type: application/json" \
  -d '{
    "org_id": "test_org",
    "cve_id": "CVE-2024-1234",
    "product_purl": "pkg:nix/nixpkgs/openssl@3.0.7",
    "status": "not_affected"
  }'

# Expected:
# {"status":"accepted","vex_id":"...","message":"VEX statement will be processed within 5 seconds"}
```

### 4. Verify Messages in Kafka

```bash
# List topics
docker exec -it $(docker ps -qf "name=kafka") kafka-topics \
  --list --bootstrap-server localhost:9092

# Expected topics:
# kev-feed
# vex-statements

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

### 5. Stop Kafka

```bash
docker-compose -f docker-compose-test.yaml down
```

---

## Integration Test (PURL Mapper + Risk Scorer)

Create a test script to combine components:

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

# Simulate a CVE for Flask
print("=" * 80)
print("Integration Test: CVE → PURL Mapping → Risk Scoring")
print("=" * 80)

# Step 1: Map upstream CVE to Nix PURLs
upstream_cve_purl = "pkg:pypi/flask@2.0.0"
print(f"\n1. Upstream CVE PURL: {upstream_cve_purl}")

mappings = purl_mapper.map_purl(upstream_cve_purl)
print(f"   Mapped to {len(mappings)} Nix PURLs:")
for mapping in mappings[:3]:  # Show first 3
    print(f"   → {mapping['purl']} (confidence: {mapping['confidence']})")

# Step 2: Calculate risk score for each scenario
print(f"\n2. Risk Scoring Scenarios:\n")

scenarios = [
    ("Production + Direct Dependency", AlertSignals(
        cvss_score=7.5,
        kev_listed=False,
        epss_score=0.3,
        exploit_available=True,
        dependency_depth=0,
        environment_tag='prod',
        vex_reachable=None
    )),
    ("Development + Transitive", AlertSignals(
        cvss_score=7.5,
        kev_listed=False,
        epss_score=0.3,
        exploit_available=True,
        dependency_depth=3,
        environment_tag='dev',
        vex_reachable=None
    )),
    ("Production + VEX Not Affected", AlertSignals(
        cvss_score=7.5,
        kev_listed=False,
        epss_score=0.3,
        exploit_available=True,
        dependency_depth=0,
        environment_tag='prod',
        vex_status='not_affected'
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

**Expected Output:**
```
================================================================================
Integration Test: CVE → PURL Mapping → Risk Scoring
================================================================================

1. Upstream CVE PURL: pkg:pypi/flask@2.0.0
   Mapped to 4 Nix PURLs:
   → pkg:nix/nixpkgs/python312Packages.flask (confidence: 0.95)
   → pkg:nix/nixpkgs/python311Packages.flask (confidence: 0.95)
   → pkg:nix/nixpkgs/python310Packages.flask (confidence: 0.95)

2. Risk Scoring Scenarios:

   Production + Direct Dependency:
   → Risk Score: 64/100 (P2)
   → Breakdown: {'cvss': 18, 'exploit': 10, 'depth': 15, 'environment': 15, ...}

   Development + Transitive:
   → Risk Score: 38/100 (P3)
   → Breakdown: {'cvss': 18, 'exploit': 10, 'depth': 2, 'environment': 3, ...}

   Production + VEX Not Affected:
   → Risk Score: 0/100 (P4)
   → Breakdown: {'vex_override': 0}

================================================================================
✅ Integration test complete!
================================================================================
```

---

## Performance Testing

### Test PURL Mapper Performance

```bash
cat > test_performance.py << 'EOF'
#!/usr/bin/env python3
"""Performance test for PURL Mapper"""

import sys
import time
sys.path.insert(0, 'src/flink/functions')

from purl_mapper import PURLMapper
import yaml

# Load rules
with open('config/purl-mapping/rules.yaml', 'r') as f:
    rules = yaml.safe_load(f)

mapper = PURLMapper(rules)

# Test PURLs
test_purls = [
    "pkg:pypi/flask@2.0.0",
    "pkg:npm/express@4.18.0",
    "pkg:golang/golang.org/x/crypto@v0.0.0",
    "pkg:maven/org.apache.commons/commons-lang3@3.12.0",
    "pkg:cargo/tokio@1.28.0"
] * 200  # 1000 total mappings

print(f"Testing {len(test_purls)} PURL mappings...")

start = time.time()
for purl in test_purls:
    mappings = mapper.map_purl(purl)
elapsed = time.time() - start

print(f"✅ Completed {len(test_purls)} mappings in {elapsed:.2f}s")
print(f"   Throughput: {len(test_purls)/elapsed:.0f} mappings/sec")
print(f"   Average latency: {(elapsed/len(test_purls))*1000:.2f}ms")
EOF

python3 test_performance.py
```

**Expected Output:**
```
Testing 1000 PURL mappings...
✅ Completed 1000 mappings in 0.05s
   Throughput: 20000 mappings/sec
   Average latency: 0.05ms
```

---

## Troubleshooting

### Python Import Errors

```bash
# Install required packages
pip install --break-system-packages pyyaml packageurl-python flask requests pytest

# Or use Flox environment
flox activate
```

### Kafka Connection Errors (Docker Compose)

```bash
# Check if Kafka is running
docker ps | grep kafka

# Check Kafka logs
docker-compose -f docker-compose-test.yaml logs kafka

# Restart Kafka
docker-compose -f docker-compose-test.yaml restart kafka
```

### Port Already in Use

```bash
# Check what's using port 8080 (VEX API)
lsof -i :8080

# Kill the process
kill -9 <PID>

# Or use a different port
python3 src/api/vex_api.py --dev --port 8081
```

---

## Full Local Test Workflow

```bash
# 1. Run unit tests
python3 -m pytest tests/unit/ -v
# Expected: 51 passed ✅

# 2. Test PURL mapper
python3 src/flink/functions/purl_mapper.py

# 3. Test risk scorer
python3 src/matchers/risk_scorer.py

# 4. Start VEX API in dev mode
python3 src/api/vex_api.py --dev &
VEX_PID=$!

# 5. Test VEX API
sleep 2
curl http://localhost:8080/health
curl http://localhost:8080/api/v1/vex/schema | jq .version

# 6. Stop VEX API
kill $VEX_PID

# 7. (Optional) Start Docker Compose Kafka
docker-compose -f docker-compose-test.yaml up -d

# 8. Test KEV producer
python3 src/producers/kev_producer.py --once

# 9. Test VEX API with Kafka
python3 src/api/vex_api.py --bootstrap-servers localhost:9092 &
VEX_PID=$!

curl -X POST http://localhost:8080/api/v1/vex \
  -H "Content-Type: application/json" \
  -d '{"org_id":"test","cve_id":"CVE-2024-TEST","product_purl":"pkg:nix/test","status":"not_affected"}'

# 10. Cleanup
kill $VEX_PID
docker-compose -f docker-compose-test.yaml down

echo "✅ All local tests complete!"
```

---

## Next Steps

Once local testing is complete:

1. **K8s Local Testing**: Run `./scripts/k8s-dev-setup.sh`
2. **Production Testing**: Deploy to EKS/GKE/AKS (see [DEPLOYMENT.md](DEPLOYMENT.md))

---

**Last Updated**: 2025-10-30
**Tested On**: macOS, Python 3.12+

🤖 Generated with [Claude Code](https://claude.com/claude-code)
