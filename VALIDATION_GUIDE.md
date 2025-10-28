# Nix/Flox Integration Validation Guide

## Quick Test (2 minutes)

Run the automated test script:

```bash
./test_nix_integration.sh
```

**Expected Output:**
```
✅ Nix SBOM generation works
✅ Nix CVE database loaded (17 CVEs)
✅ PURL matching logic validated (4/4 tests passed)
✅ Messages sent to Kafka
```

## Manual Validation Steps

### 1. Verify Infrastructure is Running

```bash
# Check Docker containers
docker ps

# Should show:
# - broker (Kafka)
# - schema-registry
# - flink-jobmanager
# - flink-taskmanager
```

### 2. Verify Python Services are Running

```bash
pgrep -lf "src/(producers|matchers|consumers|dashboard)"

# Should show processes for:
# - sbom_producer.py
# - cve_producer.py
# - simple_matcher.py
# - alert_consumer.py
# - dashboard.py
```

### 3. Test Nix SBOM Generation

```bash
source venv/bin/activate

python3 << 'EOF'
from src.producers.nix_sbom_producer import NixSBOMProducer

producer = NixSBOMProducer()
packages = producer.get_sample_nix_packages()
sbom = producer.generate_sbom('manual-test', packages)

print(f"Generated SBOM with {len(sbom['packages'])} packages:")
for pkg in sbom['packages']:
    purl = pkg['externalRefs'][0]['referenceLocator']
    print(f"  {pkg['name']:15} {pkg['versionInfo']:10} {purl}")
EOF
```

**Expected Output:**
```
Generated SBOM with 6 packages:
  openssl         1.1.1k     pkg:nix/nixpkgs/openssl@1.1.1k
  curl            7.79.1     pkg:nix/nixpkgs/curl@7.79.1
  git             2.33.0     pkg:nix/nixpkgs/git@2.33.0
  nginx           1.20.1     pkg:nix/nixpkgs/nginx@1.20.1
  python3         3.9.7      pkg:nix/nixpkgs/python3@3.9.7
  nodejs          16.13.0    pkg:nix/nixpkgs/nodejs@16.13.0
```

### 4. Test PURL Matching

```bash
python3 << 'EOF'
from src.matchers.simple_matcher import PURLMatcher

# Test 1: Nix packages should match
sbom_purl = "pkg:nix/nixpkgs/curl@7.79.1"
cve_purl = "pkg:nix/nixpkgs/curl"

sbom_norm = PURLMatcher.normalize_purl_for_comparison(sbom_purl)
cve_norm = PURLMatcher.normalize_purl_for_comparison(cve_purl)

print(f"Test 1: Nix curl matching")
print(f"  SBOM: {sbom_norm}")
print(f"  CVE:  {cve_norm}")
print(f"  Match: {sbom_norm == cve_norm} ✅\n")

# Test 2: Cross-ecosystem should NOT match
maven_purl = "pkg:maven/org.apache/curl@7.79.1"
maven_norm = PURLMatcher.normalize_purl_for_comparison(maven_purl)

print(f"Test 2: Maven vs Nix (should NOT match)")
print(f"  Maven: {maven_norm}")
print(f"  Nix:   {cve_norm}")
print(f"  Match: {maven_norm == cve_norm} ❌\n")

# Test 3: Version range matching
matches, confidence = PURLMatcher.matches_version_range("7.79.1", ">=7.0.0 <7.80.0")
print(f"Test 3: Version range")
print(f"  Version 7.79.1 in range [7.0.0, 7.80.0)")
print(f"  Matches: {matches}, Confidence: {confidence} ✅")
EOF
```

**Expected Output:**
```
Test 1: Nix curl matching
  SBOM: nix:nixpkgs:curl
  CVE:  nix:nixpkgs:curl
  Match: True ✅

Test 2: Maven vs Nix (should NOT match)
  Maven: maven:org.apache:curl
  Nix:   nix:nixpkgs:curl
  Match: False ❌

Test 3: Version range
  Version 7.79.1 in range [7.0.0, 7.80.0)
  Matches: True, Confidence: 0.95 ✅
```

### 5. Test End-to-End Message Flow

```bash
# Send test messages
python3 << 'EOF'
from src.producers.nix_sbom_producer import NixSBOMProducer
from src.producers.nix_cve_producer import NixCVEProducer
import time

print("Sending Nix SBOM...")
sbom_prod = NixSBOMProducer()
packages = sbom_prod.get_sample_nix_packages()
sbom = sbom_prod.generate_sbom('e2e-test', packages)
sbom_prod.send_sbom(sbom, 'e2e-test')

time.sleep(2)

print("Sending Nix CVEs...")
cve_prod = NixCVEProducer()
for cve in cve_prod.KNOWN_NIX_CVES[2:5]:  # curl, git, nginx
    test_cve = cve.copy()
    test_cve['published'] = '2025-10-25T23:30:00Z'
    cve_prod.send_cve(test_cve)
    print(f"  Sent {cve['cve_id']}")

print("\nWaiting for matcher...")
time.sleep(3)
print("Done!")
EOF

# Check for matches
echo ""
echo "Checking for matches in logs..."
grep -E "CVE-2021-22946|CVE-2021-40330|CVE-2021-23017" logs/matcher.log | tail -10
```

