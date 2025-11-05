#!/usr/bin/env bash

# Usage:
#   ./prepare_datasets.sh [target_directory]
#   source prepare_datasets.sh [target_directory]   # to export DATASET_LOCAL_DIR into current shell
#
# Default target directory: /mnt/nfs/home/hmngo/scratch/vectordb_bench/dataset

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_DIR="/mnt/nfs/home/hmngo/scratch/vectordb_bench/dataset"
TARGET_DIR="${1:-${DEFAULT_DIR}}"

mkdir -p "${TARGET_DIR}"

export DATASET_LOCAL_DIR="${TARGET_DIR}"
echo "Preparing datasets in ${DATASET_LOCAL_DIR}"

python - <<'PY'
from vectordb_bench.backend.dataset import Dataset
from vectordb_bench.backend.filter import non_filter

# Add any datasets you want cached locally before benchmarking.
targets = [
    Dataset.COHERE.manager(1_000_000),  # Cohere 1M (Performance768D1M)
    Dataset.SIFT.manager(1_000_000),    # SIFT 1M x 128 (for alternative L2 workloads)
    Dataset.OPENAI.manager(500_000),    # OpenAI 500K x 1536 (for larger-dim cosine cases)
]

for manager in targets:
    label = manager.data.full_name
    print(f"Preparing dataset {label} ...", flush=True)
    manager.prepare(filters=non_filter)
    print(f"Completed dataset {label}")

print("All requested datasets are ready.")
PY
