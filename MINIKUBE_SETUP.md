# Minikube Setup for macOS (No Docker Desktop Required)

Complete guide for running SBOM2CVE MVP on Minikube with QEMU driver.

---

## Quick Start

```bash
# 1. Install prerequisites (if not already installed)
brew install minikube qemu kubectl helm

# 2. Run one-command setup
./scripts/minikube-setup.sh

# 3. Wait for completion (~5-10 minutes)
#    - Minikube starts (QEMU driver)
#    - Kafka cluster deploys (3 brokers + 3 Zookeeper)
#    - VEX API deploys (3 replicas with HPA)
```

---

## What Gets Installed

### Minikube Cluster
- **Driver**: QEMU (no Docker required)
- **CPUs**: 4 cores
- **Memory**: 8GB RAM
- **Disk**: 40GB
- **Kubernetes**: v1.28.0

### Components Deployed
- **Strimzi Kafka Operator**: Manages Kafka cluster
- **Kafka Cluster**: 3 brokers + 3 Zookeeper nodes
- **Kafka Topics**: 7 topics (purl-mapping-rules, cves-enriched, kev-feed, etc.)
- **VEX API**: Flask REST API (3-10 replicas with HPA)
- **Kafka Exporter**: Prometheus metrics exporter

---

## Prerequisites

### System Requirements
- **macOS** (Intel or Apple Silicon)
- **8GB+ RAM** available
- **50GB+ disk space**
- **Homebrew** installed

### Required Tools
```bash
brew install minikube qemu kubectl helm
```

---

## Step-by-Step Setup

### 1. Start Minikube

```bash
./scripts/minikube-setup.sh
```

**What it does**:
1. ✅ Checks prerequisites (minikube, kubectl, helm)
2. ✅ Starts Minikube with QEMU driver
3. ✅ Configures kubectl context
4. ✅ Creates `sbom2cve` namespace
5. ✅ Adds Helm repositories (Strimzi, Prometheus)
6. ✅ Installs Strimzi Kafka Operator
7. ✅ Deploys Kafka cluster (waits for ready)
8. ✅ Creates Kafka topics
9. ✅ Builds VEX API Docker image (in Minikube)
10. ✅ Deploys VEX API

**Expected time**: 5-10 minutes

### 2. Verify Deployment

```bash
# Check all pods
kubectl get pods -n sbom2cve

# Expected output:
# NAME                                         READY   STATUS    RESTARTS   AGE
# kafka-exporter-...                           1/1     Running   0          2m
# sbom2cve-kafka-0                             1/1     Running   0          4m
# sbom2cve-kafka-1                             1/1     Running   0          4m
# sbom2cve-kafka-2                             1/1     Running   0          4m
# sbom2cve-kafka-entity-operator-...           2/2     Running   0          3m
# sbom2cve-kafka-zookeeper-0                   1/1     Running   0          5m
# sbom2cve-kafka-zookeeper-1                   1/1     Running   0          5m
# sbom2cve-kafka-zookeeper-2                   1/1     Running   0          5m
# strimzi-cluster-operator-...                 1/1     Running   0          6m
# vex-api-...                                  1/1     Running   0          2m

# Check Kafka status
kubectl get kafka -n sbom2cve
# NAME             DESIRED KAFKA REPLICAS   DESIRED ZK REPLICAS   READY   WARNINGS
# sbom2cve-kafka   3                        3                     True

# List Kafka topics
kubectl get kafkatopics -n sbom2cve
# NAME                        CLUSTER          PARTITIONS   REPLICATION FACTOR   READY
# alerts-enriched             sbom2cve-kafka   100          3                    True
# cve-rules-by-purl           sbom2cve-kafka   500          3                    True
# cves-enriched               sbom2cve-kafka   500          3                    True
# kev-feed                    sbom2cve-kafka   1            3                    True
# purl-mapping-rules          sbom2cve-kafka   1            3                    True
# sbom-packages-by-purl       sbom2cve-kafka   500          3                    True
# vex-statements              sbom2cve-kafka   10           3                    True
```

---

## Testing the Deployment

### Test VEX API

#### Terminal 1: Port Forward
```bash
kubectl port-forward svc/vex-api 8080:80 -n sbom2cve
```

#### Terminal 2: Test Endpoints
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
    "justification": "vulnerable_code_not_in_execute_path"
  }'
```

### Test Kafka Producers

#### Terminal 1: Port Forward Kafka
```bash
kubectl port-forward svc/sbom2cve-kafka-bootstrap 9092:9092 -n sbom2cve
```

#### Terminal 2: Run KEV Producer
```bash
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

### Verify Kafka Messages

```bash
# Exec into Kafka pod
kubectl exec -it sbom2cve-kafka-0 -n sbom2cve -- bash

# List topics
bin/kafka-topics.sh --bootstrap-server localhost:9092 --list

# Consume KEV feed
bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic kev-feed \
  --from-beginning \
  --max-messages 5

# Consume VEX statements
bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic vex-statements \
  --from-beginning \
  --max-messages 5
```

---

## Useful Commands

### Minikube Management
```bash
# Check Minikube status
minikube status

# Access Minikube dashboard (web UI)
minikube dashboard

# SSH into Minikube node
minikube ssh

# View Minikube logs
minikube logs

# Stop Minikube (keeps cluster state)
minikube stop

# Start stopped Minikube
minikube start

# Delete Minikube cluster (clean slate)
minikube delete
```

