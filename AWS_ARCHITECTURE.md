# SBOM2CVE AWS Architecture Diagrams

Visual representations of production and dev deployments on AWS.

---

## Production Deployment (~$326/month)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          AWS Region: us-west-2                              │
│                          VPC: 10.0.0.0/16                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │ Availability Zone: us-west-2a                                      │    │
│  │ Subnet: 10.0.0.0/24 (Public)                                       │    │
│  ├────────────────────────────────────────────────────────────────────┤    │
│  │                                                                      │    │
│  │  ┌─────────────────────────────────────┐                           │    │
│  │  │ EC2: sbom2cve-server                │  ←── Elastic IP           │    │
│  │  │ Type: t3.large                      │      54.123.45.67         │    │
│  │  │ • 2 vCPU, 8GB RAM                   │                           │    │
│  │  │ • 100GB EBS (gp3, 3000 IOPS)        │  ←── SSH (port 22)        │    │
│  │  │                                      │  ←── K8s API (port 6443)  │    │
│  │  │ Role: K3s Server (Control Plane)    │                           │    │
│  │  │ • kubectl, helm                      │                           │    │
│  │  │ • Strimzi Operator                   │                           │    │
│  │  └──────────────┬──────────────────────┘                           │    │
│  │                 │                                                    │    │
│  │                 │ K3s Cluster Network (private)                     │    │
│  │                 │                                                    │    │
│  └─────────────────┼────────────────────────────────────────────────────┘    │
│                    │                                                         │
│  ┌─────────────────┼────────────────────────────────────────────────────┐  │
│  │ AZ: us-west-2a  │  Subnet: 10.0.0.0/24                               │  │
│  ├─────────────────┼────────────────────────────────────────────────────┤  │
│  │                 ▼                                                      │  │
│  │  ┌──────────────────────────────┐                                    │  │
│  │  │ EC2: sbom2cve-agent-1        │  ←── Public IP: 54.x.x.1          │  │
│  │  │ Type: t3.xlarge              │                                    │  │
│  │  │ • 4 vCPU, 16GB RAM           │                                    │  │
│  │  │ • 200GB EBS (gp3, 3000 IOPS) │                                    │  │
│  │  │                               │                                    │  │
│  │  │ Pods:                         │                                    │  │
│  │  │ • Kafka Broker 1             │  ←── Kafka (port 9092)            │  │
│  │  │ • Zookeeper 1                │                                    │  │
│  │  │ • VEX API (replica 1-3)      │  ◄─┐                              │  │
│  │  └──────────────────────────────┘    │                              │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                          │                                  │
│  ┌──────────────────────────────────────┼─────────────────────────────┐   │
│  │ AZ: us-west-2b  Subnet: 10.0.1.0/24  │                             │   │
│  ├──────────────────────────────────────┼─────────────────────────────┤   │
│  │  ┌──────────────────────────────┐    │                             │   │
│  │  │ EC2: sbom2cve-agent-2        │  ←─┼── Public IP: 54.x.x.2       │   │
│  │  │ Type: t3.xlarge              │    │                             │   │
│  │  │ • 4 vCPU, 16GB RAM           │    │                             │   │
│  │  │ • 200GB EBS (gp3)            │    │                             │   │
│  │  │                               │    │                             │   │
│  │  │ Pods:                         │    │                             │   │
│  │  │ • Kafka Broker 2             │    │                             │   │
│  │  │ • Zookeeper 2                │    │                             │   │
│  │  │ • VEX API (replica 4-6)      │  ◄─┤                             │   │
│  │  └──────────────────────────────┘    │                             │   │
│  └──────────────────────────────────────┼─────────────────────────────┘   │
│                                          │                                  │
│  ┌──────────────────────────────────────┼─────────────────────────────┐   │
│  │ AZ: us-west-2c  Subnet: 10.0.2.0/24  │                             │   │
│  ├──────────────────────────────────────┼─────────────────────────────┤   │
│  │  ┌──────────────────────────────┐    │                             │   │
│  │  │ EC2: sbom2cve-agent-3        │  ←─┼── Public IP: 54.x.x.3       │   │
│  │  │ Type: t3.xlarge              │    │                             │   │
│  │  │ • 4 vCPU, 16GB RAM           │    │                             │   │
│  │  │ • 200GB EBS (gp3)            │    │                             │   │
│  │  │                               │    │                             │   │
│  │  │ Pods:                         │    │                             │   │
│  │  │ • Kafka Broker 3             │    │                             │   │
│  │  │ • Zookeeper 3                │    │                             │   │
│  │  │ • VEX API (replica 7-10)     │  ◄─┤                             │   │
│  │  └──────────────────────────────┘    │                             │   │
│  └──────────────────────────────────────┼─────────────────────────────┘   │
│                                          │                                  │
│  ┌──────────────────────────────────────┼─────────────────────────────┐   │
│  │ Application Load Balancer (ALB)      │                             │   │
│  │ DNS: sbom2cve-alb-xyz.elb.amazonaws.com                            │   │
│  ├──────────────────────────────────────┴─────────────────────────────┤   │
│  │                                                                      │   │
│  │  Target Group: vex-api-tg (port 8080)                              │   │
│  │  Health Check: GET /health (every 30s)                             │   │
│  │                                                                      │   │
│  │  Targets: ┌─ Agent 1:8080 (healthy) ──────────────────────────────┘   │
│  │           ├─ Agent 2:8080 (healthy)                                    │
│  │           └─ Agent 3:8080 (healthy)                                    │
│  │                                                                         │
│  │  Listener: HTTP:80 → Forward to vex-api-tg                            │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ Security Group: sbom2cve-k3s-sg                                     │  │
│  ├─────────────────────────────────────────────────────────────────────┤  │
│  │ Inbound Rules:                                                       │  │
│  │ • SSH (22)         ← YOUR_IP/32 only                                │  │
│  │ • K8s API (6443)   ← YOUR_IP/32 only                                │  │
│  │ • Kafka (9092)     ← 10.0.0.0/16 (VPC only)                         │  │
│  │ • VEX API (8080)   ← 0.0.0.0/0 (public via ALB)                     │  │
│  │ • Internal (all)   ← Self (cluster communication)                   │  │
│  │                                                                       │  │
│  │ Outbound Rules:                                                      │  │
│  │ • All traffic      → 0.0.0.0/0                                      │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ IAM Role: sbom2cve-k3s-node-role                                    │  │
│  ├─────────────────────────────────────────────────────────────────────┤  │
│  │ Permissions:                                                         │  │
│  │ • ec2:AttachVolume, ec2:DetachVolume (for EBS)                      │  │
│  │ • ecr:GetAuthorizationToken (for Docker images)                     │  │
│  │ • logs:CreateLogGroup, logs:PutLogEvents (CloudWatch)               │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

