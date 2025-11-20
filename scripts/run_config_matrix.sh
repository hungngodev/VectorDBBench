#!/usr/bin/env bash

# Generate and run many benchmark jobs from parameter matrices (no YAML needed).
# Adjust the arrays below to try as many configs as you like. Jobs run sequentially per DB.

set -euo pipefail

NS=${NS:-marco}
IMG=${IMG:-hungngodev/vectordbbench:latest}
DATA_DIR=${DATA_DIR:-/opt/vdb/datasets}
# If set, mount a host/NFS path into the pod for datasets to avoid re-downloading each job.
# Example: HOST_DATA_DIR=/mnt/nfs/home/hmngo/work1/hmngo/datasets
HOST_DATA_DIR=${HOST_DATA_DIR:-}
# If set, mount a host/NFS path for results so outputs persist and are shared.
# Example: HOST_RESULTS_DIR=/mnt/nfs/home/hmngo/work1/hmngo/vdb_results
HOST_RESULTS_DIR=${HOST_RESULTS_DIR:-}
# Protobuf version for Vald (must match gencode major); upgrade inside job if needed.
PROTOBUF_VERSION=${PROTOBUF_VERSION:-6.31.1}
# Resource requests/limits for benchmark jobs (fits 72 CPU / ~188Gi nodes)
CPU=${CPU:-16}
MEM=${MEM:-64Gi}

run_job() {
  local job="$1"; shift
  local cmd="$*"
  echo "-- job/${job}"
  kubectl -n "$NS" delete job "$job" --ignore-not-found
  cat <<EOF | kubectl -n "$NS" apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: ${job}
spec:
  template:
    spec:
      containers:
      - name: bench
        image: ${IMG}
        command: ["bash","-lc","cd /opt/vdb && ./prepare_datasets.sh ${DATA_DIR} && ${cmd}"]
        resources:
          requests:
            cpu: "${CPU}"
            memory: "${MEM}"
          limits:
            cpu: "${CPU}"
            memory: "${MEM}"
        volumeMounts:
        - name: datasets
          mountPath: ${DATA_DIR}
        - name: results
          mountPath: /opt/vdb/vectordb_bench/results
      restartPolicy: Never
      volumes:
$(if [[ -n "${HOST_DATA_DIR}" ]]; then
  printf "      - name: datasets\n        hostPath:\n          path: %s\n" "${HOST_DATA_DIR}"
else
  printf "      - name: datasets\n        emptyDir: {}\n"
fi)
$(if [[ -n "${HOST_RESULTS_DIR}" ]]; then
  printf "      - name: results\n        hostPath:\n          path: %s\n" "${HOST_RESULTS_DIR}"
else
  printf "      - name: results\n        emptyDir: {}\n"
fi)
EOF
  kubectl -n "$NS" wait --for=condition=complete --timeout=2h "job/${job}" || true
  kubectl -n "$NS" logs -f "job/${job}" || true
}

echo "Running matrix sweeps in namespace: $NS with image: $IMG"

# Milvus matrix (trimmed for quick test)
milvus_m=(24)
milvus_ef=(256)
mid=1
for m in "${milvus_m[@]}"; do
  for ef in "${milvus_ef[@]}"; do
    job="vdb-milvus-${mid}"
    run_job "$job" bash -lc "cd /opt/vdb && \
      vectordbbench milvushnsw \
        --db-label k8s-milvus --task-label milvus-m${m}-ef${ef} \
        --case-type Performance768D1M --uri http://milvus.marco.svc.cluster.local:19530 \
        --m ${m} --ef-search ${ef} --ef-construction ${ef} \
        --k 10 --drop-old --load --search-serial --search-concurrent"
    mid=$((mid+1))
  done
done

# Qdrant matrix (trimmed for quick test; drop_old/load enabled by default)
qdrant_m=(24)
qdrant_ef=(256)
qid=1
for m in "${qdrant_m[@]}"; do
  for ef in "${qdrant_ef[@]}"; do
    job="vdb-qdrant-${qid}"
    run_job "$job" bash -lc "cd /opt/vdb && \
      vectordbbench qdrantlocal \
        --db-label k8s-qdrant --task-label qdrant-m${m}-ef${ef} \
        --case-type Performance768D1M --url http://qdrant.marco.svc.cluster.local:6333 \
        --metric-type COSINE --on-disk False --m ${m} --ef-construct ${ef} --hnsw-ef ${ef} --k 10 \
        --drop-old --load --search-serial --search-concurrent"
    qid=$((qid+1))
  done
done

# Weaviate matrix (trimmed for quick test; no auth)
weav_m=(24)
weav_ef=(256)
wid=1
for m in "${weav_m[@]}"; do
  for ef in "${weav_ef[@]}"; do
    job="vdb-weaviate-${wid}"
    run_job "$job" bash -lc "cd /opt/vdb && \
      vectordbbench weaviate \
        --db-label k8s-weaviate --task-label weaviate-m${m}-ef${ef} \
        --case-type Performance768D1M --url http://weaviate.marco.svc.cluster.local \
        --no-auth --m ${m} --ef-construction ${ef} --ef ${ef} --metric-type COSINE --k 10 \
        --drop-old --load --search-serial --search-concurrent"
    wid=$((wid+1))
  done
done

# Vald matrix (trimmed for quick test; requires protobuf runtime pinned)
vald_num=(12)
vid=1
for num in "${vald_num[@]}"; do
  job="vdb-vald-${vid}"
  run_job "$job" bash -lc "cd /opt/vdb && \
    python -m pip install -U protobuf==${PROTOBUF_VERSION} >/tmp/pip-vald.log 2>&1 && \
    vectordbbench vald \
      --db-label k8s-vald --task-label vald-num${num} \
      --case-type Performance768D1M --host vald-lb-gateway.marco.svc.cluster.local --port 8081 \
      --use-tls False --batch-size 128 --metric-type COSINE --num ${num} --min-num 1 \
      --wait-for-sync-seconds 10 --k 10 --drop-old --load --search-serial --search-concurrent"
  vid=$((vid+1))
done
