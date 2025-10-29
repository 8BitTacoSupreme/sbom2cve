# Flox Quick Start Guide

## 🎯 Get Started in 2 Commands

```bash
flox activate
./scripts/demo_start.sh
```

That's it! No Docker, no pip, no brew, no manual setup. Everything is managed by Flox.

---

## 📦 What You Get

When you `flox activate`, you automatically get:

✅ **Python 3.12** with all required packages:
- kafka-python (Kafka client)
- packaging (semantic versioning)
- flask (web dashboard)
- packageurl-python (PURL parsing)

✅ **Apache Kafka** (KRaft mode - no Zookeeper!)
- Ready to run natively
- No Docker containers required

✅ **All scripts and configuration**
- Auto-initialized on first run
- Kafka configured and ready

✅ **Clean environment**
- No conflicts with system packages
- Reproducible across machines

---

## 🚀 Quick Start

### First Time Setup

```bash
# Enter the Flox environment
flox activate

# You'll see a welcome message with instructions

# Initialize Kafka (automatic on first demo_start.sh run)
./scripts/kafka_init.sh

# Start the complete demo
./scripts/demo_start.sh
```

### Subsequent Runs

```bash
# Enter environment
flox activate

# Start demo
./scripts/demo_start.sh

# Open dashboard
open http://localhost:5001
```

### Stop the Demo

```bash
./scripts/demo_stop.sh
```

---

## 🏗️ Architecture (Pure Flox Stack)

