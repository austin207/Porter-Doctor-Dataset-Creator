#!/usr/bin/env python3
"""Export TensorFlow Lite models as Zephyr-ready C files."""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List

from common.training_utils import load_json, write_json


ROOT = Path(__file__).resolve().parents[2]
ZEPHYR_INFERENCE_ROOT = ROOT / "zephyr_inference"
DEFAULT_OUTPUT_DIR = ZEPHYR_INFERENCE_ROOT / "generated"
MODELS = [
    "power_expert",
    "motor_expert",
    "motor_driver_expert",
    "esp32_expert",
    "lighting_expert",
    "router",
    "anomaly_detector",
]


def c_identifier(value: str) -> str:
    cleaned = re.sub(r"[^0-9a-zA-Z_]", "_", value)
    if cleaned and cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    return cleaned.lower()


def c_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def format_float(value: float) -> str:
    text = f"{float(value):.9g}"
    if "e" not in text.lower() and "." not in text:
        text = f"{text}.0"
    return f"{text}f"


def model_dir(model_name: str) -> Path:
    return ROOT / "ai_ml/models" / model_name


def artifact_dir(model_name: str, source: str) -> tuple[Path, str]:
    base = model_dir(model_name)
    best = base / "best_candidate/artifacts"
    current = base / "artifacts"
    if source == "best_candidate":
        return best, "best_candidate"
    if source == "artifacts":
        return current, "artifacts"
    if best.exists():
        return best, "best_candidate"
    return current, "artifacts"


def load_optional_json(path: Path) -> Dict:
    return load_json(path) if path.exists() else {}


def sorted_by_index(mapping: Dict[str, int]) -> List[str]:
    return [name for name, _index in sorted(mapping.items(), key=lambda item: int(item[1]))]


def read_metadata(artifacts: Path) -> Dict:
    feature_order = load_optional_json(artifacts / "feature_order.json").get("feature_order", [])
    stats = load_optional_json(artifacts / "normalization_stats.json")
    labels = sorted_by_index(load_optional_json(artifacts / "label_map.json").get("labels", {}))
    actions = sorted_by_index(load_optional_json(artifacts / "action_map.json").get("actions", {}))
    metrics = load_optional_json(artifacts / "metrics.json")
    tuning = load_optional_json(artifacts / "hyperparameter_tuning_results.json")
    threshold = metrics.get("reconstruction_error_threshold_p95", 0.0)
    return {
        "feature_order": feature_order,
        "mean": [float(stats.get("mean", {}).get(feature, 0.0)) for feature in feature_order],
        "std": [float(stats.get("std", {}).get(feature, 1.0)) for feature in feature_order],
        "labels": labels,
        "actions": actions,
        "anomaly_threshold": float(threshold) if threshold is not None else 0.0,
        "metrics": metrics,
        "tuning": tuning,
    }


def write_model_files(model_name: str, artifacts: Path, output_dir: Path, source: str) -> Dict:
    tflite_path = artifacts / "model_int8.tflite"
    if not tflite_path.exists():
        raise FileNotFoundError(f"Missing INT8 TFLite model: {tflite_path}")

    model_bytes = tflite_path.read_bytes()
    symbol = f"porter_{c_identifier(model_name)}"
    header_name = f"{model_name}_model_data.h"
    source_name = f"{model_name}_model_data.c"
    metadata = read_metadata(artifacts)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    byte_rows = []
    for index in range(0, len(model_bytes), 12):
        row = ", ".join(f"0x{byte:02x}" for byte in model_bytes[index : index + 12])
        byte_rows.append(f"\t{row},")

    (output_dir / header_name).write_text(
        f"""#ifndef {symbol.upper()}_MODEL_DATA_H
#define {symbol.upper()}_MODEL_DATA_H

#include <stddef.h>
#include <stdint.h>

#define {symbol.upper()}_MODEL_TFLITE_LEN {len(model_bytes)}u

extern const unsigned char {symbol}_model_tflite[];
extern const unsigned int {symbol}_model_tflite_len;

#endif
""",
        encoding="ascii",
    )

    (output_dir / source_name).write_text(
        f"""#include "{header_name}"

#if defined(__GNUC__)
#define PORTER_MODEL_ALIGN __attribute__((aligned(16)))
#else
#define PORTER_MODEL_ALIGN
#endif

const unsigned char {symbol}_model_tflite[] PORTER_MODEL_ALIGN = {{
{chr(10).join(byte_rows)}
}};

const unsigned int {symbol}_model_tflite_len = {len(model_bytes)}u;
""",
        encoding="ascii",
    )

    return {
        "model_name": model_name,
        "source": source,
        "artifact_dir": str(artifacts.relative_to(ROOT)),
        "tflite_bytes": len(model_bytes),
        "generated_at_utc": generated_at,
        "symbol_prefix": symbol,
        "model_header": header_name,
        "model_source": source_name,
        "metadata": metadata,
    }


