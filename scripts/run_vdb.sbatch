#!/bin/bash
#SBATCH --job-name=vdb-orchestrate
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8          # adjust if you need more/less CPU
#SBATCH --mem=32G                  # adjust memory as needed
#SBATCH --time=12:00:00            # adjust walltime as needed
#SBATCH --exclusive                # request the whole node
#SBATCH --output=run_all.%j.log
#SBATCH --error=run_all.%j.log

set -euo pipefail

# Ensure kubectl context is available on the Slurm node
# export KUBECONFIG=/path/to/kubeconfig

cd ~/work1/hmngo/VectorDBBench

# Namespace/image/paths are picked up from the scripts; override via env if needed:
# NS=marco IMG=hungngodev/vectordbbench:latest RESULT_ROOT=/mnt/nfs/home/hmngo/work1/hmngo/vdb_results

bash scripts/run_all_and_cleanup.sh
