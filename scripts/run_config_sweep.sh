#!/usr/bin/env bash

# Run many benchmark configs sequentially per database in the marco namespace.
# This avoids cross-DB interference and uses one Job per config.
# Requirements:
#   - Image hungngodev/vectordbbench:latest is built/pushed and includes the repo at /opt/vdb (and protobuf pin for Vald).
#   - Config files for each DB live in directories you define below.

set -euo pipefail

NS=${NS:-marco}
IMG=${IMG:-hungngodev/vectordbbench:latest}
DATA_DIR=${DATA_DIR:-/opt/vdb/datasets}

# Set these to directories containing per-run config yaml files (one per run).
MILVUS_CFG_DIR=${MILVUS_CFG_DIR:-configs/milvus}
QDRANT_CFG_DIR=${QDRANT_CFG_DIR:-configs/qdrant}
WEAVIATE_CFG_DIR=${WEAVIATE_CFG_DIR:-configs/weaviate}
VALD_CFG_DIR=${VALD_CFG_DIR:-configs/vald}

# Command templates (adjust flags to your environment)
MILVUS_CMD=${MILVUS_CMD:-"vectordbbench milvusautoindex --db-label k8s-milvus --task-label milvus-k8s-benchmark --case-type Performance768D1M --uri http://milvus.marco.svc.cluster.local:19530 --k 10 --drop-old --load --search-serial --search-concurrent"}
QDRANT_CMD=${QDRANT_CMD:-"vectordbbench qdrantlocal --db-label k8s-qdrant --task-label qdrant-k8s-benchmark --case-type Performance768D1M --url http://qdrant.marco.svc.cluster.local:6333 --metric-type COSINE --on-disk False --m 16 --ef-construct 256 --hnsw-ef 256 --k 10 --skip-drop-old --skip-load --search-serial --search-concurrent"}
WEAVIATE_CMD=${WEAVIATE_CMD:-"vectordbbench weaviate --db-label k8s-weaviate --task-label weaviate-k8s-benchmark --case-type Performance768D1M --url http://weaviate.marco.svc.cluster.local --no-auth --m 16 --ef-construction 256 --ef 256 --metric-type COSINE --k 10 --drop-old --load --search-serial --search-concurrent"}
VALD_CMD=${VALD_CMD:-"vectordbbench vald --db-label k8s-vald --task-label vald-k8s-benchmark --case-type Performance768D1M --host vald-lb-gateway.marco.svc.cluster.local --port 8081 --use-tls False --batch-size 128 --metric-type COSINE --num 10 --min-num 1 --wait-for-sync-seconds 10 --k 10 --drop-old --load --search-serial --search-concurrent"}

run_sweep() {
  local db="$1"
  local cfg_dir="$2"
  local cmd="$3"

  shopt -s nullglob
  local cfgs=("$cfg_dir"/*.yml "$cfg_dir"/*.yaml)
  echo "== Running ${db} configs from ${cfg_dir} (count: ${#cfgs[@]}) =="
  local idx=1
  for cfg in "${cfgs[@]}"; do
    [ -e "$cfg" ] || continue
    local base
    base=$(basename "$cfg")
    local job="vdb-${db}-${idx}"
    echo "-- ${db} run ${idx}: ${base} -> job/${job}"
    kubectl -n "$NS" delete job "$job" --ignore-not-found
    kubectl -n "$NS" create job "$job" --image="$IMG" -- \
      bash -lc "cd /opt/vdb && ./prepare_datasets.sh ${DATA_DIR} && ${cmd} --config-file \"${cfg}\""
    kubectl -n "$NS" logs -f "job/${job}" || true
    idx=$((idx + 1))
  done
}

run_sweep milvus "$MILVUS_CFG_DIR" "$MILVUS_CMD"
run_sweep qdrant "$QDRANT_CFG_DIR" "$QDRANT_CMD"
run_sweep weaviate "$WEAVIATE_CFG_DIR" "$WEAVIATE_CMD"
run_sweep vald "$VALD_CFG_DIR" "$VALD_CMD"
