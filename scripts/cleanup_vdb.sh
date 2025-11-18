#!/usr/bin/env bash

# Delete benchmark jobs/pods and wipe result JSONs.
# Defaults: namespace=marco, results root=/mnt/nfs/home/hmngo/work1/hmngo/vdb_results

set -euo pipefail

NS=${NS:-marco}
RESULT_ROOT=${RESULT_ROOT:-/mnt/nfs/home/hmngo/work1/hmngo/vdb_results}

JOBS=(
  vdb-milvus
  vdb-qdrant
  vdb-weaviate
  vdb-vald
)

echo "Deleting jobs in namespace ${NS}: ${JOBS[*]}"
for job in "${JOBS[@]}"; do
  kubectl -n "$NS" delete job "$job" --ignore-not-found
done

echo "Deleting pods from previous runs (if any)..."
kubectl -n "$NS" get pods | awk '/vdb-(milvus|qdrant|weaviate|vald)/{print $1}' | xargs -r kubectl -n "$NS" delete pod

echo "Removing result JSONs under ${RESULT_ROOT}..."
find "${RESULT_ROOT}" -name "result_*.json" -delete

echo "Cleanup complete."
