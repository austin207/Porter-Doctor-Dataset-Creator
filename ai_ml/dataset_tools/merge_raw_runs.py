#!/usr/bin/env python3
"""Merge per-run raw CSV files into larger dataset CSV files."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


EXPERTS = [
    "power_expert",
    "motor_expert",
    "motor_driver_expert",
    "esp32_expert",
    "lighting_expert",
]


def raw_files(dataset_root: Path, expert: str) -> List[Path]:
    return sorted((dataset_root / expert / "raw").glob("*.csv"))


def collect_headers(files: Sequence[Path]) -> List[str]:
    columns: List[str] = []
    seen = set()

    for path in files:
        with path.open("r", encoding="ascii", newline="") as f:
            reader = csv.reader(f)
            try:
                header = next(reader)
            except StopIteration:
                continue
        for column in header:
            if column not in seen:
                seen.add(column)
                columns.append(column)

    if "source_file" not in seen:
        columns.append("source_file")

    return columns


def iter_rows(files: Sequence[Path]) -> Iterable[Dict[str, str]]:
    for path in files:
        with path.open("r", encoding="ascii", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["source_file"] = str(path.as_posix())
                yield row


def write_merged(files: Sequence[Path], output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    columns = collect_headers(files)
    count = 0

    with output_path.open("w", encoding="ascii", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in iter_rows(files):
            writer.writerow({column: row.get(column, "") for column in columns})
            count += 1

    return count


def merge_expert(dataset_root: Path, expert: str, output_dir: Path) -> int:
    files = raw_files(dataset_root, expert)
    return write_merged(files, output_dir / f"{expert}_raw_merged.csv")


def merge_all(dataset_root: Path, output_dir: Path) -> int:
    files: List[Path] = []
    for expert in EXPERTS:
        files.extend(raw_files(dataset_root, expert))
    return write_merged(files, output_dir / "all_experts_raw_merged.csv")


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge raw Porter Doctor run CSV files.")
    parser.add_argument("--dataset-root", type=Path, default=Path("ai_ml/datasets"))
    parser.add_argument("--output-dir", type=Path, default=Path("ai_ml/datasets/merged"))
    parser.add_argument(
        "--expert",
        choices=[*EXPERTS, "all"],
        default="all",
        help="Expert to merge, or all for one combined CSV.",
    )
    parser.add_argument(
        "--per-expert",
        action="store_true",
        help="Write one merged raw CSV per expert.",
    )
    args = parser.parse_args()

    if args.per_expert:
        total = 0
        for expert in EXPERTS:
            count = merge_expert(args.dataset_root, expert, args.output_dir)
            print(f"{expert}: wrote {count} rows")
            total += count
        print(f"total rows: {total}")
        return 0

    if args.expert == "all":
        count = merge_all(args.dataset_root, args.output_dir)
        print(f"all experts: wrote {count} rows")
    else:
        count = merge_expert(args.dataset_root, args.expert, args.output_dir)
        print(f"{args.expert}: wrote {count} rows")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
