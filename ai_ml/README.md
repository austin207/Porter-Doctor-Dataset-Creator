# AI ML

Dataset examples and offline tooling for Porter Doctor / RoboMoE-Diag.

This folder contains:

```text
  datasets/
  dataset_tools/
  models/
  router_dataset_builder/
  training/
```

No embedded ML inference is implemented here yet. Current tooling is focused on:

- sample dataset layout
- merging raw run CSV files
- building the first rule-based MoE router dataset
- TensorFlow/Keras training code for anomaly, router, and subsystem expert models
- model architecture planning and placeholder training/export pipelines

Create and use the local `uv` environment from the repository root:

```powershell
python -m pip install --user uv
uv venv
.\.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt
```

On Windows, if `uv` is installed but not on `PATH`, replace `uv` with:

```powershell
& "$env:APPDATA\Python\Python312\Scripts\uv.exe"
```

Without activating the shell:

```powershell
uv pip install --python .\.venv\Scripts\python.exe -r requirements.txt
.\.venv\Scripts\python.exe ai_ml/models/tune_hyperparameters.py --model power_expert
```

Merge all raw run files:

```powershell
python ai_ml/dataset_tools/merge_raw_runs.py --expert all
```

Build the router dataset:

```powershell
python ai_ml/router_dataset_builder/build_router_dataset.py
```

Train TensorFlow models:

```powershell
python ai_ml/models/train_all_baselines.py
```

Train all currently trainable TensorFlow models in parallel from the repository
root:

```powershell
.\train.ps1
```

If local script execution is blocked:

```powershell
powershell -ExecutionPolicy Bypass -File .\train.ps1
```

If dependencies are missing:

```powershell
powershell -ExecutionPolicy Bypass -File .\train.ps1 -InstallDeps
```

Current training outputs are TensorFlow/Keras and TensorFlow Lite artifacts
under `ai_ml/models/<model_name>/artifacts/`:

```text
model_float32.keras
model_float32.tflite
model_int8.tflite
feature_order.json
label_map.json
action_map.json
normalization_stats.json
metrics.json
```

The firmware-side TensorFlow Lite Micro / LiteRT Micro integration is not wired
into Zephyr yet.

Train one model:

```powershell
python ai_ml/models/power_expert/train.py
python ai_ml/models/anomaly_detector/train.py
```

Tune all TensorFlow/Keras hyperparameters:

```powershell
python ai_ml/models/tune_hyperparameters.py
```

Tune one model:

```powershell
python ai_ml/models/tune_hyperparameters.py --model power_expert
```

Tuning writes repeat-aware candidate tables and ESP32-aware recommendations:

```text
ai_ml/models/<model_name>/artifacts/hyperparameter_candidates.csv
ai_ml/models/<model_name>/artifacts/hyperparameter_tuning_results.json
ai_ml/models/<model_name>/artifacts/recommended_config_patch.json
```

Check trained model size against current ESP32 limits:

```powershell
python ai_ml/models/check_esp32_feasibility.py
```

Export available best-candidate models to Zephyr-ready C files:

```powershell
python ai_ml/models/export_zephyr_inference.py
```

Export one model:

```powershell
python ai_ml/models/export_zephyr_inference.py --model power_expert
```

Outputs are written to `zephyr_inference/generated/` and include
the INT8 TFLite bytes, feature normalization metadata, labels, actions, and a
bundle struct for firmware code.

Build and lock a quick best-candidate model package:

```powershell
python ai_ml/models/build_best_candidates.py --model power_expert
```

Build quick best-candidate packages for every model:

```powershell
python ai_ml/models/build_best_candidates.py
```

Run the slower full YAML search:

```powershell
python ai_ml/models/build_best_candidates.py --full
```

The generated candidate package includes final artifacts, evaluation plots,
ESP32 feasibility output, and an HTML report:

```text
ai_ml/models/<model_name>/best_candidate/candidate_report.html
ai_ml/models/<model_name>/best_candidate/selected_parameters.json
ai_ml/models/<model_name>/best_candidate/selected_parameters.yaml
```

`build_best_candidates.py` tunes candidate architectures, repeats training for
stability, ranks candidates with ESP32 size pressure, locks the selected fields
into the model config, retrains, evaluates, checks ESP32 feasibility, writes the
best-candidate package, and cleans transient outputs by default.

The builder defaults to a practical quick search of 8 candidates x 1 repeat per
model. Use `--full` for the YAML defaults, or pass `--max-combinations` and
`--repeats` to control runtime manually.

Run inference for one model:

```powershell
python ai_ml/models/power_expert/infer.py --input ai_ml/datasets/merged/power_expert_raw_merged.csv
```

Evaluate all trained models and generate plots:

```powershell
python ai_ml/models/evaluate_all_models.py
```

Outputs are written to `ai_ml/evaluation_outputs/` and include prediction
CSVs, JSON reports, model summaries, layer tables, confusion matrices,
confidence/action distributions, anomaly reconstruction plots, and architecture
diagrams.

The tuning search spaces live in:

```text
ai_ml/models/hyperparameter_tuning.yaml
```

Architecture planning:

```text
docs/MODEL_ARCHITECTURE.md
ai_ml/models/architectures/
ai_ml/training/
```
