#!/usr/bin/env bash

# Generate and run many benchmark jobs from parameter matrices (no YAML needed).
# Adjust the arrays below to try as many configs as you like. Jobs run sequentially per DB.

set -euo pipefail

NS=${NS:-marco}
IMG=${IMG:-hungngodev/vectordbbench:latest}
DATA_DIR=${DATA_DIR:-/opt/vdb/datasets}
HOST_DATA_DIR=${HOST_DATA_DIR:-/mnt/nfs/home/hmngo/work1/hmngo/datasets}
HOST_RESULTS_DIR=${HOST_RESULTS_DIR:-/mnt/nfs/home/hmngo/work1/hmngo/vdb_results}
# Protobuf version for Vald (must match gencode major); upgrade inside job if needed.
PROTOBUF_VERSION=${PROTOBUF_VERSION:-6.31.1}
# Resource requests/limits for benchmark jobs (fits 72 CPU / ~188Gi nodes)
CPU=${CPU:-16}
MEM=${MEM:-64Gi}
# Vald tuning (timeouts/concurrency) to avoid empty results/timeouts under heavy load.
VALD_WAIT_SECONDS=${VALD_WAIT_SECONDS:-60}
VALD_TIMEOUT=${VALD_TIMEOUT:-300}
VALD_TIMEOUT=${VALD_TIMEOUT:-300}
VALD_CONCURRENCIES=${VALD_CONCURRENCIES:-"1"}
# Concurrency list for client scaling (default: doubling sequence)
NUM_CONCURRENCY=${NUM_CONCURRENCY:-1,2,4,8,16,32}
CONCURRENCY_DURATION=${CONCURRENCY_DURATION:-60}
CASE_TYPE=${CASE_TYPE:-Performance768D1M}
# Weaviate replication factor for fault tolerance (data copied to N nodes)
WEAVIATE_REPLICATION_FACTOR=${WEAVIATE_REPLICATION_FACTOR:-1}
# Weaviate sharding count for parallel query execution (data split across N nodes)
WEAVIATE_SHARDING_COUNT=${WEAVIATE_SHARDING_COUNT:-3}
K=${K:-100}
# HNSW efConstruction: Fixed high value for quality graph (do not vary with efSearch)
EF_CONSTRUCTION=${EF_CONSTRUCTION:-360}

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

# Milvus matrix (expanded for diverse testing)
ENABLE_MILVUS=${ENABLE_MILVUS:-true}
if [[ "${ENABLE_MILVUS}" == "true" ]]; then
  # Milvus: single config for quick test (change back for full matrix)
  milvus_m=(32)
  milvus_ef=(256)
  mid=1
  for m in "${milvus_m[@]}"; do
    for ef in "${milvus_ef[@]}"; do
      job="vdb-milvus-${mid}"
      run_job "$job" bash -lc "cd /opt/vdb && \
        vectordbbench milvushnsw \
          --db-label k8s-milvus --task-label milvus-m${m}-ef${ef} \
          --case-type ${CASE_TYPE} --uri http://milvus.marco.svc.cluster.local:19530 \
          --m ${m} --ef-search ${ef} --ef-construction ${EF_CONSTRUCTION} \
          --concurrency-duration ${CONCURRENCY_DURATION} --k ${K} \
          --drop-old --load --search-serial --search-concurrent \
          --num-concurrency ${NUM_CONCURRENCY}"
      mid=$((mid+1))
    done
  done
fi

# Qdrant matrix (trimmed for quick test; drop_old/load enabled by default)
ENABLE_QDRANT=${ENABLE_QDRANT:-true}
if [[ "${ENABLE_QDRANT}" == "true" ]]; then
  # Qdrant: 6x10 = 60 configs
  qdrant_m=(4 8 16 32 64 128)
  qdrant_ef=(64 96 128 192 256 384 512 640 768 1024)
  DROP_OLD_QDRANT=${DROP_OLD_QDRANT:-true}
  qid=1
  for m in "${qdrant_m[@]}"; do
    for ef in "${qdrant_ef[@]}"; do
      job="vdb-qdrant-${qid}"
      qdrant_drop_flag="--drop-old"
      [[ "${DROP_OLD_QDRANT}" == "false" ]] && qdrant_drop_flag="--skip-drop-old"
      run_job "$job" bash -lc "cd /opt/vdb && \
        vectordbbench qdrantlocal \
          --db-label k8s-qdrant --task-label qdrant-m${m}-ef${ef} \
          --case-type ${CASE_TYPE} --url http://qdrant.marco.svc.cluster.local:6333 \
          --metric-type COSINE --on-disk False --m ${m} --ef-construct ${ef} --hnsw-ef ${ef} \
          --concurrency-duration ${CONCURRENCY_DURATION} --k ${K} \
          ${qdrant_drop_flag} --load --search-serial --search-concurrent \
          --num-concurrency ${NUM_CONCURRENCY}"
      qid=$((qid+1))
    done
  done
fi

# Weaviate matrix (expanded for diverse testing; no auth)
ENABLE_WEAVIATE=${ENABLE_WEAVIATE:-true}
if [[ "${ENABLE_WEAVIATE}" == "true" ]]; then
  # Weaviate: single config for quick test (change back for full matrix)
  weav_m=(32)
  weav_ef=(256)
  wid=1
  for m in "${weav_m[@]}"; do
    for ef in "${weav_ef[@]}"; do
      job="vdb-weaviate-${wid}"
      run_job "$job" bash -lc "cd /opt/vdb && \
        vectordbbench weaviate \
          --db-label k8s-weaviate --task-label weaviate-m${m}-ef${ef} \
          --case-type ${CASE_TYPE} --url http://weaviate.marco.svc.cluster.local \
          --no-auth --m ${m} --ef-construction ${EF_CONSTRUCTION} --ef ${ef} --metric-type COSINE \
          --replication-factor ${WEAVIATE_REPLICATION_FACTOR} \
          --sharding-count ${WEAVIATE_SHARDING_COUNT} \
          --concurrency-duration ${CONCURRENCY_DURATION} --k ${K} \
          --drop-old --load --search-serial --search-concurrent \
          --num-concurrency ${NUM_CONCURRENCY}"
      wid=$((wid+1))
    done
  done
fi

# Vald matrix (trimmed for quick test; requires protobuf runtime pinned)
ENABLE_VALD=${ENABLE_VALD:-true}
if [[ "${ENABLE_VALD}" == "true" ]]; then
  # Vald: 10 configs
  vald_num=(10 20 40 60 80 100 150 200 300 400)
  vid=1
  for num in "${vald_num[@]}"; do
    job="vdb-vald-${vid}"
    run_job "$job" bash -lc "cd /opt/vdb && \
      python -m pip install -U protobuf==${PROTOBUF_VERSION} >/tmp/pip-vald.log 2>&1 && \
      vectordbbench vald \
        --db-label k8s-vald --task-label vald-num${num} \
        --case-type ${CASE_TYPE} --host vald-lb-gateway.marco.svc.cluster.local --port 8081 \
        --use-tls False --batch-size 128 --metric-type COSINE --num ${num} --min-num 1 \
        --wait-for-sync-seconds ${VALD_WAIT_SECONDS} --timeout ${VALD_TIMEOUT} \
        --concurrency-duration ${CONCURRENCY_DURATION} --k ${K} \
        --drop-old --load --search-serial --search-concurrent \
        --num-concurrency ${NUM_CONCURRENCY}"
    vid=$((vid+1))
  done
fi
