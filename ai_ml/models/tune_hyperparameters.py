#!/usr/bin/env python3
"""Tune TensorFlow/Keras model hyperparameters from a YAML search config."""

from __future__ import annotations

import argparse
import itertools
import os
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

sys.path.append(str(Path(__file__).resolve().parent / "common"))
from training_utils import (  # noqa: E402
    ACTION_LABELS,
    action_for_label,
    build_autoencoder,
    build_classifier_model,
    choose_feature_columns,
    label_indices,
    load_json,
    normalize_frames,
    read_csvs,
    require_tensorflow_deps,
    resolve_paths,
    split_by_run_id,
    split_by_run_id_with_label_coverage,
    write_json,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TUNING_CONFIG = Path("ai_ml/models/hyperparameter_tuning.yaml")


def load_yaml(path: Path) -> Dict:
    import yaml

    with path.open("r", encoding="ascii") as f:
        return yaml.safe_load(f) or {}


def resolve_repo_path(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def limited_param_grid(params: Dict[str, List], max_combinations: int) -> List[Dict]:
    keys = list(params)
    values = [params[key] for key in keys]
    rows = [dict(zip(keys, combo)) for combo in itertools.product(*values)]
    return rows[:max_combinations] if max_combinations > 0 else rows


def selected_items(items: Dict[str, Dict], requested: Iterable[str] | None) -> Iterable[Tuple[str, Dict]]:
    requested_set = set(requested or [])
    for name, entry in items.items():
        if not requested_set or name in requested_set:
            yield name, entry


def tune_classifier(name: str, entry: Dict, defaults: Dict) -> Tuple[str, Dict]:
    import numpy as np

    config_path = resolve_repo_path(entry["config"])
    config = load_json(config_path)
    label_column = config.get("label_column", "fault_label")
    df = read_csvs([resolve_repo_path(path) for path in config["input_csvs"]])
    if label_column not in df.columns:
        raise SystemExit(f"{name}: missing label column: {label_column}")

    df = df.dropna(subset=[label_column]).copy()
    feature_columns = choose_feature_columns(df, label_column, config.get("feature_columns"))
    if not feature_columns:
        raise SystemExit(f"{name}: no numeric feature columns available for tuning")

    train_df, val_df, test_df = split_by_run_id_with_label_coverage(df, label_column)
    eval_df = val_df if not val_df.empty else test_df
    if train_df.empty or eval_df.empty:
        raise SystemExit(f"{name}: tuning needs non-empty train and validation/test splits")

    labels = sorted(str(label) for label in df[label_column].dropna().unique())
    actions = ACTION_LABELS
    x_train, x_val, x_test, _stats = normalize_frames(train_df, val_df, test_df, feature_columns)
    x_eval = x_val if not val_df.empty else x_test

    y_train_fault = np.array(label_indices(train_df[label_column].astype(str), labels), dtype=np.int32)
    y_train_action = np.array(label_indices([action_for_label(label) for label in train_df[label_column].astype(str)], actions), dtype=np.int32)
    y_eval_fault = np.array(label_indices(eval_df[label_column].astype(str), labels), dtype=np.int32)

    max_combinations = int(defaults.get("search", {}).get("max_combinations", 18))
    candidates = limited_param_grid(entry.get("params", {}), max_combinations)
    best = None

    for params in candidates:
        model = build_classifier_model(
            len(feature_columns),
            params.get("hidden_layers", config.get("hidden_layers", [32, 16])),
            len(labels),
            len(actions),
            float(params.get("learning_rate", config.get("learning_rate", 0.001))),
        )
        model.fit(
            x_train,
            {"fault_output": y_train_fault, "action_output": y_train_action},
            epochs=int(params.get("epochs", config.get("epochs", 80))),
            batch_size=int(params.get("batch_size", config.get("batch_size", 16))),
            verbose=0,
        )
        predictions = model.predict(x_eval, verbose=0)[0].argmax(axis=1)
        score = float((predictions == y_eval_fault).mean())
        if best is None or score > best["score"]:
            best = {"params": params, "score": score}

    result = {
        "model_name": name,
        "mode": "tensorflow_classifier",
        "config": str(config_path.relative_to(ROOT)),
        "feature_columns": feature_columns,
        "candidate_count": len(candidates),
        "best_params": best["params"],
        "best_score": best["score"],
        "score_metric": "validation_fault_accuracy" if not val_df.empty else "test_fault_accuracy",
    }
    write_json(resolve_repo_path(config["artifact_dir"]) / "hyperparameter_tuning_results.json", result)
    return name, result


def tune_anomaly(name: str, entry: Dict, defaults: Dict) -> Tuple[str, Dict]:
    import numpy as np

    config_path = resolve_repo_path(entry["config"])
    config = load_json(config_path)
    label_column = config.get("label_column", "fault_label")
    healthy_label = config.get("healthy_label", "healthy")
    df = read_csvs(resolve_paths([str(resolve_repo_path(path)) for path in config["input_csvs"]]))
    train_df = df[df[label_column].astype(str) == healthy_label].copy() if label_column in df.columns else df.copy()
    if train_df.empty:
        raise SystemExit(f"{name}: no healthy rows available for anomaly tuning")

    feature_columns = choose_feature_columns(train_df, label_column, config.get("feature_columns"))
    train_split, val_split, test_split = split_by_run_id(train_df)
    eval_split = val_split if not val_split.empty else test_split
    if train_split.empty or eval_split.empty:
        raise SystemExit(f"{name}: tuning needs non-empty train and validation/test splits")

    x_train, x_val, x_test, _stats = normalize_frames(train_split, val_split, test_split, feature_columns)
    x_eval = x_val if not val_split.empty else x_test
    max_combinations = int(defaults.get("search", {}).get("max_combinations", 18))
    candidates = limited_param_grid(entry.get("params", {}), max_combinations)
    best = None

    for params in candidates:
        model = build_autoencoder(
            len(feature_columns),
            params.get("hidden_layers", config.get("hidden_layers", [16, 8, 16])),
            float(params.get("learning_rate", config.get("learning_rate", 0.001))),
        )
        model.fit(
            x_train,
            x_train,
            epochs=int(params.get("epochs", config.get("epochs", 80))),
            batch_size=int(params.get("batch_size", config.get("batch_size", 16))),
            verbose=0,
        )
        recon = model.predict(x_eval, verbose=0)
        loss = float(np.mean((x_eval - recon) ** 2))
        if best is None or loss < best["loss"]:
            best = {"params": params, "loss": loss}

    result = {
        "model_name": name,
        "mode": "tensorflow_autoencoder",
        "config": str(config_path.relative_to(ROOT)),
        "feature_columns": feature_columns,
        "candidate_count": len(candidates),
        "best_params": best["params"],
        "best_score": best["loss"],
        "score_metric": "validation_reconstruction_mse" if not val_split.empty else "test_reconstruction_mse",
    }
    write_json(resolve_repo_path(config["artifact_dir"]) / "hyperparameter_tuning_results.json", result)
    return name, result


def main() -> int:
    parser = argparse.ArgumentParser(description="Tune TensorFlow/Keras Porter Doctor models.")
    parser.add_argument("--config", default=DEFAULT_TUNING_CONFIG, type=Path)
    parser.add_argument("--model", action="append", help="Tune only this model name. Can be repeated.")
    args = parser.parse_args()

    require_tensorflow_deps()
    tuning = load_yaml(resolve_repo_path(args.config))
    defaults = tuning.get("defaults", {})
    results = []

    for name, entry in selected_items(tuning.get("classifier_models", {}), args.model):
        tuned_name, result = tune_classifier(name, entry, defaults)
        print(f"{tuned_name}: best={result['best_params']} score={result['best_score']:.3f}")
        results.append(result)

    for name, entry in selected_items(tuning.get("anomaly_models", {}), args.model):
        tuned_name, result = tune_anomaly(name, entry, defaults)
        print(f"{tuned_name}: best={result['best_params']} mse={result['best_score']:.6f}")
        results.append(result)

    if args.model and not results:
        raise SystemExit(f"No models matched: {', '.join(args.model)}")

    write_json(ROOT / "ai_ml/models/tuning_summary.json", {"results": results})
    print("wrote tuning summary to ai_ml/models/tuning_summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