### Kubectl Commands
```bash
# View all resources in sbom2cve namespace
kubectl get all -n sbom2cve

# View pod logs
kubectl logs -f deployment/vex-api -n sbom2cve
kubectl logs -f sbom2cve-kafka-0 -n sbom2cve

# Describe pod (for troubleshooting)
kubectl describe pod <pod-name> -n sbom2cve

# Get events (for debugging)
kubectl get events -n sbom2cve --sort-by='.lastTimestamp'

# Scale VEX API
kubectl scale deployment vex-api --replicas=5 -n sbom2cve

# Restart deployment
kubectl rollout restart deployment/vex-api -n sbom2cve
```

### Kafka Commands
```bash
# Exec into Kafka broker
kubectl exec -it sbom2cve-kafka-0 -n sbom2cve -- bash

# Check consumer groups
bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --list

# Describe consumer group lag
bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe \
  --group my-consumer-group
```

---

## Troubleshooting

### Minikube Won't Start

**Problem**: `minikube start` fails

**Solutions**:
```bash
# Delete and recreate
minikube delete
minikube start --driver=qemu --cpus=4 --memory=8192

# Check logs
minikube logs

# Try different driver (if QEMU fails)
minikube start --driver=hyperkit  # Intel Macs only
```

### Kafka Pods CrashLoopBackOff

**Problem**: Kafka pods stuck in `CrashLoopBackOff`

**Solutions**:
```bash
# Check pod logs
kubectl logs sbom2cve-kafka-0 -n sbom2cve

# Check PVC status
kubectl get pvc -n sbom2cve

# Delete and recreate Kafka cluster
kubectl delete kafka sbom2cve-kafka -n sbom2cve
kubectl apply -f k8s/kafka/kafka-cluster.yaml
```

### VEX API Can't Connect to Kafka

**Problem**: VEX API logs show Kafka connection errors

**Solutions**:
```bash
# Check Kafka service
kubectl get svc sbom2cve-kafka-bootstrap -n sbom2cve

# Test connectivity from VEX API pod
kubectl exec -it deployment/vex-api -n sbom2cve -- \
  nc -zv sbom2cve-kafka-bootstrap 9092

# Check environment variables
kubectl exec deployment/vex-api -n sbom2cve -- env | grep KAFKA
```

### Out of Memory/Disk Space

**Problem**: Minikube runs out of resources

**Solutions**:
```bash
# Check Minikube resource usage
minikube ssh
df -h  # Check disk
free -h  # Check memory

# Increase resources (requires restart)
minikube delete
minikube start --driver=qemu --cpus=6 --memory=12288 --disk-size=60g

# Or reduce Kafka replicas for local testing
# Edit k8s/kafka/kafka-cluster.yaml:
# spec.kafka.replicas: 1
# spec.zookeeper.replicas: 1
```

### Port Forward Fails

**Problem**: `kubectl port-forward` disconnects

**Solutions**:
```bash
# Use a more stable port-forward with retry
while true; do
  kubectl port-forward svc/vex-api 8080:80 -n sbom2cve
  sleep 2
done

# Or use Minikube service (automatic port forward)
minikube service vex-api -n sbom2cve
```

---

## Cleanup

### Stop Minikube (Keep State)
```bash
minikube stop
```

### Delete Everything (Fresh Start)
```bash
minikube delete
```

### Delete Just the Deployment
```bash
kubectl delete namespace sbom2cve
helm uninstall kafka-operator -n sbom2cve
```

---

## Performance Tips

### Reduce Resource Usage for Older Macs
```bash
# Edit k8s/kafka/kafka-cluster.yaml
# Reduce replicas to 1:
spec:
  kafka:
    replicas: 1
  zookeeper:
    replicas: 1
```

### Speed Up Minikube Start
```bash
# Preload images (after first successful start)
minikube cache add strimzi/kafka:0.40.0-kafka-3.6.0
minikube cache add strimzi/operator:0.40.0
```

---

## Comparison: Minikube vs K3s

| Feature | Minikube (macOS) | K3s (Linux) |
|---------|------------------|-------------|
| **Driver** | QEMU/HyperKit | Native systemd |
| **Startup Time** | ~2-3 minutes | ~30 seconds |
| **Resource Overhead** | Higher (VM) | Lower (native) |
| **Docker Required?** | No (QEMU) | No |
| **Dashboard** | Built-in | Manual install |
| **Production Parity** | Good | Excellent |
| **Best For** | macOS local dev | Linux local dev |

---

## Next Steps

Once Minikube deployment is working:

1. **Test Components**: Run unit tests, test PURL mapper, risk scorer
2. **Add Flink Jobs**: Deploy PURL mapper and matcher Flink jobs
3. **Production Deployment**: Transition to EKS/GKE/AKS (see DEPLOYMENT.md)
4. **Monitoring**: Add Prometheus + Grafana dashboards
5. **SBOM Ingestion**: Connect real Flox environments

---

## Support

- **Minikube Docs**: https://minikube.sigs.k8s.io/docs/
- **Strimzi Docs**: https://strimzi.io/docs/
- **Kubernetes Docs**: https://kubernetes.io/docs/

---

**Last Updated**: 2025-10-30
**Tested On**: macOS 15.0 (Sequoia), Apple Silicon
**Minikube Version**: 1.37.0
**Kubernetes Version**: v1.28.0

🤖 Generated with [Claude Code](https://claude.com/claude-code)
