#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

LOCAL_RES_DIR="${SCRIPT_DIR}/../res/Batch/${BATCH_ID}/json"

echo "Batch ID: ${BATCH_ID}"
echo "Results will be collected to: ${LOCAL_RES_DIR}"
echo "Running matrix sweeps with Benchmark/scripts/run_config_matrix.sh ..."
bash "${SCRIPT_DIR}/run_config_matrix.sh"

echo "All jobs completed. Results collected incrementally after each job."

if [[ -n "${LOG_FILE:-}" ]] && [[ -f "${LOG_FILE}" ]]; then
  echo "Archiving log file (${LOG_FILE}) to batch folder..."
  cp "${LOG_FILE}" "${LOCAL_RES_DIR}/"
fi

echo "You can view them by running: RESULTS_LOCAL_DIR=${LOCAL_RES_DIR} python -m vectordb_bench"
echo "Done."
