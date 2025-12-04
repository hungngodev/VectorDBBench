#!/usr/bin/env bash

# Stop local benchmark scripts
echo "Stopping local scripts..."
pkill -f run_all_nohup.sh || true
pkill -f run_config_matrix.sh || true

# Verify they are stopped
echo "Verifying processes are stopped..."
if pgrep -fl "run_all_nohup.sh|run_config_matrix.sh"; then
    echo "Warning: Some processes are still running."
else
    echo "All local scripts stopped."
fi

# Delete Kubernetes jobs
echo "Deleting Kubernetes jobs in namespace 'marco'..."
kubectl -n marco delete jobs --all

echo "Cleanup complete."
