from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


COMMON_DROP_COLUMNS = {
    "timestamp_ms",
    "elapsed_s",
    "run_id",
    "robot_id",
    "expert_name",
    "fault_label",
    "fault_subsystem",
    "source_file",
}


def require_training_deps():
    try:
        import joblib  # noqa: F401
        import numpy as np  # noqa: F401
        import pandas as pd  # noqa: F401
        import sklearn  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "Missing training dependency. Install with: "
            "python -m pip install pandas scikit-learn joblib numpy"
        ) from exc


def load_json(path: Path) -> Dict:
    with path.open("r", encoding="ascii") as f:
        return json.load(f)


def write_json(path: Path, data: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")


def resolve_paths(paths: Iterable[str]) -> List[Path]:
    return [Path(p) for p in paths]


def read_csvs(paths: List[Path]):
    require_training_deps()
    import pandas as pd

    frames = []
    for path in paths:
        if path.exists():
            frames.append(pd.read_csv(path))
    if not frames:
        raise SystemExit("No dataset CSV files found. Generate or merge datasets first.")
    return pd.concat(frames, ignore_index=True)


def choose_feature_columns(df, label_column: str, configured: List[str] | None = None) -> List[str]:
    if configured:
        return [col for col in configured if col in df.columns]

    drop = set(COMMON_DROP_COLUMNS)
    drop.add(label_column)
    numeric_cols = []
    for col in df.columns:
        if col in drop:
            continue
        if str(df[col].dtype).startswith(("int", "float", "bool")):
            numeric_cols.append(col)
    return numeric_cols


def split_by_run_id(df, train_ratio: float = 0.7, val_ratio: float = 0.15) -> Tuple[object, object, object]:
    if "run_id" not in df.columns:
        return df, df.iloc[0:0], df.iloc[0:0]

    runs = sorted(str(run) for run in df["run_id"].dropna().unique())
    if not runs:
        return df, df.iloc[0:0], df.iloc[0:0]

    train_end = max(1, int(len(runs) * train_ratio))
    val_end = max(train_end, int(len(runs) * (train_ratio + val_ratio)))
    train_runs = set(runs[:train_end])
    val_runs = set(runs[train_end:val_end])
    test_runs = set(runs[val_end:])

    train_df = df[df["run_id"].astype(str).isin(train_runs)]
    val_df = df[df["run_id"].astype(str).isin(val_runs)]
    test_df = df[df["run_id"].astype(str).isin(test_runs)]
    return train_df, val_df, test_df


def train_classifier(config_path: Path) -> None:
    require_training_deps()
    import joblib
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, classification_report
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    config = load_json(config_path)
    artifact_dir = Path(config["artifact_dir"])
    label_column = config.get("label_column", "fault_label")
    df = read_csvs(resolve_paths(config["input_csvs"]))

    if label_column not in df.columns:
        raise SystemExit(f"Missing label column: {label_column}")

    df = df.dropna(subset=[label_column]).copy()
    feature_columns = choose_feature_columns(df, label_column, config.get("feature_columns"))
    if not feature_columns:
        raise SystemExit("No numeric feature columns available for training.")

    train_df, val_df, test_df = split_by_run_id(df)
    if train_df.empty:
        raise SystemExit("Training split is empty.")

    model = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "classifier",
                RandomForestClassifier(
                    n_estimators=int(config.get("n_estimators", 100)),
                    max_depth=config.get("max_depth", 8),
                    random_state=int(config.get("random_state", 7)),
                    class_weight="balanced",
                ),
            ),
        ]
    )

    x_train = train_df[feature_columns].fillna(-1.0)
    y_train = train_df[label_column].astype(str)
    model.fit(x_train, y_train)

    metrics = {
        "model_name": config["model_name"],
        "model_type": "RandomForestClassifier",
        "train_rows": int(len(train_df)),
        "val_rows": int(len(val_df)),
        "test_rows": int(len(test_df)),
        "feature_count": int(len(feature_columns)),
        "classes": sorted(y_train.unique().tolist()),
    }

    eval_df = test_df if not test_df.empty else val_df
    if not eval_df.empty:
        y_true = eval_df[label_column].astype(str)
        y_pred = model.predict(eval_df[feature_columns].fillna(-1.0))
        metrics["eval_accuracy"] = float(accuracy_score(y_true, y_pred))
        metrics["classification_report"] = classification_report(y_true, y_pred, output_dict=True, zero_division=0)

    artifact_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, artifact_dir / "model.joblib")
    write_json(artifact_dir / "metrics.json", metrics)
    write_json(artifact_dir / "feature_columns.json", {"feature_columns": feature_columns})
    write_json(
        artifact_dir / "label_map.json",
        {"labels": {label: idx for idx, label in enumerate(metrics["classes"])}},
    )
    write_json(
        artifact_dir / "model_card.json",
        {
            "model_name": config["model_name"],
            "purpose": config.get("purpose", ""),
            "safety_note": "Offline model only. ML may request bounded actions; deterministic firmware must authorize safety actions.",
            "training_data": config["input_csvs"],
        },
    )
    print(f"trained {config['model_name']} with {len(feature_columns)} features")


def train_anomaly_detector(config_path: Path) -> None:
    require_training_deps()
    import joblib
    from sklearn.ensemble import IsolationForest
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    config = load_json(config_path)
    artifact_dir = Path(config["artifact_dir"])
    df = read_csvs(resolve_paths(config["input_csvs"]))
    label_column = config.get("label_column", "fault_label")
    healthy_label = config.get("healthy_label", "healthy")

    if label_column in df.columns:
        train_df = df[df[label_column].astype(str) == healthy_label].copy()
    else:
        train_df = df.copy()
    if train_df.empty:
        raise SystemExit("No healthy rows available for anomaly detector training.")

    feature_columns = choose_feature_columns(train_df, label_column, config.get("feature_columns"))
    if not feature_columns:
        raise SystemExit("No numeric feature columns available for anomaly detector.")

    model = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "detector",
                IsolationForest(
                    n_estimators=int(config.get("n_estimators", 100)),
                    contamination=float(config.get("contamination", 0.05)),
                    random_state=int(config.get("random_state", 7)),
                ),
            ),
        ]
    )
    model.fit(train_df[feature_columns].fillna(-1.0))

    artifact_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, artifact_dir / "model.joblib")
    write_json(
        artifact_dir / "metrics.json",
        {
            "model_name": config["model_name"],
            "model_type": "IsolationForest",
            "train_rows": int(len(train_df)),
            "feature_count": int(len(feature_columns)),
            "contamination": float(config.get("contamination", 0.05)),
        },
    )
    write_json(artifact_dir / "feature_columns.json", {"feature_columns": feature_columns})
    write_json(
        artifact_dir / "model_card.json",
        {
            "model_name": config["model_name"],
            "purpose": config.get("purpose", ""),
            "unknown_fault_rule": "anomaly_score > 0.80 and max_expert_confidence < 0.55",
        },
    )
    print(f"trained {config['model_name']} anomaly detector")


def main() -> int:
    parser = argparse.ArgumentParser(description="Train RoboMoE-Diag baseline models.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--mode", choices=["classifier", "anomaly"], default="classifier")
    args = parser.parse_args()

    if args.mode == "anomaly":
        train_anomaly_detector(args.config)
    else:
        train_classifier(args.config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
