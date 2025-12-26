#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

HNSW_M_VALUES_ARR=(${HNSW_M_VALUES})
HNSW_EF_VALUES_ARR=(${HNSW_EF_VALUES})

LOCAL_RES_DIR="${SCRIPT_DIR}/../res/Batch/${BATCH_ID}/json"
mkdir -p "${LOCAL_RES_DIR}"

collect_results() {
  echo "Collecting new results to ${LOCAL_RES_DIR} ..."
  find "${RESULT_ROOT}" -name "result_*.json" -exec cp {} "${LOCAL_RES_DIR}/" \; 2>/dev/null || true
  # Clear NFS (files owned by root, so run cleanup via K8s job)
  echo "Clearing NFS results folder..."
  kubectl -n "$NS" delete pod cleanup-results --ignore-not-found 2>/dev/null || true
  kubectl -n "$NS" run cleanup-results \
    --restart=Never \
    --image=busybox \
    --overrides='{
      "spec": {
        "containers": [{
          "name": "cleanup-results",
          "image": "busybox",
          "command": ["sh", "-c", "rm -rf /results/Milvus/result_*.json /results/WeaviateCloud/result_*.json /results/QdrantLocal/result_*.json /results/Vald/result_*.json && echo Cleaned"],
          "volumeMounts": [{"name": "results", "mountPath": "/results"}]
        }],
        "volumes": [{"name": "results", "hostPath": {"path": "'"${HOST_RESULTS_DIR}"'"}}],
        "restartPolicy": "Never"
      }
    }' \
    2>/dev/null || true
  kubectl -n "$NS" wait --for=condition=Ready pod/cleanup-results --timeout=30s 2>/dev/null || true
  kubectl -n "$NS" logs cleanup-results 2>/dev/null || true
  kubectl -n "$NS" delete pod cleanup-results --ignore-not-found 2>/dev/null || true
}

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
  kubectl -n "$NS" wait --for=condition=complete --timeout=8h "job/${job}"
  kubectl -n "$NS" logs "job/${job}" || true
  collect_results
}

echo "Running matrix sweeps in namespace: $NS with image: $IMG"

if [[ "${ENABLE_MILVUS}" == "true" ]]; then
  mid=1
  for m in "${HNSW_M_VALUES_ARR[@]}"; do
    first_ef_for_m=true
    for ef in "${HNSW_EF_VALUES_ARR[@]}"; do
      job="vdb-milvus-${mid}"
      
      if [[ "${first_ef_for_m}" == "true" ]]; then
        load_flags="--drop-old --load"
        first_ef_for_m=false
      else
        load_flags="--skip-drop-old --skip-load"
      fi
      
      run_job "$job" bash -lc "cd /opt/vdb && \
        vectordbbench milvushnsw \
          --db-label milvus-m${m}-ef${ef}-rep${REPLICA}-shard${SHARDING}-${BATCH_ID} --task-label ${BATCH_ID}-milvus-m${m}-ef${ef}-rep${REPLICA}-shard${SHARDING} \
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

if [[ "${ENABLE_QDRANT}" == "true" ]]; then
  qid=1
  for m in "${HNSW_M_VALUES_ARR[@]}"; do
    for ef in "${HNSW_EF_VALUES_ARR[@]}"; do
      job="vdb-qdrant-${qid}"
      qdrant_drop_flag="--drop-old"
      [[ "${DROP_OLD_QDRANT}" == "false" ]] && qdrant_drop_flag="--skip-drop-old"
      run_job "$job" bash -lc "cd /opt/vdb && \
        vectordbbench qdrantlocal \
          --db-label qdrant-m${m}-ef${ef}-${BATCH_ID} --task-label ${BATCH_ID}-qdrant-m${m}-ef${ef} \
          --case-type ${CASE_TYPE} --url http://qdrant.marco.svc.cluster.local:6333 \
          --metric-type COSINE --on-disk False --m ${m} --ef-construct ${ef} --hnsw-ef ${ef} \
          --concurrency-duration ${CONCURRENCY_DURATION} --k ${K} \
          ${qdrant_drop_flag} --load --search-serial --search-concurrent \
          --num-concurrency ${NUM_CONCURRENCY}"
      qid=$((qid+1))
    done
  done
fi

if [[ "${ENABLE_WEAVIATE}" == "true" ]]; then
  wid=1
  for m in "${HNSW_M_VALUES_ARR[@]}"; do
    first_ef_for_m=true
    for ef in "${HNSW_EF_VALUES_ARR[@]}"; do
      job="vdb-weaviate-${wid}"
      
      if [[ "${first_ef_for_m}" == "true" ]]; then
        load_flags="--drop-old --load"
        first_ef_for_m=false
      else
        load_flags="--skip-drop-old --skip-load"
      fi
      
      run_job "$job" bash -lc "cd /opt/vdb && \
        vectordbbench weaviate \
          --db-label weaviate-m${m}-ef${ef}-rep${REPLICA}-shard${SHARDING}-${BATCH_ID} --task-label ${BATCH_ID}-weaviate-m${m}-ef${ef}-rep${REPLICA}-shard${SHARDING} \
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
