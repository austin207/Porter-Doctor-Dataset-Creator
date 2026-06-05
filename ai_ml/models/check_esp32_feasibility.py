#!/usr/bin/env python3
"""Check trained model artifacts against current ESP32 deployment limits."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List

from common.training_utils import (
    ESP32_MODEL_LIMITS,
    esp32_feasibility_report,
    estimate_int8_tflite_bytes,
    load_json,
    write_json,
)


ROOT = Path(__file__).resolve().parents[2]
MODELS = [
    "power_expert",
    "motor_expert",
    "motor_driver_expert",
    "esp32_expert",
    "lighting_expert",
    "router",
    "anomaly_detector",
]


def model_report(model_name: str) -> Dict[str, object]:
    import tensorflow as tf

    artifact_dir = ROOT / "ai_ml/models" / model_name / "artifacts"
    metrics_path = artifact_dir / "metrics.json"
    int8_path = artifact_dir / "model_int8.tflite"
    keras_path = artifact_dir / "model_float32.keras"
    if not metrics_path.exists():
        return {
            "model_name": model_name,
            "status": "missing_metrics",
            "fits_esp32": False,
        }

    metrics = load_json(metrics_path)
    parameter_count = int(metrics.get("parameter_count", 0))
    if parameter_count == 0 and keras_path.exists():
        parameter_count = int(tf.keras.models.load_model(keras_path, compile=False).count_params())

    feature_count = int(metrics.get("feature_count", 0))
    output_dim = len(metrics.get("classes", [])) + len(metrics.get("actions", []))
    if model_name == "anomaly_detector":
        output_dim = feature_count
    estimated_bytes = estimate_int8_tflite_bytes(parameter_count, feature_count, output_dim, 2 if model_name != "anomaly_detector" else 1)
    feasibility = metrics.get("esp32_feasibility") or esp32_feasibility_report(model_name, parameter_count, estimated_bytes)
    actual_bytes = int8_path.stat().st_size if int8_path.exists() else 0
    fits_params = bool(feasibility.get("fits_parameter_limit", False))
    fits_size = actual_bytes <= int(feasibility.get("max_int8_tflite_bytes", 0)) if actual_bytes else False
    return {
        "model_name": model_name,
        "status": "ok" if int8_path.exists() else "missing_int8_tflite",
        "parameter_count": parameter_count,
        "int8_tflite_bytes": actual_bytes,
        "max_parameters": int(feasibility.get("max_parameters", 0)),
        "max_int8_tflite_bytes": int(feasibility.get("max_int8_tflite_bytes", 0)),
        "fits_parameter_limit": fits_params,
        "fits_tflite_size_limit": fits_size,
        "fits_esp32": fits_params and fits_size,
    }


def write_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check trained TFLite models against ESP32 limits.")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "ai_ml/evaluation_outputs/esp32_feasibility")
    args = parser.parse_args()

    rows = [model_report(model_name) for model_name in MODELS]
    total_parameters = sum(int(row.get("parameter_count", 0)) for row in rows)
    total_limit = int(ESP32_MODEL_LIMITS["total_embedded"]["max_parameters"])
    summary = {
        "models": rows,
        "total_parameters": total_parameters,
        "total_parameter_limit": total_limit,
        "fits_total_parameter_limit": total_parameters <= total_limit,
        "all_models_fit_individual_limits": all(bool(row.get("fits_esp32", False)) for row in rows),
    }

    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    write_json(output_dir / "esp32_feasibility_report.json", summary)
    write_csv(output_dir / "esp32_feasibility_report.csv", rows)

    for row in rows:
        print(
            f"{row['model_name']}: params={row.get('parameter_count', 0)} "
            f"int8={row.get('int8_tflite_bytes', 0)}B fits={row.get('fits_esp32', False)}"
        )
    print(f"total params={total_parameters}/{total_limit} fits={summary['fits_total_parameter_limit']}")
    print(f"wrote {output_dir / 'esp32_feasibility_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
