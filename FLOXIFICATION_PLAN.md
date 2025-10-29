# Floxification Plan: SBOM2CVE Vulnerability Matcher

## Goal
Enable end users to run:
```bash
flox pull <org>/sbom2cve
cd sbom2cve
flox activate
# System automatically starts, demo runs
```

## Current State Analysis

### ✅ Already Flox-Native
- Python 3.12 (via Flox: `python312`)
- Kafka client (via Flox: `python312Packages.kafka-python`)
- Version parsing (via Flox: `python312Packages.packaging`)
- Flask web framework (via Flox: `python312Packages.flask`)
- Apache Kafka binaries (via Flox: `apacheKafka`)
- Flink (via Flox: `flink`)

### ❌ External Dependencies (Need Migration)
1. **Python venv** - Currently using `venv/` with pip
2. **pip packages**:
   - `apache-flink==1.18.0` (PyFlink API) - NOT available in Flox
   - `packageurl-python==0.11.2` - ✅ AVAILABLE in Flox as `python312Packages.packageurl-python`
3. **Docker Desktop** - Used for Confluent Platform (Kafka, Schema Registry, Flink containers)

### 🤔 Infrastructure Decision Required
- **Current**: Docker Compose with Confluent images (5 containers)
- **Alternative**: k3s/minikube (better aligns with Flox philosophy)

---

## Phase 1: Eliminate Python venv + pip

