#!/usr/bin/env bash

# Usage:
#   source prepare_datasets.sh   # exports DATASET_LOCAL_DIR for current shell
#   ./prepare_datasets.sh        # creates the directory and prints instructions

DATASET_DIR="/mnt/nfs/home/hmngo/scratch/vectordb_bench/dataset"

mkdir -p "${DATASET_DIR}"

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "Dataset directory prepared at ${DATASET_DIR}"
  echo "Export DATASET_LOCAL_DIR=\"${DATASET_DIR}\" (or source this script) before running the benchmark."
else
  export DATASET_LOCAL_DIR="${DATASET_DIR}"
  echo "DATASET_LOCAL_DIR set to ${DATASET_LOCAL_DIR}"
fi
