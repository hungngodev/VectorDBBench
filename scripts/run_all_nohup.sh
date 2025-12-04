#!/usr/bin/env bash

# Wrapper to run the full benchmark pipeline detached via nohup.
# Usage:
#   HOST_DATA_DIR=... HOST_RESULTS_DIR=... CPU=16 MEM=64Gi \
#   bash scripts/run_all_nohup.sh
#
# Log is written to run_all.log in the current working directory.

set -euo pipefail

export PATH=/usr/local/bin:$PATH

LOG_FILE=${LOG_FILE:-run_all.log}

echo "Starting scripts/run_all_and_cleanup.sh with nohup; logging to ${LOG_FILE}"
nohup bash scripts/run_all_and_cleanup.sh > "${LOG_FILE}" 2>&1 &
echo "PID: $! (log: ${LOG_FILE})"