```
┌─────────────────────────────────────────────┐
│  Flox Environment                           │
│  ┌───────────────────────────────────────┐  │
│  │  Python 3.12 + Packages (via Flox)   │  │
│  │  - kafka-python                       │  │
│  │  - packaging                          │  │
│  │  - flask                              │  │
│  │  - packageurl-python                  │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  ┌───────────────────────────────────────┐  │
│  │  Apache Kafka (via Flox)              │  │
│  │  - KRaft mode (no Zookeeper)          │  │
│  │  - Native binary execution            │  │
│  │  - Topics: sboms, cves, alerts        │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  ┌───────────────────────────────────────┐  │
│  │  Application Services                 │  │
│  │  - Nix SBOM Producer (scans Flox)     │  │
│  │  - Nix CVE Producer                   │  │
│  │  - PURL Matcher                       │  │
│  │  - Alert Consumer                     │  │
│  │  - Dashboard (Flask)                  │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

**Key Point**: Everything runs natively via Flox. No containers, no images, no Docker Desktop required!

---

## 📝 What's Running

When you start the demo:

1. **Kafka Broker** (localhost:9092)
   - Native Kafka process managed by Flox
   - KRaft mode (modern, no Zookeeper)
   - 3 topics: sboms, cves, alerts

2. **Nix SBOM Producer** (Python)
   - Scans your Flox environment via `flox list`
   - Generates SPDX 2.3 SBOMs every 10 seconds
   - PURLs: `pkg:nix/nixpkgs/{package}@{version}`

3. **Nix CVE Producer** (Python)
   - Publishes known Nix CVEs every 7 seconds
   - Curated database of real vulnerabilities

4. **PURL Matcher** (Python)
   - High-confidence matching (95%)
   - Ecosystem isolation (no false positives)
   - Semantic version range checking

5. **Alert Consumer** (Python)
   - Formatted vulnerability alerts
   - Real-time display in logs

6. **Dashboard** (Flask)
   - Web UI at http://localhost:5001
   - Real-time message counts
   - Vulnerability severity distribution

---

## 🔍 Monitoring

### View Logs

```bash
# All logs
tail -f logs/*.log

# Specific services
tail -f logs/kafka.log          # Kafka broker
tail -f logs/matcher.log        # Vulnerability matching
tail -f logs/alert_consumer.log # Formatted alerts
tail -f logs/sbom_producer.log  # SBOM generation
tail -f logs/cve_producer.log   # CVE publishing
tail -f logs/dashboard.log      # Web dashboard
```

### Dashboard

Open http://localhost:5001 to see:
- Real-time message counts
- Severity distribution
- Recent alerts
- System status

### Kafka Topics

```bash
# List topics
$KAFKA_HOME/bin/kafka-topics.sh --list --bootstrap-server localhost:9092

# Consume messages (from beginning)
$KAFKA_HOME/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic alerts --from-beginning
```

---

## 🛠️ Manual Operations

If you want more control, run components individually:

### Start Kafka Only

```bash
./scripts/kafka_start.sh
```

### Start Python Services Only

```bash
./scripts/start_all.sh
```

### Stop Individual Components

```bash
# Stop Python services
pkill -f 'python3 src/'

# Stop Kafka
./scripts/kafka_stop.sh
```

---

## 📚 Project Structure

```
sbom2cve/
├── .flox/
│   └── env/manifest.toml       # All dependencies defined here
├── config/
│   └── kafka/
│       └── kraft-server.properties  # Kafka configuration
├── scripts/
│   ├── kafka_init.sh           # Initialize Kafka (first time)
│   ├── kafka_start.sh          # Start Kafka
│   ├── kafka_stop.sh           # Stop Kafka
│   ├── demo_start.sh           # ⭐ Start everything
│   ├── demo_stop.sh            # Stop everything
│   └── start_all.sh            # Start Python services
├── src/
│   ├── producers/
│   │   ├── nix_sbom_producer.py
│   │   └── nix_cve_producer.py
│   ├── matchers/
│   │   └── simple_matcher.py
│   ├── consumers/
│   │   └── alert_consumer.py
│   └── dashboard/
│       └── dashboard.py
├── data/
│   └── kafka/                  # Kafka data (auto-created)
├── logs/                       # Application logs
└── README.md                   # Main documentation
```

---

## 🐛 Troubleshooting

### Kafka won't start

```bash
# Check if already running
pgrep -f "kafka.Kafka"

# View logs
tail -50 logs/kafka.log

# Re-initialize (will wipe data)
rm -rf data/kafka
./scripts/kafka_init.sh
./scripts/kafka_start.sh
```

### Python import errors

```bash
# Verify you're in Flox environment
echo $FLOX_ENV  # Should show path

# If empty, activate again
flox activate

# Verify packages
flox list | grep python
```

### Port already in use

```bash
# Check what's using port 9092 (Kafka)
lsof -i :9092

# Check what's using port 5001 (Dashboard)
lsof -i :5001

# Kill conflicting processes
kill -9 <PID>
```

### Dashboard not showing data

```bash
# Check if services are running
pgrep -f "python3 src/"

# Restart services
./scripts/demo_stop.sh
./scripts/demo_start.sh

# Verify Kafka topics have data
$KAFKA_HOME/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic sboms --from-beginning --max-messages 1
```

---

## 🎓 Learn More

- **Main Documentation**: [README.md](README.md)
- **Floxification Plan**: [FLOXIFICATION_PLAN.md](FLOXIFICATION_PLAN.md)
- **Nix Integration**: [NIX_INTEGRATION.md](NIX_INTEGRATION.md)
- **Validation Guide**: [VALIDATION_GUIDE.md](VALIDATION_GUIDE.md)
- **System Status**: [RUNNING.md](RUNNING.md)
- **Setup Guide**: [SETUP.md](SETUP.md)

---

## 🎯 Why Flox?

### Before Flox
```bash
# Install Docker Desktop
brew install docker

# Start Docker Desktop and wait...
open -a Docker

# Install Python deps
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start infrastructure
docker compose up -d

# Wait for containers...
# Start services
./scripts/start_all.sh
```

### With Flox
```bash
flox activate
./scripts/demo_start.sh
```

**Benefits**:
- ✅ No Docker required (flatter stack)
- ✅ No virtual environments (venv)
- ✅ No pip install
- ✅ Reproducible across machines
- ✅ Faster startup
- ✅ Less resource usage
- ✅ Everything declarative in manifest.toml

---

## 🚀 Next Steps

1. **Explore the codebase**: Check out `src/` for Python services
2. **Customize CVEs**: Edit `src/producers/nix_cve_producer.py`
3. **Add packages**: Scan your own Flox environment
4. **Integrate with NVD**: Fetch CVEs from National Vulnerability Database
5. **Publish to FloxHub**: Share your environment with others

---

## 🤝 Contributing

When adding dependencies:

```bash
# Search for packages
flox search <package-name>

# Add to environment
flox install <package>

# Verify it works
flox list

# Dependencies are automatically added to manifest.toml
```

Never use `pip install`, `brew install`, or other package managers!

---

## 📞 Support

- **Issues**: Check logs in `logs/` directory
- **Questions**: See [VALIDATION_GUIDE.md](VALIDATION_GUIDE.md)
- **Documentation**: [README.md](README.md)
- **Architecture**: [FLOXIFICATION_PLAN.md](FLOXIFICATION_PLAN.md)

---

**Happy vulnerability hunting! 🎯**
