#!/usr/bin/env bash

# Cancel benchmark jobs and delete their pods/logs.
# Usage:
#   NS=marco bash scripts/cleanup_bench.sh

set -euo pipefail

NS=${NS:-marco}

echo "Deleting jobs with prefix vdb- and vectordb-bench in namespace ${NS}..."
kubectl -n "${NS}" get jobs -o name | grep -E '^job/(vdb-|vectordb-bench)' | xargs -r kubectl -n "${NS}" delete

echo "Deleting pods with prefix vdb- and vectordb-bench in namespace ${NS}..."
kubectl -n "${NS}" get pods -o name | grep -E '^pod/(vdb-|vectordb-bench)' | xargs -r kubectl -n "${NS}" delete

echo "Cleanup done."
