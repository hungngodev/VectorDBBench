#!/usr/bin/env bash

# Run a quick verification test for Milvus and Weaviate in parallel.
# Configured for 1 client concurrency.

set -euo pipefail

NS=${NS:-marco}
IMG=${IMG:-hungngodev/vectordbbench:latest}
DATA_DIR=${DATA_DIR:-/opt/vdb/datasets}
HOST_DATA_DIR=${HOST_DATA_DIR:-}
HOST_RESULTS_DIR=${HOST_RESULTS_DIR:-}
CPU=${CPU:-16}
MEM=${MEM:-64Gi}

run_job() {
  local job="$1"; shift
  local cmd="$*"
  echo "-- Launching job/${job}..."
  kubectl -n "$NS" delete job "$job" --ignore-not-found >/dev/null 2>&1
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
  # Wait for job to complete (will be run in background)
  echo "-- Waiting for job/${job} to complete..."
  kubectl -n "$NS" wait --for=condition=complete --timeout=2h "job/${job}"
}

echo "Starting Parallel Verification (Concurrency=1)"
echo "Logs will be streamed to verify_milvus.log and verify_weaviate.log"

# Milvus Job
(
  run_job "verify-milvus" bash -lc "cd /opt/vdb && \
    vectordbbench milvushnsw \
      --db-label k8s-milvus --task-label verify-milvus \
      --case-type Performance768D1M --uri http://milvus.marco.svc.cluster.local:19530 \
      --m 16 --ef-search 128 --ef-construction 128 \
      --concurrency-duration 60 \
      --drop-old --load --search-serial --search-concurrent \
      --num-concurrency 1"
) > verify_milvus.log 2>&1 &
PID_MILVUS=$!

# Weaviate Job
(
  run_job "verify-weaviate" bash -lc "cd /opt/vdb && \
    vectordbbench weaviate \
      --db-label k8s-weaviate --task-label verify-weaviate \
      --case-type Performance768D1M --url http://weaviate.marco.svc.cluster.local \
      --no-auth --m 16 --ef-construction 128 --ef 128 --metric-type COSINE \
      --concurrency-duration 60 \
      --drop-old --load --search-serial --search-concurrent \
      --num-concurrency 1"
) > verify_weaviate.log 2>&1 &
PID_WEAVIATE=$!

echo "Jobs launched."
echo "Milvus PID: $PID_MILVUS"
echo "Weaviate PID: $PID_WEAVIATE"
echo "Monitor with: tail -f verify_milvus.log verify_weaviate.log"

wait $PID_MILVUS
wait $PID_WEAVIATE

echo "Verification completed."
