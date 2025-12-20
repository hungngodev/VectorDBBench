#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

echo "Batch ID: ${BATCH_ID}"
echo "Running matrix sweeps with Benchmark/scripts/run_config_matrix.sh ..."
bash "${SCRIPT_DIR}/run_config_matrix.sh"

LOCAL_RES_DIR="${SCRIPT_DIR}/../res/batch/${BATCH_ID}/json"
mkdir -p "${LOCAL_RES_DIR}"

echo "Collecting result JSONs from ${RESULT_ROOT} to ${LOCAL_RES_DIR} ..."
find "${RESULT_ROOT}" -name "result_*.json" -exec cp {} "${LOCAL_RES_DIR}/" \; 2>/dev/null || true

echo "Individual JSONs collected in ${LOCAL_RES_DIR}."

if [[ -n "${LOG_FILE:-}" ]] && [[ -f "${LOG_FILE}" ]]; then
  echo "Archiving log file (${LOG_FILE}) to batch folder..."
  cp "${LOG_FILE}" "${LOCAL_RES_DIR}/"
fi

echo "You can view them by running: RESULTS_LOCAL_DIR=${LOCAL_RES_DIR} python -m vectordb_bench"
echo "Done."
