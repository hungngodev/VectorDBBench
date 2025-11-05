#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DEFAULT="${ROOT_DIR}/vectordb_bench/config-files/k8s_local_fourdb.yml"

CONFIG_FILE="${1:-${CONFIG_DEFAULT}}"

if [[ ! -f "${CONFIG_FILE}" ]]; then
  echo "Configuration file not found: ${CONFIG_FILE}" >&2
  exit 1
fi

if ! command -v vectordbbench >/dev/null 2>&1; then
  echo "Installing VectorDBBench with Vald extra..." >&2
  python -m pip install -e "${ROOT_DIR}[vald]"
fi

echo "Running benchmark with configuration: ${CONFIG_FILE}"
vectordbbench batchcli --batch-config-file "${CONFIG_FILE}"
