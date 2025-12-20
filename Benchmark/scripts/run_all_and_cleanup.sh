#!/usr/bin/env bash


set -euo pipefail

NS=${NS:-marco}
IMG=${IMG:-hungngodev/vectordbbench:latest}
RESULT_ROOT=${RESULT_ROOT:-/mnt/nfs/home/hmngo/work1/hmngo/vdb_results}

DROP_OLD_QDRANT=${DROP_OLD_QDRANT:-true}
VALD_WAIT_SECONDS=${VALD_WAIT_SECONDS:-60}
VALD_TIMEOUT=${VALD_TIMEOUT:-300}
VALD_CONCURRENCIES=${VALD_CONCURRENCIES:-"1"}

REPLICA=${REPLICA:-1}
SHARDING=${SHARDING:-1}
CASE_TYPE=${CASE_TYPE:-Performance768D100K}
NUM_CONCURRENCY=${NUM_CONCURRENCY:-512}
EF_CONSTRUCTION=${EF_CONSTRUCTION:-360}

TIMESTAMP=$(date +%Y%m%d-%H%M)
BATCH_NAME="Batch_${TIMESTAMP}_${CASE_TYPE}_Rep${REPLICA}_Shard${SHARDING}_Conc${NUM_CONCURRENCY}_EFC${EF_CONSTRUCTION}"

export BATCH_ID="${BATCH_NAME}"
export REPLICA SHARDING CASE_TYPE NUM_CONCURRENCY EF_CONSTRUCTION

echo "Batch ID: ${BATCH_ID}"
echo "Running matrix sweeps with Benchmark/scripts/run_config_matrix.sh ..."
bash "$(dirname "$0")/run_config_matrix.sh"


LOCAL_RES_DIR="$(cd "$(dirname "$0")/../res" 2>/dev/null || mkdir -p "$(dirname "$0")/../res"; cd "$(dirname "$0")/../res"; pwd)/batch/${BATCH_ID}/json"
mkdir -p "${LOCAL_RES_DIR}"

echo "Collecting result JSONs from ${RESULT_ROOT} to ${LOCAL_RES_DIR} ..."

find "${RESULT_ROOT}" -name "result_*.json" -exec mv {} "${LOCAL_RES_DIR}/" \; 2>/dev/null || true

echo "Individual JSONs collected in ${LOCAL_RES_DIR}."

if [[ -n "${LOG_FILE}" ]] && [[ -f "${LOG_FILE}" ]]; then
  echo "Archiving log file (${LOG_FILE}) to batch folder..."
  cp "${LOG_FILE}" "${LOCAL_RES_DIR}/"
fi

echo "You can view them by running: RESULTS_LOCAL_DIR=${LOCAL_RES_DIR} python -m vectordb_bench"

echo "Done."
