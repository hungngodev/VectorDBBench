#!/usr/bin/env bash

# Generate and run many benchmark jobs from parameter matrices (no YAML needed).
# Adjust the arrays below to try as many configs as you like. Jobs run sequentially per DB.

set -euo pipefail

NS=${NS:-marco}
IMG=${IMG:-hungngodev/vectordbbench:latest}
DATA_DIR=${DATA_DIR:-/opt/vdb/datasets}

run_job() {
  local job="$1"; shift
  echo "-- job/${job}"
  kubectl -n "$NS" delete job "$job" --ignore-not-found
  kubectl -n "$NS" create job "$job" --image="$IMG" -- "$@"
  kubectl -n "$NS" logs -f "job/${job}" || true
}

echo "Running matrix sweeps in namespace: $NS with image: $IMG"

# Milvus matrix (~12 jobs: 4x3)
milvus_m=(16 24 32 40)
milvus_ef=(128 256 384)
mid=1
for m in "${milvus_m[@]}"; do
  for ef in "${milvus_ef[@]}"; do
    job="vdb-milvus-${mid}"
    run_job "$job" bash -lc "cd /opt/vdb && ./prepare_datasets.sh ${DATA_DIR} && \
      vectordbbench milvusautoindex \
        --db-label k8s-milvus --task-label milvus-m${m}-ef${ef} \
        --case-type Performance768D1M --uri http://milvus.marco.svc.cluster.local:19530 \
        --m ${m} --ef-search ${ef} --k 10 --drop-old --load --search-serial --search-concurrent"
    mid=$((mid+1))
  done
done

# Qdrant matrix (~12 jobs: 4x3; drop_old/load enabled by default)
qdrant_m=(16 24 32 40)
qdrant_ef=(128 256 384)
qid=1
for m in "${qdrant_m[@]}"; do
  for ef in "${qdrant_ef[@]}"; do
    job="vdb-qdrant-${qid}"
    run_job "$job" bash -lc "cd /opt/vdb && ./prepare_datasets.sh ${DATA_DIR} && \
      vectordbbench qdrantlocal \
        --db-label k8s-qdrant --task-label qdrant-m${m}-ef${ef} \
        --case-type Performance768D1M --url http://qdrant.marco.svc.cluster.local:6333 \
        --metric-type COSINE --on-disk False --m ${m} --ef-construct ${ef} --hnsw-ef ${ef} --k 10 \
        --drop-old --load --search-serial --search-concurrent"
    qid=$((qid+1))
  done
done

# Weaviate matrix (~12 jobs: 4x3; no auth)
weav_m=(16 24 32 40)
weav_ef=(128 256 384)
wid=1
for m in "${weav_m[@]}"; do
  for ef in "${weav_ef[@]}"; do
    job="vdb-weaviate-${wid}"
    run_job "$job" bash -lc "cd /opt/vdb && ./prepare_datasets.sh ${DATA_DIR} && \
      vectordbbench weaviate \
        --db-label k8s-weaviate --task-label weaviate-m${m}-ef${ef} \
        --case-type Performance768D1M --url http://weaviate.marco.svc.cluster.local \
        --no-auth --m ${m} --ef-construction ${ef} --ef ${ef} --metric-type COSINE --k 10 \
        --drop-old --load --search-serial --search-concurrent"
    wid=$((wid+1))
  done
done

# Vald matrix (~4 jobs; requires protobuf runtime pinned)
vald_num=(8 12 16 20)
vid=1
for num in "${vald_num[@]}"; do
  job="vdb-vald-${vid}"
  run_job "$job" bash -lc "cd /opt/vdb && ./prepare_datasets.sh ${DATA_DIR} && \
    vectordbbench vald \
      --db-label k8s-vald --task-label vald-num${num} \
      --case-type Performance768D1M --host vald-lb-gateway.marco.svc.cluster.local --port 8081 \
      --use-tls False --batch-size 128 --metric-type COSINE --num ${num} --min-num 1 \
      --wait-for-sync-seconds 10 --k 10 --drop-old --load --search-serial --search-concurrent"
  vid=$((vid+1))
done
