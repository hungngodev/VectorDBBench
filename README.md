# VectorDBBench on Kubernetes

A comprehensive framework for benchmarking vector databases (Milvus, Weaviate, Qdrant, Vald) in distributed Kubernetes environments. This repository contains the source code, benchmark scripts, and analysis tools used to produce rigorous performance reports.

## Prerequisites

- **Kubernetes Cluster**: Version 1.25+ (verified on 1.31)
- **Shared Storage (NFS)**: Highly recommended for sharing datasets and results between nodes.
- **Python 3.10+**: For local analysis scripts.
- **Docker**: To build the benchmark image.
- **Poetry**: For dependency management.

## 1. Setup

### Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/hungngodev/VectorDBBench.git
cd VectorDBBench
pip install poetry
poetry install
```

### Build Docker Image

Build the benchmark runner image and push it to your registry (or use the pre-built one):

```bash
docker build -t hungngodev/vectordbbench:latest .
docker push hungngodev/vectordbbench:latest
```

## 2. Infrastructure Deployment

Before running benchmarks, you must deploy the target vector databases in your Kubernetes cluster. The scripts verify against the following service URLs by default in the `marco` namespace:

- **Milvus**: `http://milvus.marco.svc.cluster.local:19530`
- **Weaviate**: `http://weaviate.marco.svc.cluster.local:8080` (or `weaviate-0.weaviate-headless:8080`)
- **Qdrant**: `http://qdrant.marco.svc.cluster.local:6333`

Ensure your databases are healthy and accessible from within the cluster.

## 3. Dataset Preparation

To avoid downloading large datasets (1M+ vectors) for every job, download them once to a shared NFS volume:

```bash
# Run locally or on a cluster node with NFS access
./prepare_datasets.sh /mnt/nfs/shared/datasets
```

This will download:
- Cohere 1M (768d)
- SIFT 1M (128d)
- OpenAI 500K (1536d)

## 4. Running Benchmarks

We provide shell scripts in `scripts/` to orchestrate Kubernetes Jobs for parameter sweeps.

### Configure Environment

Edit `scripts/run_config_matrix.sh` or set environment variables:

```bash
export NS=marco                                 # Kubernetes namespace
export IMG=hungngodev/vectordbbench:latest      # Benchmark image
export HOST_DATA_DIR=/mnt/nfs/shared/datasets   # Path to cached datasets
export HOST_RESULTS_DIR=/mnt/nfs/shared/results # Path to save JSON results
export NUM_CONCURRENCY=1,2,4,8,16,32            # Client concurrency levels
export CASE_TYPE=Performance768D1M              # Benchmark case (1M vectors)
```

### Execute Parameter Sweep

Run the full matrix of configurations (M, efConstruction, efSearch):

```bash
# Runs ~100 jobs sequentially per database to test all parameter combinations
./scripts/run_config_matrix.sh
```

### Quick Verification

For a faster sanity check (fewer configs), run:

```bash
./scripts/run_verify_parallel.sh
```

## 5. Analysis & Visualization

After benchmarks complete, results are saved as JSON files in your `HOST_RESULTS_DIR`.

### Aggregate Results

Combine all JSON results into a single CSV for analysis:

```bash
python scripts/aggregate_results.py --dir /mnt/nfs/shared/results --output analysis/all_results.csv
```

### Generate Plots

Create performance visualizations (QPS vs Recall, Latency, etc.):

```bash
cd analysis
python generate_plots.py
```

This will generate figures like:
- `deep_fig1_overview.png`: QPS/Recall distribution
- `deep_fig2_sensitivity.png`: Parameter trade-offs
- `deep_fig3_heatmaps.png`: Scalability heatmaps

## 6. Project Structure

```
├── analysis/               # Analysis scripts and report
│   ├── RESEARCH_REPORT.md  # Final performance report
│   └── generate_plots.py   # Visualization script
├── scripts/                # Kubernetes orchestration scripts
│   ├── run_config_matrix.sh # Main benchmark runner
│   └── aggregate_results.py # Result aggregator
├── vectordb_bench/         # Core benchmark python package
│   ├── backend/            # Database clients and runners
│   └── cli/                # Command-line interface
├── Dockerfile              # Runner image definition
└── prepare_datasets.sh     # Dataset downloader
```

## Troubleshooting

- **Permission Denied**: Ensure the K8s ServiceAccount used by the Job has permissions to `list/get` pods if using auto-discovery, or that the runner can access the database URLs.
- **Timeouts**: If large datasets fail to load, increase `VALD_TIMEOUT` or check database resource limits (CPU/Mem).
- **Empty Results**: Check `HOST_RESULTS_DIR` permissions; the container runs as root by default but NFS might squash permissions.