Internet Gateway: 0.0.0.0/0 ───┐
                                │
                                ▼
                    ┌──────────────────────┐
                    │  Public Access       │
                    ├──────────────────────┤
                    │ ALB (HTTP:80)        │ ──► VEX API
                    │ Server SSH (22)      │ ──► Control plane
                    │ K8s API (6443)       │ ──► kubectl
                    └──────────────────────┘

Monthly Cost: ~$326
  • EC2 (1x t3.large):      ~$60
  • EC2 (3x t3.xlarge):     ~$180
  • EBS (100GB + 600GB):    ~$56
  • ALB:                    ~$20
  • Data Transfer:          ~$10
```

---

## Dev/Free Tier Deployment (~$2-5/month)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          AWS Region: us-east-1                              │
│                          VPC: 10.0.0.0/16                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │ Availability Zone: us-east-1a                                      │    │
│  │ Subnet: 10.0.0.0/24 (Public)                                       │    │
│  ├────────────────────────────────────────────────────────────────────┤    │
│  │                                                                      │    │
│  │  ┌─────────────────────────────────────┐                           │    │
│  │  │ EC2: sbom2cve-dev-server            │  ←── Elastic IP           │    │
│  │  │ Type: t2.micro  ⭐ FREE TIER        │      54.123.45.67         │    │
│  │  │ • 1 vCPU, 1GB RAM                   │                           │    │
│  │  │ • 20GB EBS (gp2) ⭐ PARTIAL FREE    │  ←── SSH (port 22)        │    │
│  │  │ • 2GB Swap (for stability)          │  ←── K8s API (port 6443)  │    │
│  │  │                                      │                           │    │
│  │  │ Role: K3s Server (Control Plane)    │  Free Tier Hours:         │    │
│  │  │ • kubectl, helm                      │  750 hrs/month            │    │
│  │  │ • Strimzi Operator (lightweight)    │  = 24/7 coverage ✅       │    │
│  │  └──────────────┬──────────────────────┘                           │    │
│  │                 │                                                    │    │
│  │                 │ K3s Cluster Network (private)                     │    │
│  │                 │                                                    │    │
│  │                 ▼                                                    │    │
│  │  ┌──────────────────────────────┐                                  │    │
│  │  │ EC2: sbom2cve-dev-agent-1    │  ←── Public IP: 54.x.x.1        │    │
│  │  │ Type: t2.micro  ⭐ FREE TIER  │                                  │    │
│  │  │ • 1 vCPU, 1GB RAM            │                                  │    │
│  │  │ • 30GB EBS (gp2) ⭐ FREE      │  Free Tier Hours:                │    │
│  │  │ • 2GB Swap (critical!)       │  750 hrs/month                   │    │
│  │  │                               │  = 24/7 coverage ✅              │    │
│  │  │ Pods (Reduced Resources):     │                                  │    │
│  │  │ • Kafka Broker 1 (ONLY)      │  ←── Kafka (9092)               │    │
│  │  │   - 512Mi RAM, 256m-512m JVM │      VPC only                    │    │
│  │  │ • Zookeeper 1 (ONLY)         │                                  │    │
│  │  │   - 256Mi RAM                │                                  │    │
│  │  │ • VEX API (1 replica)        │  ←── Port-forward                │    │
│  │  │   - 128Mi RAM                │      (no ALB)                    │    │
│  │  └──────────────────────────────┘                                  │    │
│  │                                                                      │    │
│  │  Memory Allocation (1GB total):                                    │    │
│  │  ┌────────────────────────────────────────────┐                    │    │
│  │  │ Kafka:     512Mi  ████████████             │                    │    │
│  │  │ Zookeeper: 256Mi  ██████                   │                    │    │
│  │  │ VEX API:   128Mi  ███                      │                    │    │
│  │  │ System:    100Mi  ██                       │                    │    │
│  │  │ Swap:      2GB    (overflow)               │                    │    │
│  │  └────────────────────────────────────────────┘                    │    │
│  │                                                                      │    │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ❌ No Application Load Balancer (saves ~$20/month)                        │
│     Use kubectl port-forward instead:                                      │
│     kubectl port-forward svc/vex-api 8080:80 -n sbom2cve                  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ Security Group: sbom2cve-dev-sg                                     │  │
│  ├─────────────────────────────────────────────────────────────────────┤  │
│  │ Inbound Rules:                                                       │  │
│  │ • SSH (22)         ← YOUR_IP/32 only                                │  │
│  │ • K8s API (6443)   ← YOUR_IP/32 only                                │  │
│  │ • Kafka (9092)     ← 10.0.0.0/16 (VPC only, no external)            │  │
│  │ • Internal (all)   ← Self (cluster communication)                   │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ Kafka Configuration (Dev-Optimized)                                 │  │
│  ├─────────────────────────────────────────────────────────────────────┤  │
│  │ • Replicas: 1 (no replication)                                      │  │
│  │ • Partitions: 10 (vs 500 in prod)                                   │  │
│  │ • Retention: 1 day (vs 7 days in prod)                              │  │
│  │ • Storage: 10GB (vs 100GB in prod)                                  │  │
│  │ • JVM Heap: 256m-512m (vs 2GB in prod)                              │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

Internet Gateway: 0.0.0.0/0 ───┐
                                │
                                ▼
                    ┌──────────────────────┐
                    │  Public Access       │
                    ├──────────────────────┤
                    │ Server SSH (22)      │ ──► Control plane
                    │ K8s API (6443)       │ ──► kubectl
                    │ ❌ No VEX API ALB    │ ──► Use port-forward
                    └──────────────────────┘

Monthly Cost: ~$2-5 (first 12 months with Free Tier)
  • EC2 (2x t2.micro):       $0    (750 hrs/month free each)
  • EBS (50GB gp2):          ~$2   (30GB free + $0.10/GB for 20GB)
  • Data Transfer (< 15GB):  $0    (15GB/month free)
  • ❌ No ALB:               $0    (saves ~$20/month)

After Free Tier (12 months): ~$15/month
  • EC2 (2x t2.micro):       ~$8
  • EBS (50GB gp2):          ~$5
  • Data Transfer:           ~$2
```

