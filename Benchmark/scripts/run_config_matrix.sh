#!/usr/bin/env bash


set -euo pipefail


BATCH_ID=${BATCH_ID:-$(date +%Y%m%d-%H%M)}

NS=${NS:-marco}
IMG=${IMG:-hungngodev/vectordbbench:latest}
DATA_DIR=${DATA_DIR:-/opt/vdb/datasets}
HOST_DATA_DIR=${HOST_DATA_DIR:-/mnt/nfs/home/hmngo/work1/hmngo/datasets}
HOST_RESULTS_DIR=${HOST_RESULTS_DIR:-/mnt/nfs/home/hmngo/work1/hmngo/vdb_results}
PROTOBUF_VERSION=${PROTOBUF_VERSION:-6.31.1}
CPU=${CPU:-16}
MEM=${MEM:-64Gi}
VALD_WAIT_SECONDS=${VALD_WAIT_SECONDS:-60}
VALD_TIMEOUT=${VALD_TIMEOUT:-300}
VALD_CONCURRENCIES=${VALD_CONCURRENCIES:-"1"}
NUM_CONCURRENCY=${NUM_CONCURRENCY:-32}
CONCURRENCY_DURATION=${CONCURRENCY_DURATION:-60}
CASE_TYPE=${CASE_TYPE:-Performance768D100K}
REPLICA=${REPLICA:-1}
SHARDING=${SHARDING:-1}
K=${K:-100}
EF_CONSTRUCTION=${EF_CONSTRUCTION:-360}
HNSW_M_VALUES=(${HNSW_M_VALUES:-4 8 16 32 64 128 256})
HNSW_EF_VALUES=(${HNSW_EF_VALUES:-128 192 256 384 512 640 768 1024})

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
        command: ["bash","-lc","cd /opt/vdb && ./Benchmark/prepare_datasets.sh ${DATA_DIR} && ${cmd}"]
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
  echo "Waiting for job/${job} to start..."
  kubectl -n "$NS" wait --for=condition=Ready pod -l job-name="${job}" --timeout=5m
  echo "Waiting for job/${job} to complete..."
  kubectl -n "$NS" wait --for=condition=complete --timeout=2h "job/${job}"
  kubectl -n "$NS" logs "job/${job}" || true
}

echo "Running matrix sweeps in namespace: $NS with image: $IMG"

ENABLE_MILVUS=${ENABLE_MILVUS:-true}
if [[ "${ENABLE_MILVUS}" == "true" ]]; then
  mid=1
  for m in "${HNSW_M_VALUES[@]}"; do
    first_ef_for_m=true
    for ef in "${HNSW_EF_VALUES[@]}"; do
      job="vdb-milvus-${mid}"
      
      if [[ "${first_ef_for_m}" == "true" ]]; then
        load_flags="--drop-old --load"
        first_ef_for_m=false
      else
        load_flags="--skip-drop-old --skip-load"
      fi
      
      run_job "$job" bash -lc "cd /opt/vdb && \
        vectordbbench milvushnsw \
          --db-label k8s-milvus --task-label ${BATCH_ID}-milvus-m${m}-ef${ef} \
          --case-type ${CASE_TYPE} --uri http://milvus.marco.svc.cluster.local:19530 \
          --m ${m} --ef-search ${ef} --ef-construction ${EF_CONSTRUCTION} \
          --num-shards ${SHARDING} --replica-number ${REPLICA} \
          --concurrency-duration ${CONCURRENCY_DURATION} --k ${K} \
          ${load_flags} --search-serial --search-concurrent \
          --num-concurrency ${NUM_CONCURRENCY}"
      mid=$((mid+1))
    done
  done
fi

ENABLE_QDRANT=${ENABLE_QDRANT:-false}
if [[ "${ENABLE_QDRANT}" == "true" ]]; then
  DROP_OLD_QDRANT=${DROP_OLD_QDRANT:-true}
  qid=1
  for m in "${HNSW_M_VALUES[@]}"; do
    for ef in "${HNSW_EF_VALUES[@]}"; do
      job="vdb-qdrant-${qid}"
      qdrant_drop_flag="--drop-old"
      [[ "${DROP_OLD_QDRANT}" == "false" ]] && qdrant_drop_flag="--skip-drop-old"
      run_job "$job" bash -lc "cd /opt/vdb && \
        vectordbbench qdrantlocal \
          --db-label k8s-qdrant --task-label ${BATCH_ID}-qdrant-m${m}-ef${ef} \
          --case-type ${CASE_TYPE} --url http://qdrant.marco.svc.cluster.local:6333 \
          --metric-type COSINE --on-disk False --m ${m} --ef-construct ${ef} --hnsw-ef ${ef} \
          --concurrency-duration ${CONCURRENCY_DURATION} --k ${K} \
          ${qdrant_drop_flag} --load --search-serial --search-concurrent \
          --num-concurrency ${NUM_CONCURRENCY}"
      qid=$((qid+1))
    done
  done
fi

ENABLE_WEAVIATE=${ENABLE_WEAVIATE:-true}
if [[ "${ENABLE_WEAVIATE}" == "true" ]]; then
  wid=1
  for m in "${HNSW_M_VALUES[@]}"; do
    first_ef_for_m=true
    for ef in "${HNSW_EF_VALUES[@]}"; do
      job="vdb-weaviate-${wid}"
      
      if [[ "${first_ef_for_m}" == "true" ]]; then
        load_flags="--drop-old --load"
        first_ef_for_m=false
      else
        load_flags="--skip-drop-old --skip-load"
      fi
      
      run_job "$job" bash -lc "cd /opt/vdb && \
        vectordbbench weaviate \
          --db-label k8s-weaviate --task-label ${BATCH_ID}-weaviate-m${m}-ef${ef} \
          --case-type ${CASE_TYPE} --url http://weaviate.marco.svc.cluster.local \
          --no-auth --m ${m} --ef-construction ${EF_CONSTRUCTION} --ef ${ef} --metric-type COSINE \
          --replication-factor ${REPLICA} \
          --sharding-count ${SHARDING} \
          --concurrency-duration ${CONCURRENCY_DURATION} --k ${K} \
          ${load_flags} --search-serial --search-concurrent \
          --num-concurrency ${NUM_CONCURRENCY}"
      wid=$((wid+1))
    done
  done
fi

ENABLE_VALD=${ENABLE_VALD:-false}
if [[ "${ENABLE_VALD}" == "true" ]]; then
  vald_num=(10 20 40 60 80 100 150 200 300 400)
  vid=1
  for num in "${vald_num[@]}"; do
    job="vdb-vald-${vid}"
    run_job "$job" bash -lc "cd /opt/vdb && \
      python -m pip install -U protobuf==${PROTOBUF_VERSION} >/tmp/pip-vald.log 2>&1 && \
      vectordbbench vald \
        --db-label k8s-vald --task-label ${BATCH_ID}-vald-num${num} \
        --case-type ${CASE_TYPE} --host vald-lb-gateway.marco.svc.cluster.local --port 8081 \
        --use-tls False --batch-size 128 --metric-type COSINE --num ${num} --min-num 1 \
        --wait-for-sync-seconds ${VALD_WAIT_SECONDS} --timeout ${VALD_TIMEOUT} \
        --concurrency-duration ${CONCURRENCY_DURATION} --k ${K} \
        --drop-old --load --search-serial --search-concurrent \
        --num-concurrency ${NUM_CONCURRENCY}"
    vid=$((vid+1))
  done
fi