### Current Problem
```bash
# User must manually run:
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Solution: Pure Flox Dependencies

#### Step 1.1: Migrate packageurl-python to Flox
- ✅ Available as `python312Packages.packageurl-python`
- Action: Add to `.flox/env/manifest.toml` `[install]` section

#### Step 1.2: Handle apache-flink (PyFlink)
**Problem**: PyFlink not available in nixpkgs
**Options**:
1. **Remove PyFlink dependency** (RECOMMENDED)
   - Current system uses Python matcher (`src/matchers/simple_matcher.py`)
   - `src/flink_jobs/sbom_cve_matcher.py` appears unused in default flow
   - PyFlink only needed if running actual Flink jobs (not Python scripts)

2. **Bundle PyFlink locally** (if needed)
   - Download wheel, vendor into project
   - Not ideal for Flox philosophy

**Recommendation**: Remove PyFlink dependency since system works without it

#### Step 1.3: Update manifest.toml
```toml
[install]
python312.pkg-path = "python312"
kafka-python.pkg-path = "python312Packages.kafka-python"
packaging.pkg-path = "python312Packages.packaging"
flask.pkg-path = "python312Packages.flask"
packageurl-python.pkg-path = "python312Packages.packageurl-python"  # NEW
apacheKafka.pkg-path = "apacheKafka"
flink.pkg-path = "flink"
openjdk.pkg-path = "openjdk"
```

#### Step 1.4: Remove venv references
- Delete `requirements.txt` (or document as legacy)
- Remove venv creation from documentation
- Update all scripts to not use `source venv/bin/activate`

---

## Phase 2: Infrastructure Choice - k3s vs Docker

### Philosophy Alignment
**Flox Goal**: Image-free, reproducible environments
**Docker**: Image-based containers (less aligned)
**k3s**: Lightweight k8s, can run native binaries (better aligned)

### Analysis

#### Option A: Keep Docker Compose (Pragmatic)
**Pros**:
- Already working
- Confluent images are well-tested
- Quick to start
- User-friendly for demos

**Cons**:
- Requires Docker Desktop installation
- Image-based (not Flox philosophy)
- Not managed by Flox

**If choosing this**: Accept Docker as external dependency, document clearly

#### Option B: Migrate to k3s (Philosophically Aligned)
**Pros**:
- ✅ k3s available in Flox: `flox install k3s`
- Aligns with Flox image-free philosophy
- Can run Kafka/Flink as k3s deployments
- More "production-like" architecture

**Cons**:
- More complex setup
- Requires k8s YAML manifests
- Slower startup than Docker Compose
- May require additional k8s tooling (kubectl, helm)

#### Option C: Hybrid Approach (RECOMMENDED)
**Use native Kafka from Flox + Lightweight k3s**
- Kafka already available in Flox (`apacheKafka`)
- Run Kafka natively (no containers)
- Use k3s only if needed for scaling/isolation
- Simplest path to pure Flox

**Pros**:
- Everything managed by Flox
- No external dependencies
- Fast startup
- True to Flox philosophy

**Cons**:
- More configuration work
- Lose Confluent's pre-configured setup

### Recommendation: **Option C - Native Kafka via Flox**

---

## Phase 3: Pure Flox Infrastructure Setup

### Step 3.1: Native Kafka Configuration
Replace Docker Compose with Flox-managed Kafka:

```bash
# All via Flox environment
$KAFKA_HOME/bin/kafka-server-start.sh config/kraft/server.properties
```

**Benefits**:
- No Docker required
- Managed by Flox
- Fast startup
- Reproducible across machines

### Step 3.2: Create Flox Hook Script
Add to `.flox/env/manifest.toml`:

```toml
[hook]
on-activate = '''
#!/bin/bash
echo "🚀 Setting up SBOM2CVE environment..."

# Create directories
mkdir -p logs data/kafka config/kafka

# Generate Kafka KRaft cluster ID if needed
if [ ! -f data/kafka/cluster.id ]; then
  CLUSTER_ID=$(kafka-storage random-uuid)
  echo "$CLUSTER_ID" > data/kafka/cluster.id
  echo "Generated Kafka cluster ID: $CLUSTER_ID"
fi

# Initialize Kafka storage
CLUSTER_ID=$(cat data/kafka/cluster.id)
if [ ! -d data/kafka/logs ]; then
  kafka-storage format -t "$CLUSTER_ID" -c "$FLOX_ENV/libexec/kafka/config/kraft/server.properties"
fi

# Create Kafka config if needed
if [ ! -f config/kafka/server.properties ]; then
  cp "$KAFKA_HOME/config/kraft/server.properties" config/kafka/
  # Customize: set log dirs, ports, etc.
fi

echo "✅ Environment ready!"
echo ""
echo "To start the demo:"
echo "  ./scripts/demo_start.sh"
'''
```

### Step 3.3: Background Process Management
**Challenge**: How to manage multiple background processes (Kafka, producers, matcher, consumer, dashboard)?

**Options**:
1. **Simple script with `&`** - Current approach, works
2. **GNU Screen/tmux** - Split terminal panes
3. **Supervisor/systemd** - Process management (may not be Flox-friendly)
4. **Flox services** - Use Flox's process management (if available)

**Recommendation**: Enhanced script with process tracking

---

## Phase 4: Single-Command Demo Launcher

### Create `scripts/demo_start.sh`
```bash
#!/bin/bash
set -e

echo "🚀 Starting SBOM2CVE Demo (Nix/Flox Mode)"

# Start Kafka in background
echo "📦 Starting Kafka..."
kafka-server-start.sh config/kafka/server.properties > logs/kafka.log 2>&1 &
KAFKA_PID=$!

# Wait for Kafka
sleep 10

# Create topics
kafka-topics.sh --create --if-not-exists --topic sboms --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
kafka-topics.sh --create --if-not-exists --topic cves --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1
kafka-topics.sh --create --if-not-exists --topic alerts --bootstrap-server localhost:9092 --partitions 3 --replication-factor 1

# Start Python services
./scripts/start_all.sh

echo ""
echo "✅ Demo is running!"
echo ""
echo "📊 Dashboard: http://localhost:5001"
echo "📝 Logs: tail -f logs/*.log"
echo ""
echo "To stop: ./scripts/demo_stop.sh"
```

### Create `scripts/demo_stop.sh`
```bash
#!/bin/bash
echo "🛑 Stopping SBOM2CVE Demo..."

