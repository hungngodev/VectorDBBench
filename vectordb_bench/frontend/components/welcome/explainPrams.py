def explainPrams(st):
    st.markdown("# VectorDB Benchmark - UMass Edition")
    st.markdown("*Comprehensive benchmark framework for comparing vector databases on UMass Swarm Kubernetes cluster*")
    
    st.markdown("---")
    
    # Quick Start
    st.markdown("## Quick Start")
    st.markdown("""
### 1. Clone & Install
```bash
git clone https://github.com/hungngodev/VectorDBBench.git
cd VectorDBBench
pip install poetry && poetry install
```

### 2. Build & Push Docker Image
```bash
docker build -t hungngodev/vectordbbench:latest .
docker push hungngodev/vectordbbench:latest
```

### 3. Run a Benchmark
```bash
# Minimal: Run with defaults (100K dataset, Milvus + Weaviate)
bash Benchmark/scripts/run_all_nohup.sh

# Custom: 1M dataset, distributed mode
CASE_TYPE=Performance768D1M \\
BATCH_ID="MY-TEST" \\
REPLICA=3 SHARDING=1 \\
ENABLE_MILVUS=true ENABLE_WEAVIATE=true \\
bash Benchmark/scripts/run_all_nohup.sh
```

### 4. View Results
```bash
# Start this Streamlit UI
cd vectordb_bench && streamlit run Home.py
# Open: http://localhost:8501
```
""")
    
    st.markdown("---")
    
    # Database Setup
    st.markdown("## Database Setup on Kubernetes (UMass Swarm)")
    st.markdown("""
### Prerequisites
- SSH access to UMass Swarm cluster: `ssh user@swarm056.cs.umass.edu`
- Kubernetes cluster with `kubectl` configured
- Helm 3.x installed
- Namespace created (default: `marco`)

```bash
kubectl create namespace marco
```

### Milvus Installation
```bash
# Add Milvus Helm repo
helm repo add milvus https://zilliztech.github.io/milvus-helm/
helm repo update

# Install Milvus (distributed mode with 3 query nodes)
helm install milvus milvus/milvus -n marco \\
  --set cluster.enabled=true \\
  --set queryNode.replicas=3 \\
  --set dataNode.replicas=1 \\
  --set indexNode.replicas=1

# Verify installation
kubectl get pods -n marco -l app.kubernetes.io/instance=milvus
```
**Service URL:** `milvus.marco.svc.cluster.local:19530`

### Weaviate Installation
```bash
# Add Weaviate Helm repo
helm repo add semitechnologies https://semitechnologies.github.io/weaviate-helm
helm repo update

# Install Weaviate (3 replicas for Raft consensus)
helm install weaviate semitechnologies/weaviate -n marco \\
  --set replicas=3 \\
  --set storage.size=50Gi

# Verify installation
kubectl get pods -n marco -l app.kubernetes.io/name=weaviate
```
**Service URL:** `weaviate.marco.svc.cluster.local:8080`

### Scaling Databases
```bash
# Scale Milvus query nodes
helm upgrade milvus milvus/milvus -n marco --set queryNode.replicas=3

# Scale Weaviate replicas
helm upgrade weaviate semitechnologies/weaviate -n marco --set replicas=3
```

### Understanding Replication vs Sharding
| Strategy | What it does | When to use |
|----------|--------------|-------------|
| **Replication** (`REPLICA=3`) | Creates 3 copies of full data, queries distributed across replicas | Fault tolerance + query parallelism |
| **Sharding** (`SHARDING=3`) | Splits data into 3 partitions, each shard searched in parallel | Data too large for one node |
| **Both** (`REPLICA=3, SHARDING=3`) | 3 shards × 3 replicas = 9 total nodes | Maximum parallelism + fault tolerance |

**Milvus Implementation:**
- `replica_number`: Query parallelism via multiple query nodes
- `num_shards`: Data partitioning at collection level

**Weaviate Implementation:**
- `replication_factor`: Raft consensus (fault tolerance)
- `sharding_count`: Data partitioning across nodes
""")
    
    st.markdown("---")
    
    # Dataset Preparation
    st.markdown("## Dataset Preparation")
    st.markdown("""
### Pre-cache Datasets to NFS (UMass Swarm)
Before running benchmarks, download datasets to shared storage:

```bash
# SSH into UMass Swarm cluster
ssh user@swarm056.cs.umass.edu

# Run the dataset preparation script
./Benchmark/prepare_datasets.sh /mnt/nfs/shared/datasets
```

### Available Datasets
| Dataset | Dimensions | Sizes | Use Case |
|---------|------------|-------|----------|
| **Cohere** | 768 | 100K, 1M, 10M | `Performance768D100K`, `Performance768D1M` |
| **OpenAI** | 1536 | 50K, 500K, 5M | `Performance1536D50K`, `Performance1536D500K` |
| **SIFT** | 128 | 500K | Low-dimensional benchmark |

### Manual Dataset Download
```python
from vectordb_bench.backend.dataset import Dataset
from vectordb_bench.backend.filter import non_filter

# Download Cohere 1M
manager = Dataset.COHERE.manager(1_000_000)
manager.prepare(filters=non_filter)
```
""")
    
    st.markdown("---")
    
    # Running Benchmarks
    st.markdown("## Running Benchmarks")
    st.markdown("""
### Understanding the Benchmark Flow
1. **`run_all_nohup.sh`** - Entry point, runs in background with logging
2. **`run_all_and_cleanup.sh`** - Orchestrates the benchmark pipeline
3. **`run_config_matrix.sh`** - Creates K8s jobs for each M/EF configuration
4. **`config.sh`** - Central configuration file

### Basic Usage
```bash
# Run with defaults (logs to Benchmark/archive/logs/run_all.log)
bash Benchmark/scripts/run_all_nohup.sh

# Monitor logs
tail -f Benchmark/archive/logs/run_all.log
```

### Advanced Usage
```bash
# Full distributed test (1M dataset, 3 replicas, sharding)
CASE_TYPE=Performance768D1M \\
BATCH_ID="DISTRIBUTED-1M" \\
HNSW_EF_VALUES="100 150 200 300 500 800 1200" \\
REPLICA=3 \\
SHARDING=1 \\
ENABLE_MILVUS=true \\
ENABLE_WEAVIATE=true \\
bash Benchmark/scripts/run_all_nohup.sh
```

### Test Matrix Examples
| Test Type | REPLICA | SHARDING | Description |
|-----------|---------|----------|-------------|
| Baseline | 1 | 1 | Single node performance |
| Replicated | 3 | 1 | Query replication (load balanced) |
| Sharded | 1 | 3 | Data partitioned across nodes |
| Full Distributed | 3 | 3 | Combined replication + sharding |

### Scheduling Sequential Tests
```bash
# Wait for current job to finish, then start next
PID=$(pgrep -f run_all_and_cleanup.sh)
while kill -0 $PID 2>/dev/null; do sleep 60; done && \\
BATCH_ID="NEXT-TEST" bash Benchmark/scripts/run_all_nohup.sh
```
""")
    
    st.markdown("---")
    
    # CLI Commands
    st.markdown("## CLI Commands (vectordbbench)")
    st.markdown("""
### List Available Commands
```bash
vectordbbench --help
```

### Run Individual Benchmarks
```bash
# Milvus HNSW benchmark
vectordbbench milvushnsw \\
  --uri http://milvus.marco.svc.cluster.local:19530 \\
  --case-type Performance768D100K \\
  --m 32 --ef-search 100 --ef-construction 256 \\
  --replica-number 3 --num-shards 1 \\
  --drop-old --load --search-serial --search-concurrent \\
  --num-concurrency 1,2,4,8,16,32

# Weaviate benchmark
vectordbbench weaviate \\
  --url http://weaviate.marco.svc.cluster.local \\
  --no-auth \\
  --case-type Performance768D100K \\
  --m 32 --ef 100 --ef-construction 256 \\
  --replication-factor 3 --sharding-count 1 \\
  --metric-type COSINE \\
  --drop-old --load --search-serial --search-concurrent \\
  --num-concurrency 1,2,4,8,16,32
```

### Common CLI Flags
| Flag | Description |
|------|-------------|
| `--drop-old` | Drop existing collection before loading |
| `--skip-drop-old` | Keep existing collection |
| `--load` | Load data into the database |
| `--skip-load` | Skip data loading (use existing) |
| `--search-serial` | Run serial search benchmark |
| `--search-concurrent` | Run concurrent search benchmark |
| `--num-concurrency` | Comma-separated concurrency levels |
| `--db-label` | Label for this database configuration |
| `--task-label` | Label for this benchmark task |
""")
    
    st.markdown("---")
    
    # Configuration Reference
    st.markdown("## Configuration Reference")
    st.markdown("""
### Environment Variables (`config.sh`)
| Variable | Default | Description |
|----------|---------|-------------|
| `NS` | `marco` | Kubernetes namespace |
| `IMG` | `hungngodev/vectordbbench:latest` | Benchmark Docker image |
| `CASE_TYPE` | `Performance768D100K` | Dataset: `Performance768D100K` or `Performance768D1M` |
| `BATCH_ID` | Auto-generated | Unique identifier for this test batch |
| **HNSW Parameters** |||
| `HNSW_M_VALUES` | `"32"` | Graph connectivity (space-separated) |
| `HNSW_EF_VALUES` | `"100 110 120..."` | Search beam width (space-separated) |
| `EF_CONSTRUCTION` | `256` | Index build quality |
| **Scaling** |||
| `REPLICA` | `3` | Replication factor (query parallelism) |
| `SHARDING` | `1` | Data partitioning count |
| **Performance** |||
| `NUM_CONCURRENCY` | `"1,2,4,8,16,32,64,128,256,512"` | Concurrency levels to test |
| `CONCURRENCY_DURATION` | `30` | Seconds per concurrency level |
| `K` | `100` | Number of nearest neighbors |
| **Resources** |||
| `CPU` | `48` | Pod CPU limit |
| `MEM` | `130Gi` | Pod memory limit |
| **Database Toggles** |||
| `ENABLE_MILVUS` | `true` | Run Milvus benchmarks |
| `ENABLE_WEAVIATE` | `true` | Run Weaviate benchmarks |
| `ENABLE_QDRANT` | `false` | Run Qdrant benchmarks |
| `ENABLE_VALD` | `false` | Run Vald benchmarks |

### Task Label Format
Benchmark results are labeled as: `BATCH_ID-database-mX-efY-repZ-shardW`

Example: `DISTRIBUTED-1M-milvus-m32-ef100-rep3-shard1`
""")
    
    st.markdown("---")
    
    # Monitoring & Debugging
    st.markdown("## Monitoring & Debugging")
    st.markdown("""
### Watch Running Jobs
```bash
# List all benchmark jobs
kubectl get jobs -n marco -l "job-name" | grep vdb-

# Watch pods in real-time
kubectl get pods -n marco -w

# Get job status
kubectl describe job/vdb-milvus-1 -n marco
```

### View Logs
```bash
# Follow logs of a running job
kubectl logs -n marco job/vdb-milvus-1 -f

# Get last 100 lines
kubectl logs -n marco job/vdb-milvus-1 --tail=100

# View logs of a specific pod
kubectl logs -n marco vdb-milvus-1-xxxxx

# View local benchmark log
tail -f Benchmark/archive/logs/run_all.log
```

### Check Database Status
```bash
# Milvus pods
kubectl get pods -n marco -l app.kubernetes.io/instance=milvus

# Weaviate pods
kubectl get pods -n marco -l app.kubernetes.io/name=weaviate

# Milvus query node logs
kubectl logs -n marco deployment/milvus-querynode -f

# Weaviate logs
kubectl logs -n marco weaviate-0 -f
```

### Resource Monitoring
```bash
# CPU/Memory usage
kubectl top pods -n marco

# Node resources
kubectl top nodes

# Describe pod for detailed resource info
kubectl describe pod vdb-milvus-1-xxxxx -n marco
```

### Emergency Stop
```bash
# Stop all benchmarks and cleanup
bash Benchmark/scripts/stop_and_clean.sh

# Or manually:
# Kill local scripts
pkill -f run_all_and_cleanup
pkill -f run_config_matrix

# Delete all benchmark jobs
kubectl delete jobs -n marco -l job-name --all
kubectl delete jobs -n marco $(kubectl get jobs -n marco -o name | grep vdb-)
```
""")
    
    st.markdown("---")
    
    # Viewing Results
    st.markdown("## Viewing Results (Streamlit UI)")
    st.markdown("""
### Available Pages
| Page | Description |
|------|-------------|
| **Concurrent Performance** | Main analysis page with 8 chart types |
| **Results** | Raw benchmark results with filtering |
| **QPS Recall** | QPS vs Recall tradeoff analysis |
| **Streaming** | Streaming ingestion benchmarks |
| **Tables** | Tabular comparison of results |

### Chart Types (Concurrent Performance Page)
1. **QPS vs Latency** - Line chart showing QPS/latency tradeoff
2. **QPS vs Concurrency** - Performance scaling with concurrency
3. **Peak QPS Comparison** - Direct side-by-side bar chart (common configs only)
4. **QPS vs EF Scatter** - Peak QPS vs EF line chart
5. **QPS Distribution (Box)** - Box plot comparing databases
6. **QPS Distribution (Violin)** - Full distribution shape
7. **Latency Distribution (Violin)** - Latency distribution comparison
8. **EF vs QPS Heatmap** - Color-coded EF impact matrix

**Toggle Options:**
- **Show point labels**: Display concurrency levels on data points (off by default to reduce clutter)

### Smart Filters
The sidebar includes smart filters for managing large result sets:
- **Batch** - Filter by test batch (SINGLE, DISTRIBUTED, SHARDED-1M, etc.)
- **Fine-tune Selection** - Filter by database configuration
- **EF Range** - Low (≤150), Medium (151-300), High (301-600), Very High (>600)
""")
    
    st.markdown("---")
    
    # Common K8s Commands
    st.markdown("## Common Kubernetes Commands")
    st.markdown("""
### Pod Management
```bash
# List all pods in namespace
kubectl get pods -n marco

# Watch pods (real-time  updates)
kubectl get pods -n marco -w

# Get pod details
kubectl describe pod POD_NAME -n marco

# Get pod logs
kubectl logs POD_NAME -n marco

# Follow logs
kubectl logs -f POD_NAME -n marco

# Exec into pod
kubectl exec -it POD_NAME -n marco -- /bin/bash
```

### Job Management
```bash
# List jobs
kubectl get jobs -n marco

# Delete a job
kubectl delete job JOB_NAME -n marco

# Delete all benchmark jobs
kubectl delete jobs -n marco $(kubectl get jobs -n marco -o name | grep vdb-)

# Get job logs
kubectl logs job/JOB_NAME -n marco
```

### Helm Management
```bash
# List releases
helm list -n marco

# Get current values
helm get values RELEASE_NAME -n marco

# Upgrade release
helm upgrade RELEASE_NAME CHART -n marco --set key=value

# Uninstall release
helm uninstall RELEASE_NAME -n marco
```

### Debugging
```bash
# Check events
kubectl get events -n marco --sort-by='.lastTimestamp'

# Check resource usage
kubectl top pods -n marco
kubectl top nodes

# DNS debugging
kubectl run -it --rm debug --image=busybox --restart=Never -n marco -- nslookup milvus.marco.svc.cluster.local

# Network connectivity test
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -n marco -- curl -v http://milvus.marco.svc.cluster.local:19530
```

### Scaling
```bash
# Scale deployment
kubectl scale deployment DEPLOYMENT_NAME --replicas=3 -n marco

# Scale statefulset
kubectl scale statefulset STATEFULSET_NAME --replicas=3 -n marco

# Scale CoreDNS (for high concurrency)
kubectl scale deployment coredns --replicas=4 -n kube-system
```
""")
    
    st.markdown("---")
    
    # Troubleshooting
    st.markdown("## Troubleshooting")
    st.markdown("""
### Benchmark Job Stuck
```bash
# Check pod status
kubectl describe pod -n marco -l job-name=vdb-milvus-1

# Check events
kubectl get events -n marco --field-selector involvedObject.name=vdb-milvus-1

# Check if database is reachable
kubectl logs job/vdb-milvus-1 -n marco --tail=50
```

### Database Connection Failed
```bash
# Verify service exists
kubectl get svc -n marco

# Test DNS resolution
kubectl run -it --rm debug --image=busybox -n marco -- nslookup milvus.marco.svc.cluster.local

# Test port connectivity
kubectl run -it --rm debug --image=curlimages/curl -n marco -- curl -v telnet://milvus.marco.svc.cluster.local:19530
```

### High Latency at High Concurrency
1. **Scale CoreDNS** - DNS can become a bottleneck:
   ```bash
   kubectl scale deployment coredns --replicas=4 -n kube-system
   ```

2. **Check resource limits** - Ensure pods have sufficient CPU/memory:
   ```bash
   kubectl top pods -n marco
   ```

3. **Check database scaling** - Ensure replicas are running:
   ```bash
   kubectl get pods -n marco | grep -E "(milvus|weaviate)"
   ```

### Streamlit UI Errors
- **FileNotFoundError for dbPrices.json**: Create empty file:
  ```bash
  echo "{}" > Benchmark/res/Batch/dbPrices.json
  ```

- **Module not found (statsmodels)**: Charts use built-in methods, no extra install needed.

### Cleanup Stale Jobs
```bash
# Delete all completed jobs
kubectl delete jobs -n marco --field-selector status.successful=1

# Delete all failed jobs
kubectl delete jobs -n marco --field-selector status.failed=1

# Nuclear option - delete all
kubectl delete jobs -n marco --all
```
""")
    
    st.markdown("---")
    
    # Test Process Details
    st.markdown("## Benchmark Test Process")
    st.markdown("""
The test is divided into 3 sub-processes:

### Part 1 - Load (Insert + Optimize)
- (1) Use a single process to perform serial inserts until all data is inserted, and record the time taken as **insert_duration**.
- (2) For most vector databases, index construction requires additional time to optimize to achieve an optimal state, and record the time taken as **optimize_duration**.
- (3) **Load_duration (insert_duration + optimize_duration)** can be understood as the time from the start of insertion until the database is ready to query.
    - load_duration can serve as a reference for the insert capability of a vector database to some extent. However, it should be noted that some vector databases may perform better under **concurrent insert operations**.

### Part 2 - Serial Search Test
- (1) Use a single process to perform serial searches, record the results and time taken for each search, and calculate **recall** and **latency**.
- (2) **Recall**: For vector databases, most searches are approximately nearest neighbor (ANN) searches rather than perfectly accurate results. In production environments, commonly targeted recall rates are 0.9 or 0.95.
    - Note that there is a **trade-off** between **accuracy** and **search performance**. By adjusting parameters, it is possible to sacrifice some accuracy in exchange for better performance. We recommend comparing performance while ensuring that the recall rates remain reasonably close.
- (3) **Latency**: **p99** rather than average. **latency_p99** focuses on **the slowest 1% of requests**. In many high-demand applications, ensuring that most user requests stay within acceptable latency limits is critical, whereas **latency_avg** can be skewed by faster requests.
    - **serial_latency** can serve as a reference for a database's search capability to some extent. However, serial_latency is significantly affected by network conditions. We recommend running the test client and database server within the same local network.

### Part 3 - Concurrent Search Test
- (1) Create multiple processes, each perform serial searches independently to test the database's **maximum throughput (max-qps)**.
- (2) Since different databases may reach peak throughput under different conditions, we conduct multiple test rounds. The number of processes **starts at 1 by default and gradually increases up to 512**, with each test group running for **30 seconds**.
    - Detailed latency and QPS metrics at different concurrency levels can be viewed on the <a href="concurrent" target="_self">Concurrent Performance</a> page.
    - The highest recorded QPS value from these tests will be selected as the final max-qps.
""", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Results Directory Structure
    st.markdown("## Results Directory Structure")
    st.markdown("""
```
Benchmark/
├── res/
│   └── Batch/
│       ├── BATCH_ID_1/
│       │   └── json/
│       │       ├── result_milvus_m32_ef100_*.json
│       │       └── result_weaviate_m32_ef100_*.json
│       └── BATCH_ID_2/
│           └── json/
├── archive/
│   └── logs/
│       └── run_all.log
└── scripts/
    ├── config.sh
    ├── run_all_nohup.sh
    ├── run_all_and_cleanup.sh
    ├── run_config_matrix.sh
    └── stop_and_clean.sh
```
""")
    
    st.markdown("---")
    
    # Key Metrics Summary
    st.markdown("## Key Metrics Summary")
    st.markdown("""
| Metric | Description | Target |
|--------|-------------|--------|
| **QPS** | Queries per second (throughput) | Maximize |
| **Recall** | Search accuracy | 0.9-0.95 for production |
| **Latency p99** | 99th percentile response time | Minimize (focus on worst 1%) |
| **Load Duration** | Time to insert + optimize all data | - |

**Trade-off**: Higher recall = more accurate results but slower performance. Tune HNSW parameters (M, EF) to balance accuracy and speed.

**HNSW Parameters:**
- **M**: Connections per layer (16-64 typical)
- **EF / ef-search**: Candidate list size during search (100-500 typical)
- **EF_CONSTRUCTION**: Candidate list size during  index build (256-512 typical)
""")
    