def write_metadata_files(model_name: str, output_dir: Path, export: Dict) -> None:
    symbol = export["symbol_prefix"]
    metadata = export["metadata"]
    header_name = f"{model_name}_metadata.h"
    source_name = f"{model_name}_metadata.c"
    features = metadata["feature_order"]
    labels = metadata["labels"]
    actions = metadata["actions"]
    means = metadata["mean"]
    stds = metadata["std"]

    (output_dir / header_name).write_text(
        f"""#ifndef {symbol.upper()}_METADATA_H
#define {symbol.upper()}_METADATA_H

#include <stddef.h>

#define {symbol.upper()}_FEATURE_COUNT {len(features)}u
#define {symbol.upper()}_LABEL_COUNT {len(labels)}u
#define {symbol.upper()}_ACTION_COUNT {len(actions)}u
#define {symbol.upper()}_ANOMALY_THRESHOLD {format_float(metadata["anomaly_threshold"])}

extern const char *const {symbol}_feature_names[];
extern const float {symbol}_feature_mean[];
extern const float {symbol}_feature_std[];
extern const size_t {symbol}_feature_count;

extern const char *const {symbol}_label_names[];
extern const size_t {symbol}_label_count;

extern const char *const {symbol}_action_names[];
extern const size_t {symbol}_action_count;
extern const float {symbol}_anomaly_threshold;

#endif
""",
        encoding="ascii",
    )

    feature_lines = ",\n".join(f"\t{c_string(value)}" for value in features)
    label_lines = ",\n".join(f"\t{c_string(value)}" for value in labels) if labels else "\t0"
    action_lines = ",\n".join(f"\t{c_string(value)}" for value in actions) if actions else "\t0"
    mean_lines = ", ".join(format_float(value) for value in means)
    std_lines = ", ".join(format_float(value if value != 0.0 else 1.0) for value in stds)

    (output_dir / source_name).write_text(
        f"""#include "{header_name}"

const char *const {symbol}_feature_names[] = {{
{feature_lines}
}};

const float {symbol}_feature_mean[] = {{
\t{mean_lines}
}};

const float {symbol}_feature_std[] = {{
\t{std_lines}
}};

const size_t {symbol}_feature_count = {len(features)}u;

const char *const {symbol}_label_names[] = {{
{label_lines}
}};

const size_t {symbol}_label_count = {len(labels)}u;

const char *const {symbol}_action_names[] = {{
{action_lines}
}};

const size_t {symbol}_action_count = {len(actions)}u;

const float {symbol}_anomaly_threshold = {format_float(metadata["anomaly_threshold"])};
""",
        encoding="ascii",
    )

    write_json(output_dir / f"{model_name}_manifest.json", export)


