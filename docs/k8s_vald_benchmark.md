# Kubernetes Benchmark Playbook (Milvus • Qdrant • Weaviate • Vald)

This guide wires VectorDBBench into a Kubernetes cluster so you can benchmark Milvus, Qdrant, Weaviate, and Vald under a single harness. It reflects the new Vald adapter that ships with this repository.

## 1. Architecture Overview

```
                     +----------------------+
                     |  Benchmark Pod       |
                     |  (vectordb-bench)    |
                     +----------+-----------+
                                |
                     Queries / Metrics collection
                                |
    ---------------------------------------------------------------
    |                |                 |                         |
    |                |                 |                         |
+---v----+     +-----v----+     +------v-----+           +-------v------+
| Milvus |     | Qdrant   |     | Weaviate   |           | Vald Gateway |
| gRPC   |     | REST/gRPC|     | REST/GQL   |           | REST/gRPC    |
+--------+     +----------+     +------------+           +--------------+
  Service        Service           Service                    Service
  milvus-svc     qdrant-svc        weaviate-svc               vald-gateway
  port 19530     port 6333         port 8080                  port 8081
```

- **VectorDBBench** stays in control of dataset prep, workload execution, and metric collection.
- Each backend runs inside the Kubernetes cluster and exposes a single service endpoint.
- The benchmark pod issues inserts/searches over REST/gRPC and records throughput, latency, recall, etc.

## 2. Vald Support in VectorDBBench

The repository now ships a native Vald adapter:

- `vectordb_bench/backend/clients/vald/vald_local.py` implements the `VectorDB` interface (load, search, optimize).
- `vectordb_bench/backend/clients/vald/config.py` maps YAML/CLI options into Vald connection and search configs.
- `vectordb_bench/backend/clients/vald/cli.py` adds a `Vald` CLI command (`vectordbbench Vald ...`).
- `vectordb_bench/config-files/vald_sample_config.yml` and `k8s_local_fourdb.yml` show ready-to-use configurations. The latter runs the built-in `Performance768D1M` case (Cohere 1M vectors, 768 dim) so every backend sees the same dataset and distance metric. Use `./prepare_datasets.sh /mnt/nfs/home/hmngo/scratch/vectordb_bench/dataset` (or another target) to download the dataset to durable storage before benchmarking.

Install dependencies with:

```bash
pip install -e '.[vald]'
```

Or grab everything (Milvus/Qdrant/Weaviate/Vald, etc.):

```bash
pip install -e '.[all]'
```

Run a quick sanity check against a Vald gateway:

```bash
vectordbbench Vald --host localhost --port 8081 --case-type Performance768D10K
```

Configuration files can be passed with `--config-file` or dropped into `vectordb_bench/config-files/`.

## 3. Deploy Vector Databases on Kubernetes

### Helm Repositories

```bash
helm repo add milvus https://zilliztech.github.io/milvus-helm/
helm repo add qdrant https://qdrant.github.io/helm
helm repo add semitechnologies https://weaviate.github.io/helm
helm repo add vald https://vald.vdaas.org/charts
helm repo update
```

### Install the Services

```bash
# Milvus (cluster mode)
helm install milvus milvus/milvus --set cluster.enabled=true

# Qdrant
helm install qdrant qdrant/qdrant

# Weaviate
helm install weaviate semitechnologies/weaviate

# Vald (gateway + agent defaults)
helm install vald vald/vald
```

Check that services are available:

```bash
kubectl get svc
```

You should see (namespace defaults shown):

| Service      | Port  | Protocol |
|--------------|-------|----------|
| `milvus-svc` | 19530 | gRPC     |
| `qdrant-svc` | 6333  | HTTP/gRPC|
| `weaviate-svc` | 8080 | HTTP     |
| `vald-gateway` | 8081 | HTTP/gRPC|

Expose them with `ClusterIP` or `LoadBalancer` depending on your environment.

## 4. Benchmark Pod Template

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: vectordb-bench
spec:
  restartPolicy: Never
  containers:
    - name: bench
      image: python:3.11-slim
      command:
        - bash
        - -lc
        - |
          pip install vectordb-bench[vald];
          vectordbbench batchcli --batch-config-file /bench/config/k8s_local_fourdb.yml
      volumeMounts:
        - name: bench-config
          mountPath: /bench/config
  volumes:
    - name: bench-config
      configMap:
        name: bench-config
```

Create the ConfigMap from the new sample config:

```bash
kubectl create configmap bench-config \
  --from-file=vectordb_bench/config-files/k8s_local_fourdb.yml
```

Launch the pod:

```bash
kubectl apply -f kube/bench-pod.yaml
```

Tail the logs to watch progress:

```bash
kubectl logs -f pod/vectordb-bench
```

Use the CLI interactively if you prefer:

```bash
kubectl exec -it vectordb-bench -- bash
vectordbbench Vald --config-file /bench/config/vald_sample_config.yml
```

## 5. Metrics to Track

VectorDBBench automatically records:

- Insert throughput (vectors/sec) and load duration
- Search QPS (serial + concurrent workloads)
- Latency (average, p95, p99)
- Recall@k (computed from ground truth)

Additional considerations:

- Track resource consumption (`kubectl top pod`, Prometheus/Grafana, etc.)
- Note index build behaviour: Vald relies on background synchronization; Milvus/Qdrant/Weaviate may expose explicit index build stats.
- Record cluster sizing (node types, CPU/memory limits) for fair comparisons.

## 6. Best Practices for Fair Comparisons

- Use identical datasets and ground-truth files (e.g. ANN-Benchmarks SIFT/Deep/BIGANN).
- Keep similarity metrics aligned (set all engines to cosine or L2).
- Warm caches before timing queries (perform a preliminary search pass).
- Run each case multiple times and average p95/p99 latencies.
- Document index/search knobs (e.g., Milvus `nprobe`, Qdrant `hnsw_ef`, Weaviate `ef`, Vald `epsilon`) so trade-offs are transparent.
- Fix Kubernetes resources (same node flavors, no auto-scaling) when comparing engines.

With this setup the new Vald adapter runs alongside Milvus, Qdrant, and Weaviate under one harness, making it easy to keep the workload and metrics identical across all four systems.