---

## Side-by-Side Comparison

```
┌─────────────────────────────┬──────────────────────────────┐
│  PRODUCTION (~$326/month)   │  DEV/FREE TIER (~$2-5/month) │
├─────────────────────────────┼──────────────────────────────┤
│                             │                              │
│  ┌────────────────┐         │  ┌────────────────┐         │
│  │ t3.large       │         │  │ t2.micro ⭐     │         │
│  │ 2 vCPU, 8GB    │         │  │ 1 vCPU, 1GB    │         │
│  │ 100GB EBS      │         │  │ 20GB EBS       │         │
│  │ K3s Server     │         │  │ K3s Server     │         │
│  └────────────────┘         │  │ + 2GB Swap     │         │
│                             │  └────────────────┘         │
│         │                   │         │                   │
│         ▼                   │         ▼                   │
│                             │                              │
│  ┌────────────────┐         │  ┌────────────────┐         │
│  │ t3.xlarge (×3) │         │  │ t2.micro ⭐     │         │
│  │ 4 vCPU, 16GB   │         │  │ 1 vCPU, 1GB    │         │
│  │ 200GB EBS each │         │  │ 30GB EBS       │         │
│  │                │         │  │                │         │
│  │ • Kafka (×3)   │         │  │ • Kafka (×1)   │         │
│  │ • Zookeeper(×3)│         │  │ • Zookeeper(×1)│         │
│  │ • VEX API (×9) │         │  │ • VEX API (×1) │         │
│  └────────────────┘         │  │ + 2GB Swap     │         │
│                             │  └────────────────┘         │
│         │                   │         │                   │
│         ▼                   │         ▼                   │
│                             │                              │
│  ┌────────────────┐         │  ❌ No ALB                  │
│  │ ALB (public)   │         │  Use port-forward           │
│  │ Port 80        │         │                              │
│  └────────────────┘         │                              │
│                             │                              │
│  High Availability ✅       │  Single Point of Failure ⚠️  │
│  3 Kafka Replicas ✅        │  No Replication ⚠️           │
│  500 Partitions ✅          │  10 Partitions ⚠️            │
│  7 Day Retention ✅         │  1 Day Retention ⚠️          │
│  Public VEX API ✅          │  Port-Forward Only ⚠️        │
│  Auto-Scaling (HPA) ✅      │  Fixed Resources ⚠️          │
│                             │                              │
│  Best For: Production       │  Best For: Learning, Demos   │
└─────────────────────────────┴──────────────────────────────┘
```

