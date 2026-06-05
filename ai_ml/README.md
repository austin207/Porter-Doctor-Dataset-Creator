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