def write_bundle_file(model_name: str, output_dir: Path, export: Dict) -> None:
    symbol = export["symbol_prefix"]
    header_name = f"{model_name}_bundle.h"
    source_name = f"{model_name}_bundle.c"

    (output_dir / header_name).write_text(
        f"""#ifndef {symbol.upper()}_BUNDLE_H
#define {symbol.upper()}_BUNDLE_H

#include "porter_inference.h"

extern const struct porter_model_metadata {symbol}_metadata;

#endif
""",
        encoding="ascii",
    )

    (output_dir / source_name).write_text(
        f"""#include "{header_name}"
#include "{model_name}_metadata.h"
#include "{model_name}_model_data.h"

const struct porter_model_metadata {symbol}_metadata = {{
\t.model_data = {symbol}_model_tflite,
\t.model_data_len = {symbol.upper()}_MODEL_TFLITE_LEN,
\t.feature_names = {symbol}_feature_names,
\t.feature_mean = {symbol}_feature_mean,
\t.feature_std = {symbol}_feature_std,
\t.feature_count = {symbol.upper()}_FEATURE_COUNT,
\t.label_names = {symbol}_label_names,
\t.label_count = {symbol.upper()}_LABEL_COUNT,
\t.action_names = {symbol}_action_names,
\t.action_count = {symbol.upper()}_ACTION_COUNT,
\t.anomaly_threshold = {symbol.upper()}_ANOMALY_THRESHOLD,
}};
""",
        encoding="ascii",
    )


def write_bundle_files(exports: List[Dict], output_dir: Path) -> None:
    source_entries = []
    for export in exports:
        model_name = export["model_name"]
        source_entries.append(f"  generated/{model_name}_model_data.c")
        source_entries.append(f"  generated/{model_name}_metadata.c")
        source_entries.append(f"  generated/{model_name}_bundle.c")

    write_json(
        output_dir / "manifest.json",
        {
            "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "models": [export["model_name"] for export in exports],
        },
    )

    cmake = ZEPHYR_INFERENCE_ROOT / "CMakeLists.txt"
    cmake.parent.mkdir(parents=True, exist_ok=True)
    cmake.write_text(
        """# Generated model sources are emitted into generated/.
# Include this file from a Zephyr app CMakeLists.txt after adding TFLite Micro.

zephyr_library_named(porter_zephyr_inference)
zephyr_library_include_directories(include generated)
zephyr_library_sources(
  src/porter_inference.c
"""
        + "\n".join(source_entries)
        + "\n)\n",
        encoding="ascii",
    )


def export_model(model_name: str, output_dir: Path, source: str) -> Dict | None:
    artifacts, resolved_source = artifact_dir(model_name, source)
    if not artifacts.exists():
        print(f"{model_name}: skipped, missing {source} artifacts at {artifacts}")
        return None
    output_dir.mkdir(parents=True, exist_ok=True)
    export = write_model_files(model_name, artifacts, output_dir, resolved_source)
    write_metadata_files(model_name, output_dir, export)
    write_bundle_file(model_name, output_dir, export)
    print(f"{model_name}: exported {export['tflite_bytes']} bytes to {output_dir}")
    return export


def selected_models(requested: Iterable[str] | None) -> List[str]:
    requested_set = set(requested or [])
    if not requested_set:
        return MODELS
    unknown = sorted(requested_set - set(MODELS))
    if unknown:
        raise SystemExit(f"Unknown model(s): {', '.join(unknown)}")
    return [model for model in MODELS if model in requested_set]


def main() -> int:
    parser = argparse.ArgumentParser(description="Export INT8 TFLite models to Zephyr C files.")
    parser.add_argument("--model", action="append", help="Export only this model. Can be repeated.")
    parser.add_argument("--source", choices=["auto", "best_candidate", "artifacts"], default="auto")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    exports = []
    for model_name in selected_models(args.model):
        export = export_model(model_name, output_dir, args.source)
        if export:
            exports.append(export)

    if not exports:
        raise SystemExit("No models were exported. Build best candidates first or use --source artifacts.")

    write_bundle_files(exports, output_dir)
    print(f"wrote Zephyr inference CMake file to {ZEPHYR_INFERENCE_ROOT / 'CMakeLists.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
