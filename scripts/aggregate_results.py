#!/usr/bin/env python3
"""
Aggregate benchmark result JSONs into a single CSV.

By default scans /mnt/nfs/home/hmngo/work1/hmngo/vdb_results but you can override with:
  python scripts/aggregate_results.py --root /path/to/results --output combined.csv

Each row includes db (derived from folder name or filename), task_label (parsed from filename),
and common metric fields when present.
"""

import argparse
import csv
import json
import os
from glob import glob
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description="Aggregate VectorDBBench JSON results into a CSV.")
    p.add_argument("--root", default="/mnt/nfs/home/hmngo/work1/hmngo/vdb_results", help="Root directory of result JSONs")
    p.add_argument("--output", default="results_combined.csv", help="Output CSV path")
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
        "file",
        "max_load_count",
        "insert_duration",
        "optimize_duration",
        "load_duration",
        "qps",
        "serial_latency_p99",
        "serial_latency_p95",
        "recall",
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
            row = {
                "db": db,
                "task_label": task_label,
                "file": str(path),
                "max_load_count": metrics.get("max_load_count"),
                "insert_duration": metrics.get("insert_duration"),
                "optimize_duration": metrics.get("optimize_duration"),
                "load_duration": metrics.get("load_duration") or metrics.get("load_dur"),
                "qps": metrics.get("qps"),
                "serial_latency_p99": metrics.get("serial_latency_p99") or metrics.get("latency_p99"),
                "serial_latency_p95": metrics.get("serial_latency_p95") or metrics.get("latency_p95"),
                "recall": metrics.get("recall"),
            }
            rows.append(row)

    with open(args.output, "w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
