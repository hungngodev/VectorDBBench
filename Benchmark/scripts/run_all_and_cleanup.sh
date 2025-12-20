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
K=${K:-100}
HNSW_M_VALUES=${HNSW_M_VALUES:-"4 8 16 32 64 128 256"}
HNSW_EF_VALUES=${HNSW_EF_VALUES:-"128 192 256 384 512 640 768 1024"}

M_ARR=(${HNSW_M_VALUES})
EF_ARR=(${HNSW_EF_VALUES})
M_RANGE="${M_ARR[0]}to${M_ARR[-1]}"
EF_RANGE="${EF_ARR[0]}to${EF_ARR[-1]}"

TIMESTAMP=$(date +%Y%m%d-%H%M)
BATCH_NAME="${CASE_TYPE}_Conc${NUM_CONCURRENCY}_EFC${EF_CONSTRUCTION}_Rep${REPLICA}_Shard${SHARDING}_K${K}_M${M_RANGE}_EF${EF_RANGE}_${TIMESTAMP}"

export BATCH_ID="${BATCH_NAME}"
export REPLICA SHARDING CASE_TYPE NUM_CONCURRENCY EF_CONSTRUCTION K HNSW_M_VALUES HNSW_EF_VALUES

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
