# VectorDBBench

Benchmark framework for comparing Milvus and Weaviate vector databases on Kubernetes.

## Quick Start

### 1. Install

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

### 3. Prepare Dataset

Download datasets to shared NFS storage:

```bash
./prepare_datasets.sh /mnt/nfs/shared/datasets
```

### 4. Run Benchmarks

```bash
export NS=marco
export HOST_DATA_DIR=/mnt/nfs/shared/datasets
export HOST_RESULTS_DIR=/mnt/nfs/shared/results
export CASE_TYPE=Performance768D1M  # or Performance768D100K

./scripts/run_config_matrix.sh
```

### 5. Analyze Results

```bash
python scripts/aggregate_results.py --dir /mnt/nfs/shared/results --output analysis/all_results.csv
cd analysis && python generate_figures.py
```

---

## UMass Swarm Cluster Setup

### SSH Access

```bash
ssh your_username@swarm056.cs.umass.edu
```

### Kubernetes Access

```bash
export KUBECONFIG=/path/to/kubeconfig
kubectl config use-context swarm
kubectl get pods -n marco
```

### Database Deployments

Databases are deployed in the `marco` namespace:

| Database | Service URL | Port | Configuration |
|----------|-------------|------|---------------|
| Milvus | `milvus.marco.svc.cluster.local` | 19530 | Distributed architecture, **1 querynode** |
| Weaviate | `weaviate.marco.svc.cluster.local` | 8080 | **Single monolithic instance** |

> **Note**: Although Milvus uses a distributed architecture (separate coordinator, data node, index node, query node), we run with **1 querynode** for fair comparison with Weaviate's single instance.

### Raft Scaling Experiment

In the Raft scaling experiment, Weaviate was deployed as a **3-node Raft cluster** while Milvus remained at 1 querynode.

**Key findings**:
- Weaviate's Raft consensus provides **fault tolerance only**, not search parallelism
- Each search query is still processed by a single node
- **Load balancing must be implemented separately** (e.g., via Kubernetes Ingress or a custom load balancer)
- Milvus's querynode can be independently scaled for search parallelism

### Modifying Database Configurations

**Milvus** (Helm values):
```bash
# View current config
helm get values milvus -n marco

# Update querynode replicas (NOTE: kept at 1 for fair comparison)
helm upgrade milvus milvus/milvus -n marco --set queryNode.replicas=1
```

**Weaviate** (Helm values):
```bash
# View current config
helm get values weaviate -n marco

# Update replica count (Raft consensus for fault tolerance)
helm upgrade weaviate semitechnologies/weaviate -n marco --set replicas=3
```

### HNSW Index Parameters

To modify HNSW parameters (M, efConstruction, efSearch), edit the benchmark scripts:

```bash
# In scripts/run_config_matrix.sh
M_VALUES="4 8 16 32 64 128"
EF_VALUES="128 192 256 384 512 768"
```

### Monitoring

```bash
# Check pod status
kubectl get pods -n marco -w

# View logs
kubectl logs -f deployment/milvus-querynode -n marco

# Resource usage
kubectl top pods -n marco
```

---

## Results

Benchmark results and analysis are in the `analysis/` directory:
- `RESEARCH_REPORT_v2.md` - Performance comparison report
- `all_results_*.csv` - Raw benchmark data
- `*.png` - Visualization figures

---

## Scripts Reference

### Main Benchmark Script

**`scripts/run_all_nohup.sh`** - Run full benchmark detached (recommended):
```bash
HOST_DATA_DIR=/mnt/nfs/shared/datasets \
HOST_RESULTS_DIR=/mnt/nfs/shared/results \
CPU=16 MEM=64Gi \
bash scripts/run_all_nohup.sh
```
Logs written to `run_all.log`. Monitor with `tail -f run_all.log`.

### Configuration Script

**`scripts/run_config_matrix.sh`** - Core benchmark runner with configurable parameters:

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `NS` | `marco` | Kubernetes namespace |
| `HOST_DATA_DIR` | (empty) | Path to cached datasets on NFS |
| `HOST_RESULTS_DIR` | (empty) | Path to save results on NFS |
| `CASE_TYPE` | `Performance768D1M` | Benchmark case (`Performance768D100K`, `Performance768D1M`) |
| `K` | `100` | Number of nearest neighbors to retrieve |
| `EF_CONSTRUCTION` | `360` | HNSW efConstruction (fixed for index quality) |
| `NUM_CONCURRENCY` | `1,2,4,8,16,32` | Client concurrency levels |
| `CONCURRENCY_DURATION` | `60` | Seconds per concurrency level |
| `CPU` / `MEM` | `16` / `64Gi` | Pod resource limits |

**HNSW Parameter Matrices** (edit in script):
```bash
# Milvus/Weaviate: M and efSearch values
milvus_m=(4 8 16 32 64 128 256)
milvus_ef=(128 192 256 384 512 640 768 1024)

weav_m=(4 8 16 32 64 128 256)
weav_ef=(128 192 256 384 512 640 768 1024)
```

### Other Scripts

**`scripts/run_all_and_cleanup.sh`**
Orchestrates the entire benchmark pipeline:
1. Runs `run_config_matrix.sh` to execute all benchmark jobs
2. Calls `aggregate_results.py` to combine JSON results into CSV
3. Cleans up individual JSON files after aggregation

```bash
NS=marco RESULT_ROOT=/mnt/nfs/shared/results OUTPUT=all_results.csv \
bash scripts/run_all_and_cleanup.sh
```

---

**`scripts/aggregate_results.py`**
Combines individual JSON result files into a single CSV for analysis.

```bash
python scripts/aggregate_results.py --root /mnt/nfs/shared/results --output all_results.csv
```

Output columns: `db`, `task_label`, `concurrency`, `qps`, `latency_p99`, `recall`, `load_duration`, etc.

---

**`scripts/cleanup_bench.sh`**
Deletes all benchmark jobs and pods (prefixed with `vdb-` or `vectordb-bench`) from the cluster.

```bash
NS=marco bash scripts/cleanup_bench.sh
```

---

**`scripts/stop_and_clean.sh`**
Emergency stop: kills local benchmark scripts AND deletes all Kubernetes jobs in `marco` namespace.

```bash
bash scripts/stop_and_clean.sh
```
kubectl -n marco run manual-cleanup2 --rm -it --restart=Never --image=busybox   --overrides='{"spec":{"containers":[{"name":"cleanup","image":"busybox","command":["sh","-c","rm -rf /results/QdrantLocal/*.json /results/Vald/*.json && echo Done"],"volumeMounts":[{"name":"results","mountPath":"/results"}]}],"volumes":[{"name":"results","hostPath":{"path":"/mnt/nfs/home/hmngo/work1/hmngo/vdb_results"}}],"restartPolicy":"Never"}}'