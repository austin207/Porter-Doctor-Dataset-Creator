from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
from typing import Dict, List

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

from training_utils import load_json, read_csvs, require_tensorflow_deps


REPO_ROOT = Path(__file__).resolve().parents[3]


MODEL_CONFIGS = {
    "power_expert": REPO_ROOT / "ai_ml/models/power_expert/config.json",
    "motor_expert": REPO_ROOT / "ai_ml/models/motor_expert/config.json",
    "motor_driver_expert": REPO_ROOT / "ai_ml/models/motor_driver_expert/config.json",
    "esp32_expert": REPO_ROOT / "ai_ml/models/esp32_expert/config.json",
    "lighting_expert": REPO_ROOT / "ai_ml/models/lighting_expert/config.json",
    "router": REPO_ROOT / "ai_ml/models/router/config.json",
    "anomaly_detector": REPO_ROOT / "ai_ml/models/anomaly_detector/config.json",
}


def repo_path(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else REPO_ROOT / path


def invert_index_map(data: Dict[str, int]) -> List[str]:
    return [label for label, _idx in sorted(data.items(), key=lambda item: int(item[1]))]


def load_model_bundle(config_path: Path) -> Dict:
    require_tensorflow_deps()
    import tensorflow as tf

    config = load_json(config_path)
    artifact_dir = repo_path(config["artifact_dir"])
    model_path = artifact_dir / "model_float32.keras"
    if not model_path.exists():
        raise SystemExit(f"Missing model artifact: {model_path}. Run training first.")

    return {
        "config": config,
        "artifact_dir": artifact_dir,
        "model": tf.keras.models.load_model(model_path, compile=False),
        "feature_order": load_json(artifact_dir / "feature_order.json")["feature_order"],
        "normalization": load_json(artifact_dir / "normalization_stats.json"),
        "label_map": load_json(artifact_dir / "label_map.json")["labels"] if (artifact_dir / "label_map.json").exists() else {},
        "action_map": load_json(artifact_dir / "action_map.json")["actions"] if (artifact_dir / "action_map.json").exists() else {},
        "metrics": load_json(artifact_dir / "metrics.json") if (artifact_dir / "metrics.json").exists() else {},
    }


def normalize_rows(df, feature_order: List[str], normalization: Dict):
    import numpy as np

    x = df.copy()
    for feature in feature_order:
        if feature not in x.columns:
            x[feature] = -1.0
    x = x[feature_order].fillna(-1.0).astype("float32")
    mean = normalization.get("mean", {})
    std = normalization.get("std", {})
    for feature in feature_order:
        denom = float(std.get(feature, 1.0)) or 1.0
        x[feature] = (x[feature] - float(mean.get(feature, 0.0))) / denom
    return x.to_numpy(dtype=np.float32)


def top_labels(probabilities, labels: List[str], top_k: int) -> List[str]:
    indexed = sorted(enumerate(probabilities), key=lambda item: float(item[1]), reverse=True)
    return [f"{labels[index]}:{float(score):.6f}" for index, score in indexed[:top_k]]


def predict_dataframe(model_name: str, csv_path: Path, limit: int | None = None, top_k: int = 3):
    config_path = MODEL_CONFIGS[model_name]
    bundle = load_model_bundle(config_path)
    df = read_csvs([csv_path])
    if limit:
        df = df.head(limit).copy()

    x = normalize_rows(df, bundle["feature_order"], bundle["normalization"])
    outputs = bundle["model"].predict(x, verbose=0)
    rows = []

    if model_name == "anomaly_detector":
        recon = outputs
        errors = ((x - recon) ** 2).mean(axis=1)
        threshold = float(bundle["metrics"].get("reconstruction_error_threshold_p95", 0.0))
        for index, error in enumerate(errors):
            source = df.iloc[index]
            rows.append(
                {
                    "row_index": index,
                    "run_id": source.get("run_id", ""),
                    "true_label": source.get("fault_label", ""),
                    "reconstruction_error": float(error),
                    "threshold": threshold,
                    "predicted_anomaly": int(float(error) > threshold),
                }
            )
        return rows

    fault_probs, action_probs = outputs
    labels = invert_index_map(bundle["label_map"])
    actions = invert_index_map(bundle["action_map"])
    for index in range(len(df)):
        source = df.iloc[index]
        fault_index = int(fault_probs[index].argmax())
        action_index = int(action_probs[index].argmax())
        rows.append(
            {
                "row_index": index,
                "run_id": source.get("run_id", ""),
                "true_label": source.get(bundle["config"].get("label_column", "fault_label"), ""),
                "predicted_label": labels[fault_index],
                "fault_confidence": float(fault_probs[index][fault_index]),
                "top_faults": ";".join(top_labels(fault_probs[index], labels, top_k)),
                "predicted_action": actions[action_index],
                "action_confidence": float(action_probs[index][action_index]),
                "top_actions": ";".join(top_labels(action_probs[index], actions, top_k)),
            }
        )
    return rows


def write_prediction_csv(rows: List[Dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise SystemExit("No prediction rows generated.")
    with output_path.open("w", encoding="ascii", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def default_input_csv(model_name: str) -> Path:
    config = load_json(MODEL_CONFIGS[model_name])
    return repo_path(config["input_csvs"][0])


def infer_model(model_name: str, argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"Run inference for {model_name}.")
    parser.add_argument("--input", type=Path, default=default_input_csv(model_name))
    parser.add_argument("--output", type=Path, default=REPO_ROOT / f"ai_ml/evaluation_outputs/{model_name}/predictions.csv")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args(argv)

    rows = predict_dataframe(model_name, repo_path(args.input), args.limit, args.top_k)
    write_prediction_csv(rows, repo_path(args.output))
    print(f"{model_name}: wrote {len(rows)} predictions to {repo_path(args.output)}")
    return 0
