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
# Valid sizes: Cohere (100K, 1M, 10M), OpenAI (50K, 500K, 5M), SIFT (500K)
targets = [
    Dataset.COHERE.manager(100_000),    # Cohere 100K (Performance768D100K)
    Dataset.COHERE.manager(1_000_000),  # Cohere 1M (Performance768D1M)
    Dataset.OPENAI.manager(50_000),     # OpenAI 50K (Performance1536D50K)
    Dataset.OPENAI.manager(500_000),    # OpenAI 500K (Performance1536D500K)
]

for manager in targets:
    label = manager.data.full_name
    print(f"Preparing dataset {label} ...", flush=True)
    manager.prepare(filters=non_filter)
    print(f"Completed dataset {label}")

print("All requested datasets are ready.")
PY