**Expected Output:**
```
Sending Nix SBOM...
Sent SBOM for e2e-test to sboms:0 @ offset XXX

Sending Nix CVEs...
  Sent CVE-2021-22946
  Sent CVE-2021-40330
  Sent CVE-2021-23017

Checking for matches in logs...
✅ Alert sent: CVE-2021-22946 affects curl
✅ Alert sent: CVE-2021-40330 affects git
✅ Alert sent: CVE-2021-23017 affects nginx
```

### 6. Check Dashboard

Open the dashboard in your browser:
```bash
open http://localhost:5001
```

**What to verify:**
- Message counts are incrementing
- Severity distribution shows CRITICAL, HIGH, MEDIUM
- Recent messages show both Maven/NPM and Nix packages

### 7. View Real-Time Logs

```bash
# Watch matcher activity
tail -f logs/matcher.log | grep -E "curl|git|openssl|CVE-2021"

# Watch alerts
tail -f logs/alert_consumer.log | grep -E "curl|git|nginx"
```

## Validation Checklist

- [ ] Test script runs successfully (`./test_nix_integration.sh`)
- [ ] Nix SBOM generation produces 6 packages
- [ ] PURL matching passes all 4 tests
- [ ] Messages appear in Kafka topics
- [ ] Matcher logs show Nix CVE matches
- [ ] Dashboard shows incrementing message counts
- [ ] Alert consumer displays Nix vulnerabilities
- [ ] Cross-ecosystem isolation works (Maven ≠ Nix)

## Expected Matches

These CVE/package combinations should **always match**:

| CVE ID | Package | Version | Should Match? |
|--------|---------|---------|---------------|
| CVE-2021-22946 | curl | 7.79.1 | ✅ YES (7.79.1 in [7.0.0, 7.80.0)) |
| CVE-2021-40330 | git | 2.33.0 | ✅ YES (2.33.0 in [2.0.0, 2.33.1)) |
| CVE-2021-23017 | nginx | 1.20.1 | ✅ YES (1.20.1 in [0.6.18, 1.21.0)) |
| CVE-2021-29921 | python3 | 3.9.7 | ✅ YES (3.9.7 < 3.9.5 is FALSE) ❌ |
| CVE-2021-44531 | nodejs | 16.13.0 | ✅ YES (16.13.0 in [16.0.0, 16.13.2)) |

These combinations should **NOT match** (cross-ecosystem):

| SBOM Package | CVE Package | Should Match? |
|--------------|-------------|---------------|
| pkg:maven/openssl@1.1.1 | pkg:nix/nixpkgs/openssl | ❌ NO |
| pkg:npm/curl@7.79.1 | pkg:nix/nixpkgs/curl | ❌ NO |
| pkg:pypi/requests@2.27.1 | pkg:nix/nixpkgs/python3 | ❌ NO |

## Troubleshooting

### No matches appearing

```bash
# Check if matcher is running
pgrep -f simple_matcher

# Check matcher logs for errors
tail -50 logs/matcher.log | grep -i error

# Restart matcher if needed
pkill -f simple_matcher
source venv/bin/activate
python3 src/matchers/simple_matcher.py > logs/matcher.log 2>&1 &
```

### Kafka connection errors

```bash
# Check broker status
docker ps | grep broker

# Restart infrastructure
docker compose down
./scripts/start_infrastructure.sh
```

### Messages not flowing

```bash
# Check topic offsets
docker exec broker kafka-consumer-groups --bootstrap-server localhost:9092 --group matcher-sbom --describe
docker exec broker kafka-consumer-groups --bootstrap-server localhost:9092 --group matcher-cve --describe
```

## Success Criteria

✅ **Integration is working if:**
1. Test script shows all green checkmarks
2. Matcher logs show `✅ Alert sent: CVE-2021-22946 affects curl`
3. Dashboard shows messages flowing
4. Cross-ecosystem packages don't produce false positives
5. Version range matching works correctly

## Performance Metrics

With the current setup, you should see:
- **SBOM Processing**: ~1-2 SBOMs/second
- **CVE Processing**: ~1-2 CVEs/second
- **Alert Generation**: <100ms latency from message to alert
- **Dashboard Updates**: Every 2-3 seconds

## Next Steps After Validation

1. **Integrate with real Flox environment**:
   ```bash
   python3 src/producers/nix_sbom_producer.py  # Uses flox list
   ```

2. **Add more CVEs**: Edit `src/producers/nix_cve_producer.py`

3. **Connect to NVD**: Fetch CVEs automatically from NVD database

4. **Add signature verification**: Validate cryptographic attestations

5. **Deploy to production**: Scale Kafka brokers and consumers
