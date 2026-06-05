#!/usr/bin/env python3
"""Build a first-pass MoE router dataset from expert feature CSV files.

This tool creates routing labels for the Mixture-of-Experts router. It does not
train a model and it does not perform final fault classification.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, Iterable, List


OUTPUT_COLUMNS = [
    "run_id",
    "window_start_s",
    "window_end_s",
    "power_score",
    "motor_score",
    "driver_score",
    "esp32_score",
    "lighting_score",
    "target_expert",
    "fault_label",
    "fault_subsystem",
    "severity",
]

EXPERT_SCORE_COLUMNS = {
    "power_expert": "power_score",
    "motor_expert": "motor_score",
    "motor_driver_expert": "driver_score",
    "esp32_expert": "esp32_score",
    "lighting_expert": "lighting_score",
    "unknown_fault": None,
}


def load_label_map(path: Path) -> Dict[str, str]:
    with path.open("r", encoding="ascii") as f:
        data = json.load(f)
    return {label: target for target, labels in data["labels"].items() for label in labels}


def iter_feature_files(dataset_root: Path) -> Iterable[Path]:
    for expert_dir in sorted(dataset_root.glob("*_expert/features")):
        yield from sorted(expert_dir.glob("*.csv"))


def first_present(row: Dict[str, str], names: List[str], default: str) -> str:
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return value
    return default


def map_row(row: Dict[str, str], label_map: Dict[str, str]) -> Dict[str, str]:
    fault_label = first_present(row, ["fault_label", "label"], "unknown")
    target = label_map.get(fault_label, "unknown_fault")
    out = {column: "0.0" for column in OUTPUT_COLUMNS}

    out["run_id"] = first_present(row, ["run_id"], "unknown_run")
    out["window_start_s"] = first_present(row, ["window_start_s", "start_s", "elapsed_s"], "0.0")
    out["window_end_s"] = first_present(row, ["window_end_s", "end_s", "elapsed_s"], out["window_start_s"])
    out["target_expert"] = target
    out["fault_label"] = fault_label
    out["fault_subsystem"] = first_present(row, ["fault_subsystem", "subsystem"], target)
    out["severity"] = first_present(row, ["severity"], "0")

    score_column = EXPERT_SCORE_COLUMNS.get(target)
    if score_column is not None:
        out[score_column] = "1.0"

    return out


def split_runs(run_ids: List[str]) -> Dict[str, List[str]]:
    ordered = sorted(set(run_ids))
    total = len(ordered)
    if total == 0:
        return {"train": [], "val": [], "test": []}

    train_end = max(1, int(total * 0.7))
    val_end = max(train_end, int(total * 0.85))
    if total >= 3 and val_end == train_end:
        val_end += 1

    return {
        "train": ordered[:train_end],
        "val": ordered[train_end:val_end],
        "test": ordered[val_end:],
    }


def write_run_list(path: Path, run_ids: List[str]) -> None:
    path.write_text("\n".join(run_ids) + ("\n" if run_ids else ""), encoding="ascii")


def build_router_dataset(dataset_root: Path, config_path: Path, output_dir: Path) -> int:
    label_map = load_label_map(config_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, str]] = []
    for feature_file in iter_feature_files(dataset_root):
        with feature_file.open("r", encoding="ascii", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(map_row(row, label_map))

    output_csv = output_dir / "router_dataset.csv"
    with output_csv.open("w", encoding="ascii", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    splits = split_runs([row["run_id"] for row in rows])
    write_run_list(output_dir / "train_runs.txt", splits["train"])
    write_run_list(output_dir / "val_runs.txt", splits["val"])
    write_run_list(output_dir / "test_runs.txt", splits["test"])

    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a rule-based MoE router dataset.")
    parser.add_argument("--dataset-root", default=Path("ai_ml/datasets"), type=Path)
    parser.add_argument("--config", default=Path("ai_ml/router_dataset_builder/config/router_labels.json"), type=Path)
    parser.add_argument("--output-dir", default=Path("ai_ml/router_dataset_builder/output"), type=Path)
    args = parser.parse_args()

    count = build_router_dataset(args.dataset_root, args.config, args.output_dir)
    print(f"wrote {count} router rows to {args.output_dir / 'router_dataset.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
