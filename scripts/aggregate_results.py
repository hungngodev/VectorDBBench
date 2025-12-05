#!/usr/bin/env python3
"""
Aggregate benchmark result JSONs into a single CSV.

By default scans /mnt/nfs/home/hmngo/work1/hmngo/vdb_results but you can override with:
  python scripts/aggregate_results.py --root /path/to/results --output combined.csv

Each row includes db, task_label, concurrency level, and all metrics for that concurrency.
One row is emitted per (config, concurrency) pair.
"""

import argparse
import csv
import json
from glob import glob
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description="Aggregate VectorDBBench JSON results into a CSV.")
    p.add_argument("--root", default="/mnt/nfs/home/hmngo/work1/hmngo/vdb_results", help="Root directory of result JSONs")
    p.add_argument("--output", default="all_results.csv", help="Output CSV path")
    return p.parse_args()


def parse_file_path(path: Path):
    name = path.stem  # result_20251118_qdrant-k8s-benchmark_qdrantlocal
    parts = name.split("_", 2)
    task_label = parts[1] if len(parts) > 1 else ""
    db = parts[2] if len(parts) > 2 else path.parent.name
    return task_label, db


def main():
    args = parse_args()
    root = Path(args.root)
    files = glob(str(root / "**" / "result_*.json"), recursive=True)
    if not files:
        print(f"No result_*.json files found under {root}")
        return

    fields = [
        "db",
        "task_label",
        "concurrency",
        "qps",
        "latency_p99",
        "latency_p95",
        "latency_p90",
        "latency_avg",
        "recall",
        # Also include load/build times (same for all concurrencies within a config)
        "load_duration",
        "insert_duration",
        "optimize_duration",
        # Serial search metrics (for reference)
        "serial_latency_p99",
        "serial_latency_p95",
        "serial_recall",
    ]

    rows = []
    for f in files:
        path = Path(f)
        task_label, db = parse_file_path(path)
        try:
            with path.open() as fh:
                data = json.load(fh)
        except Exception as e:
            print(f"Skip {path}: {e}")
            continue
        results = data.get("results") or []
        for res in results:
            metrics = res.get("metrics", {})

            # Get per-concurrency lists
            conc_num_list = metrics.get("conc_num_list", [])
            conc_qps_list = metrics.get("conc_qps_list", [])
            conc_latency_p99_list = metrics.get("conc_latency_p99_list", [])
            conc_latency_p95_list = metrics.get("conc_latency_p95_list", [])
            conc_latency_p90_list = metrics.get("conc_latency_p90_list", [])
            conc_latency_avg_list = metrics.get("conc_latency_avg_list", [])
            conc_recall_list = metrics.get("conc_recall_list", [])

            # Common fields (same for all concurrencies in this config)
            load_duration = metrics.get("load_duration") or metrics.get("load_dur")
            insert_duration = metrics.get("insert_duration")
            optimize_duration = metrics.get("optimize_duration")
            serial_latency_p99 = metrics.get("serial_latency_p99") or metrics.get("latency_p99")
            serial_latency_p95 = metrics.get("serial_latency_p95") or metrics.get("latency_p95")
            serial_recall = metrics.get("recall")

            # Emit one row per concurrency level
            if conc_num_list:
                for i, conc in enumerate(conc_num_list):
                    row = {
                        "db": db,
                        "task_label": task_label,
                        "concurrency": conc,
                        "qps": conc_qps_list[i] if i < len(conc_qps_list) else None,
                        "latency_p99": conc_latency_p99_list[i] if i < len(conc_latency_p99_list) else None,
                        "latency_p95": conc_latency_p95_list[i] if i < len(conc_latency_p95_list) else None,
                        "latency_p90": conc_latency_p90_list[i] if i < len(conc_latency_p90_list) else None,
                        "latency_avg": conc_latency_avg_list[i] if i < len(conc_latency_avg_list) else None,
                        "recall": conc_recall_list[i] if i < len(conc_recall_list) else None,
                        "load_duration": load_duration,
                        "insert_duration": insert_duration,
                        "optimize_duration": optimize_duration,
                        "serial_latency_p99": serial_latency_p99,
                        "serial_latency_p95": serial_latency_p95,
                        "serial_recall": serial_recall,
                    }
                    rows.append(row)
            else:
                # Fallback: no concurrency data, emit single row with summary
                row = {
                    "db": db,
                    "task_label": task_label,
                    "concurrency": None,
                    "qps": metrics.get("qps"),
                    "latency_p99": serial_latency_p99,
                    "latency_p95": serial_latency_p95,
                    "latency_p90": None,
                    "latency_avg": None,
                    "recall": serial_recall,
                    "load_duration": load_duration,
                    "insert_duration": insert_duration,
                    "optimize_duration": optimize_duration,
                    "serial_latency_p99": serial_latency_p99,
                    "serial_latency_p95": serial_latency_p95,
                    "serial_recall": serial_recall,
                }
                rows.append(row)

    with open(args.output, "w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
