#!/usr/bin/env bash


set -euo pipefail

export PATH=/usr/local/bin:$PATH

LOG_FILE=${LOG_FILE:-logs/run_all.log}

echo "Starting scripts/run_all_and_cleanup.sh with nohup; logging to ${LOG_FILE}"
nohup bash "$(dirname "$0")/run_all_and_cleanup.sh" > "${LOG_FILE}" 2>&1 &
echo "PID: $! (log: ${LOG_FILE})"
