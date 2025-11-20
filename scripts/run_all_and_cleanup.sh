#!/usr/bin/env bash

# Run matrix sweeps for all DBs, aggregate results into one CSV, then delete individual JSONs.
# Assumes:
#   - Image hungngodev/vectordbbench:latest is built/pushed and contains /opt/vdb (with protobuf pin for Vald).
#   - Namespace: marco (override with NS).

set -euo pipefail

NS=${NS:-marco}
IMG=${IMG:-hungngodev/vectordbbench:latest}
RESULT_ROOT=${RESULT_ROOT:-/mnt/nfs/home/hmngo/work1/hmngo/vdb_results}
OUTPUT=${OUTPUT:-all_results.csv}

echo "Running matrix sweeps with scripts/run_config_matrix.sh ..."
bash "$(dirname "$0")/run_config_matrix.sh"

echo "Aggregating results into ${OUTPUT} ..."
python "$(dirname "$0")/aggregate_results.py" --root "${RESULT_ROOT}" --output "${OUTPUT}"

echo "Cleaning up individual result JSONs under ${RESULT_ROOT} ..."
find "${RESULT_ROOT}" -name "result_*.json" -exec rm -f {} + 2>/dev/null || true

echo "Done. Aggregated CSV: ${OUTPUT}"