# Stop Python services
pkill -f 'python3 src/'

# Stop Kafka
pkill -f 'kafka-server-start'

echo "✅ Demo stopped"
```

---

## Phase 5: FloxHub Publishing

### Step 5.1: Prepare for Publishing
```bash
# Ensure environment is clean and reproducible
flox list  # Verify all dependencies

# Test on clean machine (if possible)
cd /tmp
git clone <repo>
cd sbom2cve
flox activate
./scripts/demo_start.sh
```

### Step 5.2: Publish to FloxHub
```bash
# Push environment to FloxHub
flox push <org>/sbom2cve

# Test pull
cd /tmp/test
flox pull <org>/sbom2cve
cd sbom2cve
flox activate
```

### Step 5.3: Document User Workflow
Update README.md:
```markdown
## Quick Start (Flox Users)

```bash
# Pull from FloxHub
flox pull <org>/sbom2cve
cd sbom2cve

# Activate environment (auto-configures everything)
flox activate

# Start demo
./scripts/demo_start.sh

# Open dashboard
open http://localhost:5001
```

All dependencies managed by Flox - no Docker, pip, or manual setup required!
```

---

## Phase 6: Fallback for Docker Users

### Keep Docker Option Available
Since some users may prefer Docker, maintain both paths:

```markdown
## Setup Options

### Option 1: Pure Flox (Recommended)
```bash
flox pull <org>/sbom2cve
cd sbom2cve
flox activate
./scripts/demo_start.sh
```

### Option 2: Docker + Flox (Legacy)
```bash
flox pull <org>/sbom2cve
cd sbom2cve
flox activate
./scripts/start_infrastructure.sh  # Docker Compose
./scripts/start_all.sh              # Python services
```

---

## Implementation Checklist

