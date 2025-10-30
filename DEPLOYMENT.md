# SBOM2CVE Deployment Guide

Complete deployment instructions for local development (K3s) and production (EKS/GKE/AKS).

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Development (K3s)](#local-development-k3s)
3. [Production Deployment](#production-deployment)
4. [Monitoring](#monitoring)
5. [Troubleshooting](#troubleshooting)
6. [Scaling](#scaling)

---

## Prerequisites

### Required Tools

- **kubectl** (1.28+): Kubernetes CLI
- **helm** (3.0+): Kubernetes package manager
- **Docker** (24.0+): Container runtime (for building images)

### For Local Development

- **K3s** (1.28+): Lightweight Kubernetes (auto-installed by setup script)
- **16GB+ RAM**: Recommended for running Kafka cluster
- **8+ CPU cores**: For optimal performance
- **50GB+ disk**: For Kafka storage

### For Production

- **Cloud Provider**: AWS (EKS), Google Cloud (GKE), or Azure (AKS)
- **Terraform** (optional): Infrastructure as code
- **S3/GCS/Azure Blob**: For Flink checkpoints (when adding Flink)

---

## Local Development (K3s)

### Quick Start (One Command)

```bash
# Clone repository
git clone https://github.com/8BitTacoSupreme/sbom2cve.git
cd sbom2cve

# Checkout MVP branch
git checkout future-state-mvp

# Run setup script
./scripts/k8s-dev-setup.sh
```

The script will:
1. ✅ Install K3s
2. ✅ Install Helm
3. ✅ Add Helm repositories (Strimzi, Prometheus)
4. ✅ Create `sbom2cve` namespace
5. ✅ Install Strimzi Kafka Operator
6. ✅ Deploy Kafka cluster (3 brokers, 3 Zookeeper)
7. ✅ Create Kafka topics (7 topics)
8. ⏭️ Optional: Install Prometheus + Grafana

### Manual Setup (Step-by-Step)

If you prefer manual control or the script fails:

#### 1. Install K3s

```bash
curl -sfL https://get.k3s.io | sh -s - --disable traefik

# Set kubeconfig
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
sudo chmod 644 /etc/rancher/k3s/k3s.yaml
```

#### 2. Install Helm

```bash
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

#### 3. Add Helm Repositories

```bash
helm repo add strimzi https://strimzi.io/charts/
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
```

#### 4. Create Namespace

```bash
kubectl create namespace sbom2cve
```

#### 5. Install Strimzi Kafka Operator

```bash
helm install kafka-operator strimzi/strimzi-kafka-operator \
    --namespace sbom2cve \
    --set watchNamespaces="{sbom2cve}"
```

#### 6. Deploy Kafka Cluster

```bash
kubectl apply -f k8s/kafka/kafka-cluster.yaml

# Wait for ready (3-5 minutes)
kubectl wait kafka/sbom2cve-kafka \
    --for=condition=Ready \
    --timeout=600s \
    -n sbom2cve
```

#### 7. Create Kafka Topics

```bash
kubectl apply -f k8s/kafka/topics.yaml
```

#### 8. Deploy VEX API

```bash
# Build Docker image
docker build -t sbom2cve/vex-api:latest -f docker/Dockerfile.vex-api .

# Deploy to K8s
kubectl apply -f k8s/apps/vex-api.yaml
```

### Verify Deployment

```bash
# Check all pods
kubectl get pods -n sbom2cve

# Expected output:
# NAME                                         READY   STATUS    RESTARTS   AGE
# kafka-operator-...                           1/1     Running   0          5m
# sbom2cve-kafka-0                             1/1     Running   0          4m
# sbom2cve-kafka-1                             1/1     Running   0          4m
# sbom2cve-kafka-2                             1/1     Running   0          4m
# sbom2cve-kafka-zookeeper-0                   1/1     Running   0          5m
# sbom2cve-kafka-zookeeper-1                   1/1     Running   0          5m
# sbom2cve-kafka-zookeeper-2                   1/1     Running   0          5m
# vex-api-...                                  1/1     Running   0          2m

# Check Kafka topics
kubectl get kafkatopics -n sbom2cve

# Expected: 7 topics (purl-mapping-rules, cves-enriched, kev-feed, etc.)
```

### Test Local Deployment

```bash
# Port forward Kafka
kubectl port-forward svc/sbom2cve-kafka-bootstrap 9092:9092 -n sbom2cve &

# Port forward VEX API
kubectl port-forward svc/vex-api 8080:80 -n sbom2cve &

# Test KEV producer
python3 src/producers/kev_producer.py --once

# Test VEX API
curl http://localhost:8080/health
curl http://localhost:8080/api/v1/vex/schema
```

### Access Monitoring (if installed)

```bash
# Port forward Grafana
kubectl port-forward svc/prometheus-grafana 3000:80 -n sbom2cve

# Open http://localhost:3000
# Username: admin
# Password: prom-operator
```

---

## Production Deployment

### AWS (EKS)

#### 1. Create EKS Cluster

```bash
# Using eksctl
eksctl create cluster \
    --name sbom2cve-prod \
    --region us-west-2 \
    --nodegroup-name standard-workers \
    --node-type t3.xlarge \
    --nodes 6 \
    --nodes-min 3 \
    --nodes-max 10 \
    --managed

# Or using Terraform
cd terraform/aws
terraform init
terraform apply
```

#### 2. Install Strimzi Operator

```bash
helm install kafka-operator strimzi/strimzi-kafka-operator \
    --namespace sbom2cve \
    --create-namespace \
    --set watchNamespaces="{sbom2cve}"
```

#### 3. Deploy Kafka Cluster (Production Config)

```yaml
# Update k8s/kafka/kafka-cluster.yaml for production:
spec:
  kafka:
    replicas: 5  # More brokers for higher throughput
    storage:
      volumes:
        - size: 500Gi  # Larger disks
          class: gp3  # AWS SSD
    resources:
      requests:
        memory: 8Gi
        cpu: 4000m
      limits:
        memory: 16Gi
        cpu: 8000m
```

```bash
kubectl apply -f k8s/kafka/kafka-cluster.yaml
```

#### 4. Configure S3 for Backups (Optional)

```bash
# Create S3 bucket
aws s3 mb s3://sbom2cve-kafka-backups

# Update Kafka config with S3 credentials
# (Add to kafka-cluster.yaml under spec.kafka.config)
```

### Google Cloud (GKE)

```bash
# Create GKE cluster
gcloud container clusters create sbom2cve-prod \
    --zone us-central1-a \
    --num-nodes 6 \
    --machine-type n1-standard-4

# Get credentials
gcloud container clusters get-credentials sbom2cve-prod

# Deploy (same as AWS steps 2-3)
```

### Azure (AKS)

```bash
# Create AKS cluster
az aks create \
    --resource-group sbom2cve \
    --name sbom2cve-prod \
    --node-count 6 \
    --node-vm-size Standard_D4s_v3

# Get credentials
az aks get-credentials --resource-group sbom2cve --name sbom2cve-prod

# Deploy (same as AWS steps 2-3)
```

---

## Monitoring

### Prometheus Metrics

**Kafka Metrics** (via JMX Exporter):
- `kafka_server_broker_topic_metrics_messages_in_total`
- `kafka_server_broker_topic_metrics_bytes_in_total`
- `kafka_server_replica_manager_under_replicated_partitions`

**VEX API Metrics** (via /metrics):
- `flask_http_request_total`
- `flask_http_request_duration_seconds`
- `vex_statements_submitted_total`

### Grafana Dashboards

Pre-configured dashboards available:

1. **Kafka Overview**
   - Broker health
   - Topic throughput
   - Consumer lag

2. **VEX API**
   - Request rate
   - Latency (p50, p95, p99)
   - Error rate

3. **Alerts**
   - Under-replicated partitions
   - Consumer lag > threshold
   - API error rate > 5%

### Log Aggregation

```bash
# View Kafka logs
kubectl logs -f sbom2cve-kafka-0 -n sbom2cve

# View VEX API logs
kubectl logs -f deployment/vex-api -n sbom2cve

# Stream all logs
kubectl logs -f -l app=sbom2cve -n sbom2cve --all-containers=true
```

---

## Troubleshooting

### Kafka Not Starting

**Problem**: Kafka pods stuck in `CrashLoopBackOff`

**Solution**:
```bash
# Check pod logs
kubectl logs sbom2cve-kafka-0 -n sbom2cve

# Common issues:
# 1. Insufficient memory → Increase resources in kafka-cluster.yaml
# 2. Storage not provisioned → Check PVC status
kubectl get pvc -n sbom2cve

# 3. Zookeeper not ready → Wait for Zookeeper first
kubectl get pods -l strimzi.io/name=sbom2cve-kafka-zookeeper -n sbom2cve
```

### Topic Creation Failed

**Problem**: KafkaTopic resources stuck in `NotReady`

**Solution**:
```bash
# Check topic operator logs
kubectl logs -l strimzi.io/kind=topic-operator -n sbom2cve

# Describe topic
kubectl describe kafkatopic purl-mapping-rules -n sbom2cve

# Delete and recreate
kubectl delete kafkatopic purl-mapping-rules -n sbom2cve
kubectl apply -f k8s/kafka/topics.yaml
```

### VEX API Not Connecting to Kafka

**Problem**: VEX API logs show Kafka connection errors

**Solution**:
```bash
# Check if Kafka service is accessible
kubectl run -it --rm debug --image=busybox --restart=Never -n sbom2cve -- \
    nc -zv sbom2cve-kafka-bootstrap 9092

# Verify env vars in VEX API pod
kubectl exec deployment/vex-api -n sbom2cve -- env | grep KAFKA

# Check network policies (if any)
kubectl get networkpolicies -n sbom2cve
```

### High Consumer Lag

**Problem**: Consumer groups falling behind

**Solution**:
```bash
# Check consumer lag
kubectl exec sbom2cve-kafka-0 -n sbom2cve -- bin/kafka-consumer-groups.sh \
    --bootstrap-server localhost:9092 \
    --describe --group my-consumer-group

# Increase consumer parallelism
# OR
# Increase Kafka partitions
kubectl patch kafkatopic cves-enriched -n sbom2cve --type merge \
    -p '{"spec":{"partitions":1000}}'
```

---

## Scaling

### Scale Kafka Brokers

```bash
# Edit kafka-cluster.yaml
# Change spec.kafka.replicas: 5

kubectl apply -f k8s/kafka/kafka-cluster.yaml

# Wait for new brokers
kubectl wait kafka/sbom2cve-kafka --for=condition=Ready -n sbom2cve
```

### Scale VEX API

```bash
# Manual scaling
kubectl scale deployment vex-api --replicas=10 -n sbom2cve

# Or adjust HPA
kubectl edit hpa vex-api-hpa -n sbom2cve
# Change maxReplicas: 20
```

### Scale Kafka Topics (Add Partitions)

```bash
# WARNING: Cannot decrease partitions, only increase!

# Edit topics.yaml
# Change spec.partitions for target topic

kubectl apply -f k8s/kafka/topics.yaml
```

### Vertical Scaling (More Resources)

```bash
# Edit kafka-cluster.yaml
spec:
  kafka:
    resources:
      requests:
        memory: 16Gi
        cpu: 8000m

kubectl apply -f k8s/kafka/kafka-cluster.yaml

# Kafka will roll out new pods one by one
```

---

## Performance Tuning

### Kafka Producer Optimization

```python
# In your producer code
producer = KafkaProducer(
    bootstrap_servers=['kafka:9092'],
    compression_type='lz4',  # Enable compression
    batch_size=32768,  # 32KB batches
    linger_ms=10,  # Wait 10ms to batch
    acks='1'  # Faster than acks='all'
)
```

### Kafka Consumer Optimization

```python
consumer = KafkaConsumer(
    'alerts-enriched',
    bootstrap_servers=['kafka:9092'],
    fetch_min_bytes=1048576,  # 1MB min fetch
    fetch_max_wait_ms=500,  # Max wait 500ms
    max_poll_records=1000  # Batch processing
)
```

### VEX API Optimization

```yaml
# In k8s/apps/vex-api.yaml
spec:
  replicas: 5  # More replicas
  template:
    spec:
      containers:
        - name: vex-api
          env:
            - name: FLASK_WORKERS
              value: "4"  # Gunicorn workers
```

---

## Backup & Disaster Recovery

### Kafka Topic Backup

```bash
# Using MirrorMaker 2
kubectl apply -f k8s/kafka/mirror-maker.yaml

# Or manual export
kubectl exec sbom2cve-kafka-0 -n sbom2cve -- \
    bin/kafka-console-consumer.sh \
    --bootstrap-server localhost:9092 \
    --topic cves-enriched \
    --from-beginning > backup.json
```

### Restore from Backup

```bash
# Recreate topics
kubectl apply -f k8s/kafka/topics.yaml

# Import data
cat backup.json | kubectl exec -i sbom2cve-kafka-0 -n sbom2cve -- \
    bin/kafka-console-producer.sh \
    --bootstrap-server localhost:9092 \
    --topic cves-enriched
```

---

## Security Hardening

### Enable TLS

```yaml
# In kafka-cluster.yaml
spec:
  kafka:
    listeners:
      - name: tls
        port: 9093
        type: internal
        tls: true
        authentication:
          type: tls  # Mutual TLS
```

### Network Policies

```yaml
# k8s/security/network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: kafka-allow
  namespace: sbom2cve
spec:
  podSelector:
    matchLabels:
      strimzi.io/cluster: sbom2cve-kafka
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: vex-api
      ports:
        - protocol: TCP
          port: 9092
```

---

## Cost Optimization

### AWS Cost Reduction

- Use **Spot Instances** for non-critical workloads
- Enable **EBS GP3** instead of GP2 (20% cheaper)
- Use **Graviton instances** (t4g.xlarge) for 20% savings
- Enable **Cluster Autoscaler** to scale down during off-hours

### GCP Cost Reduction

- Use **Preemptible VMs** for dev/staging
- Enable **Custom Machine Types** to right-size
- Use **Regional Persistent Disks** (cheaper than Zonal)
- Enable **GKE Autopilot** for automatic optimization

### Azure Cost Reduction

- Use **Spot VMs** for non-production
- Enable **Azure Hybrid Benefit** if you have licenses
- Use **Premium SSD v2** for better price/performance
- Enable **AKS Node Auto-scaling**

---

## Support & Documentation

- **GitHub Issues**: https://github.com/8BitTacoSupreme/sbom2cve/issues
- **Strimzi Docs**: https://strimzi.io/docs/
- **Kafka Docs**: https://kafka.apache.org/documentation/
- **K3s Docs**: https://docs.k3s.io/

---

**Last Updated**: 2025-10-30
**Version**: 1.0 (MVP)
**Maintainer**: SBOM2CVE Team

🤖 Generated with [Claude Code](https://claude.com/claude-code)
