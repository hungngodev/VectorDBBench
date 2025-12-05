#!/usr/bin/env bash

# === MUST BE RUN ON THE REMOTE SERVER (where kubectl works) ===
# This script will:
# 1. Download results from all completed/running pods (vdb-*) to a local folder.
#    (This works whether you used NFS or not).
# 2. Aggregate those downloaded JSONs into all_results_v2.csv using the new metrics logic.

set -e

TEMP_DIR="collected_results_$(date +%s)"
mkdir -p "${TEMP_DIR}"

echo ">>> Phase 1: Downloading results from pods to ${TEMP_DIR}..."
echo "    (This might show 'No such file' for pods that failed or haven't started, which is fine)"

# Get all pods starting with vdb-milvus (TEST MARKER)
PODS=$(kubectl -n marco get pods --no-headers -o custom-columns=":metadata.name" | grep '^vdb-milvus')

if [ -z "$PODS" ]; then
    echo "ERROR: No 'vdb-*' pods found in namespace 'marco'. Are you sure kubectl is working here?"
    exit 1
fi

for pod in $PODS; do
    echo "  - Checking pod: $pod"
    # Try to copy from Milvus, Weaviate, etc. paths. 
    # Valid paths inside pod: /opt/vdb/vectordb_bench/results/{Milvus,Weaviate,Qdrant,Vald}
    
    # We copy the *entire* results directory recursively to capture all DB subfolders
    kubectl -n marco cp "$pod:/opt/vdb/vectordb_bench/results/." "${TEMP_DIR}/" >/dev/null 2>&1 || true
done

echo ">>> Phase 2: Generating Python Aggregation Script..."
cat <<EOF > temp_aggregator.py
import argparse
import csv
import json
import os
import glob
import numpy as np

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    # Headers including NEW per-concurrency fields
    headers = [
        "db", "task_label", "concurrency", 
        "qps", 
        "latency_p99", "latency_p95", "latency_p90", "latency_avg", 
        "recall",
        "load_duration", "serial_recall", "serial_latency_p99", "file"
    ]
    
    rows = []
    # Find all result_*.json recursively
    files = glob.glob(os.path.join(args.root, "**", "result_*.json"), recursive=True)
    print(f"  Found {len(files)} JSON result files.")

    for fpath in files:
        try:
            with open(fpath, "r") as f:
                data = json.load(f)
            
            # Basic Metadata
            db = data.get("db", "N/A")
            task_label = data.get("task_label", "N/A")
            metric = data.get("result", {})
            
            # Serial/Global metrics
            serial_recall = metric.get("recall", 0.0)
            serial_p99 = metric.get("serial_latency_p99", 0.0)
            load_dur = metric.get("load_duration", 0.0)

            # Concurrent Lists
            conc_nums = metric.get("conc_num_list", [])
            conc_qps = metric.get("conc_qps_list", [])
            conc_p99 = metric.get("conc_latency_p99_list", [])
            conc_p95 = metric.get("conc_latency_p95_list", [])
            conc_p90 = metric.get("conc_latency_p90_list", [])
            conc_avg = metric.get("conc_latency_avg_list", [])
            conc_recall = metric.get("conc_recall_list", [])
            
            # Flatten lists into rows
            count = len(conc_nums)
            for i in range(count):
                row = {
                    "db": db,
                    "task_label": task_label,
                    "concurrency": conc_nums[i] if i < len(conc_nums) else 0,
                    "qps": conc_qps[i] if i < len(conc_qps) else 0.0,
                    "latency_p99": conc_p99[i] if i < len(conc_p99) else 0.0,
                    "latency_p95": conc_p95[i] if i < len(conc_p95) else 0.0,
                    "latency_p90": conc_p90[i] if i < len(conc_p90) else 0.0,
                    "latency_avg": conc_avg[i] if i < len(conc_avg) else 0.0,
                    "recall": conc_recall[i] if i < len(conc_recall) else 0.0,
                    "load_duration": load_dur,
                    "serial_recall": serial_recall,
                    "serial_latency_p99": serial_p99,
                    "file": fpath
                }
                rows.append(row)
                
        except Exception as e:
            print(f"  Skipping bad file {fpath}: {e}")

    if rows:
        rows.sort(key=lambda x: (x["db"], x["task_label"], x["concurrency"]))
        with open(args.output, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
        print(f"  Success! Aggregated {len(rows)} rows into {args.output}")
    else:
        print("  Warning: No valid rows generated.")

if __name__ == "__main__":
    main()
EOF

echo ">>> Phase 3: Aggregating..."
python3 temp_aggregator.py --root "${TEMP_DIR}" --output all_results_v2.csv

# Cleanup
rm temp_aggregator.py
# rm -rf "${TEMP_DIR}"  <-- Optional: keep the files just in case

echo ">>> DONE. Results are in: all_results_v2.csv"