### Phase 1: Dependencies (Priority: HIGH)
- [ ] Add `python312Packages.packageurl-python` to manifest.toml
- [ ] Remove apache-flink from requirements.txt (or verify it's unused)
- [ ] Update manifest.toml with all Python packages
- [ ] Remove venv references from scripts
- [ ] Test: `flox activate` provides all needed Python packages

### Phase 2: Infrastructure Decision (Priority: HIGH)
- [ ] Decide: Native Kafka vs Docker vs k3s
- [ ] Document rationale in ARCHITECTURE.md
- [ ] Get user/team consensus

### Phase 3: Native Kafka (If Option C chosen) (Priority: MEDIUM)
- [ ] Create Kafka config in `config/kafka/`
- [ ] Add KRaft initialization to hook script
- [ ] Test Kafka startup from Flox environment
- [ ] Create wrapper scripts for kafka-server-start
- [ ] Verify topics can be created
- [ ] Test producer/consumer connectivity

### Phase 4: Demo Launcher (Priority: MEDIUM)
- [ ] Create `scripts/demo_start.sh`
- [ ] Create `scripts/demo_stop.sh`
- [ ] Add process monitoring/healthchecks
- [ ] Test on macOS
- [ ] Test on Linux (if applicable)

### Phase 5: Flox Hooks (Priority: MEDIUM)
- [ ] Enhance `on-activate` hook with full setup
- [ ] Add directory creation
- [ ] Add Kafka initialization
- [ ] Add config file generation
- [ ] Test hook execution

### Phase 6: Documentation (Priority: MEDIUM)
- [ ] Update README.md with Flox-first workflow
- [ ] Update SETUP.md for pure Flox setup
- [ ] Create FLOX_QUICKSTART.md
- [ ] Add troubleshooting for Flox-specific issues
- [ ] Document FloxHub pull workflow

### Phase 7: FloxHub Publishing (Priority: LOW)
- [ ] Clean up environment
- [ ] Test reproducibility
- [ ] Create FloxHub account (if needed)
- [ ] Publish environment: `flox push`
- [ ] Document pull instructions
- [ ] Share on FloxHub community

### Phase 8: Testing (Priority: HIGH)
- [ ] Test fresh `flox pull` on clean machine
- [ ] Verify `flox activate` auto-configures
- [ ] Verify `demo_start.sh` works without manual intervention
- [ ] Test Nix SBOM scanning
- [ ] Verify CVE matching
- [ ] Confirm alerts appear
- [ ] Check dashboard functionality

---

## Success Criteria

✅ **User can run the demo in 3 commands**:
```bash
flox pull <org>/sbom2cve
cd sbom2cve && flox activate
./scripts/demo_start.sh
```

✅ **No external package managers required**:
- No `pip install`
- No `npm install`
- No `brew install`
- No `apt install`
- Optional: Docker (document as legacy path)

✅ **Everything managed by Flox**:
- All Python dependencies from Flox
- Kafka from Flox (if native option chosen)
- All configuration auto-generated via hooks

✅ **Reproducible**:
- Same result on macOS, Linux
- Same result on different machines
- Locked dependency versions

✅ **FloxHub ready**:
- Can be published and pulled
- Works out-of-the-box after pull
- Clear documentation

---

## Timeline Estimate

- **Phase 1 (Dependencies)**: 2-3 hours
- **Phase 2 (Infrastructure Decision)**: 1 hour discussion + decision
- **Phase 3 (Native Kafka)**: 4-6 hours (if chosen)
- **Phase 4 (Demo Launcher)**: 2-3 hours
- **Phase 5 (Flox Hooks)**: 2-3 hours
- **Phase 6 (Documentation)**: 2-3 hours
- **Phase 7 (FloxHub)**: 1-2 hours
- **Phase 8 (Testing)**: 2-3 hours

**Total**: 16-24 hours of work

---

## Risks and Mitigations

### Risk 1: Kafka complexity without Docker
**Mitigation**:
- Provide pre-configured Kafka settings
- Extensive testing on multiple machines
- Keep Docker path as fallback

### Risk 2: Missing Python packages in Flox
**Mitigation**:
- Pre-verify all packages available
- Document workarounds if needed
- Consider local vendoring for unavailable packages

### Risk 3: Cross-platform compatibility
**Mitigation**:
- Test on macOS and Linux
- Use portable shell scripting
- Document platform-specific issues

### Risk 4: FloxHub publishing limitations
**Mitigation**:
- Review FloxHub docs thoroughly
- Ensure environment is portable
- Test pull/push workflow early

---

## Open Questions

1. **Kafka decision**: Should we go native Kafka via Flox or keep Docker?
   - Native = more work, better alignment
   - Docker = less work, pragmatic

2. **PyFlink usage**: Is `apache-flink` Python package actually used?
   - Need to verify if any code imports `pyflink`
   - Can we remove this dependency?

3. **FloxHub org**: What organization should host this?
   - Personal account?
   - Flox examples org?
   - Company org?

4. **Flink Docker containers**: Are they actually used?
   - System seems to work with Python matcher only
   - Can we remove Flink containers entirely?

---

## Next Steps

1. ✅ Create this plan document
2. 🔄 Get team/user feedback on infrastructure decision
3. ⏳ Start Phase 1: Migrate dependencies to Flox
4. ⏳ Implement chosen infrastructure approach
5. ⏳ Create demo launcher scripts
6. ⏳ Test end-to-end workflow
7. ⏳ Publish to FloxHub

---

## Resources

- [Flox Documentation](https://flox.dev/docs)
- [FloxHub](https://hub.flox.dev)
- [Flox Manifest Reference](https://flox.dev/docs/reference/command-reference/manifest.toml/)
- [Kafka KRaft Mode](https://kafka.apache.org/documentation/#kraft)
- [k3s Documentation](https://k3s.io)
