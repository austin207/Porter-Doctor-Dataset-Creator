from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")


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


def require_tensorflow_deps():
    require_training_deps()
    try:
        import tensorflow as tf  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "Missing TensorFlow dependency. Install with: "
            "python -m pip install -r requirements.txt"
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


def split_by_run_id_with_label_coverage(df, label_column: str):
    train_df, val_df, test_df = split_by_run_id(df)
    if label_column not in df.columns or train_df.empty:
        return train_df, val_df, test_df

    all_labels = set(df[label_column].astype(str).dropna().unique())
    train_labels = set(train_df[label_column].astype(str).dropna().unique())
    if all_labels.issubset(train_labels):
        return train_df, val_df, test_df

    # Tiny generated sample datasets may only have one run per class. In that
    # case, keep every class trainable and treat metrics as smoke-test metrics.
    return df.copy(), df.copy(), df.iloc[0:0].copy()


ACTION_LABELS = [
    "ACTION_NONE",
    "ACTION_LOG_ONLY",
    "ACTION_WARN_OPERATOR",
    "ACTION_LIMIT_SPEED",
    "ACTION_CONTROLLED_STOP",
    "ACTION_ENTER_SAFE_STATE",
    "ACTION_REQUEST_ESTOP",
]


FAULT_ACTIONS = {
    "healthy": "ACTION_NONE",
    "battery_voltage_sag": "ACTION_LIMIT_SPEED",
    "battery_undervoltage": "ACTION_ENTER_SAFE_STATE",
    "loose_power_connection": "ACTION_ENTER_SAFE_STATE",
    "regulator_instability": "ACTION_CONTROLLED_STOP",
    "excessive_system_load": "ACTION_LIMIT_SPEED",
    "motor_stall": "ACTION_CONTROLLED_STOP",
    "excessive_load": "ACTION_LIMIT_SPEED",
    "motor_disconnected": "ACTION_CONTROLLED_STOP",
    "abnormal_vibration": "ACTION_WARN_OPERATOR",
    "bearing_degradation": "ACTION_WARN_OPERATOR",
    "driver_overcurrent": "ACTION_REQUEST_ESTOP",
    "driver_overtemperature": "ACTION_CONTROLLED_STOP",
    "driver_disabled": "ACTION_CONTROLLED_STOP",
    "driver_fault_pin_active": "ACTION_REQUEST_ESTOP",
    "undervoltage_lockout": "ACTION_ENTER_SAFE_STATE",
    "heartbeat_lost": "ACTION_CONTROLLED_STOP",
    "packet_loss": "ACTION_WARN_OPERATOR",
    "watchdog_reset": "ACTION_ENTER_SAFE_STATE",
    "brownout_reset": "ACTION_ENTER_SAFE_STATE",
    "task_overrun": "ACTION_WARN_OPERATOR",
    "firmware_freeze": "ACTION_CONTROLLED_STOP",
    "led_disconnected": "ACTION_WARN_OPERATOR",
    "brightness_mismatch": "ACTION_LOG_ONLY",
    "light_driver_fault": "ACTION_CONTROLLED_STOP",
    "lighting_overcurrent": "ACTION_CONTROLLED_STOP",
    "lighting_short_suspected": "ACTION_REQUEST_ESTOP",
    "power_expert": "ACTION_LOG_ONLY",
    "motor_expert": "ACTION_LOG_ONLY",
    "motor_driver_expert": "ACTION_LOG_ONLY",
    "esp32_expert": "ACTION_LOG_ONLY",
    "lighting_expert": "ACTION_LOG_ONLY",
    "unknown_fault": "ACTION_WARN_OPERATOR",
}


DEFAULT_HIDDEN_LAYERS = {
    "power_expert": [32, 16],
    "motor_expert": [32, 16],
    "motor_driver_expert": [32, 16],
    "esp32_expert": [24, 12],
    "lighting_expert": [16, 8],
    "moe_router": [32, 16],
}