---

## Data Flow (Same for Both Deployments)

```
┌────────────┐
│ KEV Feed   │ ──► Kafka Topic: kev-feed (1,451 CVEs)
│ (CISA)     │
└────────────┘

┌────────────┐
│ SBOM       │ ──► Kafka Topic: sbom-packages-by-purl
│ (Flox Env) │     (Nix packages from environment)
└────────────┘

┌────────────┐
│ NVD CVEs   │ ──► PURL Mapper ──► Kafka Topic: cves-enriched
│ (upstream) │     (PyPI/npm → Nix)   (95% more coverage!)
└────────────┘

                      │
                      ▼
              ┌───────────────┐
              │ Matcher Logic │
              │ (Join streams)│
              └───────┬───────┘
                      │
                      ▼
              ┌───────────────┐
              │ Risk Scorer   │ ◄── VEX Overrides
              │ (5 signals)   │
              └───────┬───────┘
                      │
                      ▼
              ┌───────────────┐
              │ alerts-       │
              │ enriched      │
              │ (Prioritized) │
              └───────────────┘
                      │
                      ▼
              ┌───────────────┐
              │ FloxHub UI    │
              │ (Dashboard)   │
              └───────────────┘
```

---

**Legend**:
- ⭐ = AWS Free Tier eligible
- ✅ = Available/Enabled
- ⚠️  = Limited/Reduced
- ❌ = Disabled/Not available

🤖 Generated with [Claude Code](https://claude.com/claude-code)