def action_for_label(label: str) -> str:
    return FAULT_ACTIONS.get(label, "ACTION_WARN_OPERATOR")


def normalize_frames(train_df, val_df, test_df, feature_columns: List[str]):
    import numpy as np

    x_train = train_df[feature_columns].fillna(-1.0).astype("float32")
    x_val = val_df[feature_columns].fillna(-1.0).astype("float32") if not val_df.empty else x_train.iloc[0:0]
    x_test = test_df[feature_columns].fillna(-1.0).astype("float32") if not test_df.empty else x_train.iloc[0:0]

    mean = x_train.mean(axis=0).astype("float32")
    std = x_train.std(axis=0).replace(0, 1.0).fillna(1.0).astype("float32")

    return (
        ((x_train - mean) / std).to_numpy(dtype=np.float32),
        ((x_val - mean) / std).to_numpy(dtype=np.float32),
        ((x_test - mean) / std).to_numpy(dtype=np.float32),
        {
            "mean": {column: float(mean[column]) for column in feature_columns},
            "std": {column: float(std[column]) for column in feature_columns},
        },
    )


def label_indices(values, labels: List[str]) -> List[int]:
    index = {label: idx for idx, label in enumerate(labels)}
    return [index[str(value)] for value in values]


def build_classifier_model(
    input_dim: int,
    hidden_layers: List[int],
    class_count: int,
    action_count: int,
    learning_rate: float = 0.001,
):
    import tensorflow as tf

    inputs = tf.keras.Input(shape=(input_dim,), name="features")
    x = inputs
    for layer_index, units in enumerate(hidden_layers):
        x = tf.keras.layers.Dense(int(units), activation="relu", name=f"dense_{layer_index + 1}")(x)

    fault_output = tf.keras.layers.Dense(class_count, activation="softmax", name="fault_output")(x)
    action_output = tf.keras.layers.Dense(action_count, activation="softmax", name="action_output")(x)
    model = tf.keras.Model(inputs=inputs, outputs=[fault_output, action_output])
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=learning_rate),
        loss={
            "fault_output": "sparse_categorical_crossentropy",
            "action_output": "sparse_categorical_crossentropy",
        },
        loss_weights={"fault_output": 1.0, "action_output": 0.3},
        metrics={"fault_output": ["accuracy"], "action_output": ["accuracy"]},
    )
    return model


def representative_dataset(x_train):
    for row in x_train[: min(len(x_train), 100)]:
        yield [row.reshape(1, -1)]


def export_tflite_models(model, artifact_dir: Path, x_train) -> Dict[str, str]:
    import tensorflow as tf

    outputs = {}
    float_converter = tf.lite.TFLiteConverter.from_keras_model(model)
    float_model = float_converter.convert()
    float_path = artifact_dir / "model_float32.tflite"
    float_path.write_bytes(float_model)
    outputs["float32_tflite"] = str(float_path)

    int8_converter = tf.lite.TFLiteConverter.from_keras_model(model)
    int8_converter.optimizations = [tf.lite.Optimize.DEFAULT]
    int8_converter.representative_dataset = lambda: representative_dataset(x_train)
    int8_converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    int8_converter.inference_input_type = tf.int8
    int8_converter.inference_output_type = tf.int8
    int8_model = int8_converter.convert()
    int8_path = artifact_dir / "model_int8.tflite"
    int8_path.write_bytes(int8_model)
    outputs["int8_tflite"] = str(int8_path)
    return outputs


def train_tensorflow_classifier(config_path: Path) -> None:
    require_tensorflow_deps()
    import numpy as np

    config = load_json(config_path)
    artifact_dir = Path(config["artifact_dir"])
    label_column = config.get("label_column", "fault_label")
    df = read_csvs(resolve_paths(config["input_csvs"]))

    if label_column not in df.columns:
        raise SystemExit(f"Missing label column: {label_column}")

    df = df.dropna(subset=[label_column]).copy()
    feature_columns = choose_feature_columns(df, label_column, config.get("feature_columns"))
    if not feature_columns:
        raise SystemExit("No numeric feature columns available for TensorFlow training.")

    train_df, val_df, test_df = split_by_run_id_with_label_coverage(df, label_column)
    if train_df.empty:
        raise SystemExit("Training split is empty.")

    labels = sorted(str(label) for label in df[label_column].dropna().unique())
    actions = ACTION_LABELS
    hidden_layers = config.get("hidden_layers") or DEFAULT_HIDDEN_LAYERS.get(config["model_name"], [32, 16])
    x_train, x_val, x_test, normalization_stats = normalize_frames(train_df, val_df, test_df, feature_columns)

    y_train_fault = np.array(label_indices(train_df[label_column].astype(str), labels), dtype=np.int32)
    y_train_action = np.array(label_indices([action_for_label(label) for label in train_df[label_column].astype(str)], actions), dtype=np.int32)

    validation_data = None
    if len(x_val):
        y_val_fault = np.array(label_indices(val_df[label_column].astype(str), labels), dtype=np.int32)
        y_val_action = np.array(label_indices([action_for_label(label) for label in val_df[label_column].astype(str)], actions), dtype=np.int32)
        validation_data = (x_val, {"fault_output": y_val_fault, "action_output": y_val_action})

    model = build_classifier_model(
        len(feature_columns),
        hidden_layers,
        len(labels),
        len(actions),
        float(config.get("learning_rate", 0.001)),
    )
    callbacks = []
    if validation_data is not None:
        callbacks.append(
            __import__("tensorflow").keras.callbacks.EarlyStopping(
                monitor="val_fault_output_accuracy",
                patience=int(config.get("early_stopping_patience", 20)),
                restore_best_weights=True,
                mode="max",
            )
        )

    history = model.fit(
        x_train,
        {"fault_output": y_train_fault, "action_output": y_train_action},
        validation_data=validation_data,
        epochs=int(config.get("epochs", 120)),
        batch_size=int(config.get("batch_size", 16)),
        verbose=0,
        callbacks=callbacks,
    )

    artifact_dir.mkdir(parents=True, exist_ok=True)
    keras_path = artifact_dir / "model_float32.keras"
    model.save(keras_path)
    tflite_outputs = export_tflite_models(model, artifact_dir, x_train)

    metrics = {
        "model_name": config["model_name"],
        "model_type": "tensorflow_keras_mlp",
        "train_rows": int(len(train_df)),
        "val_rows": int(len(val_df)),
        "test_rows": int(len(test_df)),
        "feature_count": int(len(feature_columns)),
        "classes": labels,
        "actions": actions,
        "hidden_layers": hidden_layers,
        "epochs_run": int(len(history.history.get("loss", []))),
        "final_train_fault_accuracy": float(history.history.get("fault_output_accuracy", [0.0])[-1]),
    }
    if len(x_test):
        y_test_fault = np.array(label_indices(test_df[label_column].astype(str), labels), dtype=np.int32)
        predictions = model.predict(x_test, verbose=0)[0].argmax(axis=1)
        metrics["test_fault_accuracy"] = float((predictions == y_test_fault).mean())

    write_json(artifact_dir / "metrics.json", metrics)
    write_json(artifact_dir / "feature_order.json", {"feature_order": feature_columns})
    write_json(artifact_dir / "feature_columns.json", {"feature_columns": feature_columns})
    write_json(artifact_dir / "label_map.json", {"labels": {label: idx for idx, label in enumerate(labels)}})
    write_json(artifact_dir / "action_map.json", {"actions": {label: idx for idx, label in enumerate(actions)}})
    write_json(artifact_dir / "normalization_stats.json", normalization_stats)
    write_json(
        artifact_dir / "model_card.json",
        {
            "model_name": config["model_name"],
            "purpose": config.get("purpose", ""),
            "framework": "TensorFlow/Keras",
            "artifacts": {
                "keras": str(keras_path),
                **tflite_outputs,
            },
            "safety_note": "Offline model artifact only. ML may request bounded actions; deterministic firmware must authorize safety actions.",
        },
    )
    print(f"trained {config['model_name']} TensorFlow model and exported TFLite artifacts")


def build_autoencoder(input_dim: int, hidden_layers: List[int], learning_rate: float = 0.001):
    import tensorflow as tf

    if len(hidden_layers) < 3:
        hidden_layers = [16, 8, 16]
    inputs = tf.keras.Input(shape=(input_dim,), name="features")
    x = inputs
    for layer_index, units in enumerate(hidden_layers):
        x = tf.keras.layers.Dense(int(units), activation="relu", name=f"autoencoder_dense_{layer_index + 1}")(x)
    outputs = tf.keras.layers.Dense(input_dim, activation="linear", name="reconstruction")(x)
    model = tf.keras.Model(inputs=inputs, outputs=outputs)
    model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=learning_rate), loss="mse", metrics=["mae"])
    return model


def train_tensorflow_anomaly_detector(config_path: Path) -> None:
    require_tensorflow_deps()
    import numpy as np

    config = load_json(config_path)
    artifact_dir = Path(config["artifact_dir"])
    df = read_csvs(resolve_paths(config["input_csvs"]))
    label_column = config.get("label_column", "fault_label")
    healthy_label = config.get("healthy_label", "healthy")

    train_df = df[df[label_column].astype(str) == healthy_label].copy() if label_column in df.columns else df.copy()
    if train_df.empty:
        raise SystemExit("No healthy rows available for anomaly detector training.")

    feature_columns = choose_feature_columns(train_df, label_column, config.get("feature_columns"))
    if not feature_columns:
        raise SystemExit("No numeric feature columns available for anomaly detector.")

    train_split, val_split, test_split = split_by_run_id(train_df)
    x_train, x_val, x_test, normalization_stats = normalize_frames(train_split, val_split, test_split, feature_columns)
    model = build_autoencoder(
        len(feature_columns),
        config.get("hidden_layers", [16, 8, 16]),
        float(config.get("learning_rate", 0.001)),
    )
    validation_data = (x_val, x_val) if len(x_val) else None
    history = model.fit(
        x_train,
        x_train,
        validation_data=validation_data,
        epochs=int(config.get("epochs", 120)),
        batch_size=int(config.get("batch_size", 16)),
        verbose=0,
    )

    artifact_dir.mkdir(parents=True, exist_ok=True)
    keras_path = artifact_dir / "model_float32.keras"
    model.save(keras_path)
    tflite_outputs = export_tflite_models(model, artifact_dir, x_train)

    recon = model.predict(x_train, verbose=0)
    train_errors = ((x_train - recon) ** 2).mean(axis=1)
    threshold = float(np.quantile(train_errors, 0.95))

    write_json(
        artifact_dir / "metrics.json",
        {
            "model_name": config["model_name"],
            "model_type": "tensorflow_keras_autoencoder",
            "train_rows": int(len(train_split)),
            "val_rows": int(len(val_split)),
            "test_rows": int(len(test_split)),
            "feature_count": int(len(feature_columns)),
            "epochs_run": int(len(history.history.get("loss", []))),
            "reconstruction_error_threshold_p95": threshold,
        },
    )
    write_json(artifact_dir / "feature_order.json", {"feature_order": feature_columns})
    write_json(artifact_dir / "feature_columns.json", {"feature_columns": feature_columns})
    write_json(artifact_dir / "normalization_stats.json", normalization_stats)
    write_json(
        artifact_dir / "model_card.json",
        {
            "model_name": config["model_name"],
            "purpose": config.get("purpose", ""),
            "framework": "TensorFlow/Keras",
            "artifacts": {
                "keras": str(keras_path),
                **tflite_outputs,
            },
            "unknown_fault_rule": "reconstruction_error > threshold and max_expert_confidence < 0.55",
        },
    )
    print(f"trained {config['model_name']} TensorFlow autoencoder and exported TFLite artifacts")


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
