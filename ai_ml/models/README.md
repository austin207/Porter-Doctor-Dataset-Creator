# Models

Offline model training code for RoboMoE-Diag.

This folder is for Python training, evaluation, and export preparation. It does
not contain embedded inference firmware and does not make safety decisions.

## Structure

```text
models/
  architectures/
  common/
  anomaly_detector/
  router/
  power_expert/
  motor_expert/
  motor_driver_expert/
  esp32_expert/
  lighting_expert/
  encoder_expert/
  pi_expert/
```

## Install Training Dependencies

Use a Python environment on the PC or Raspberry Pi:

```powershell
python -m pip install -r ai_ml/models/requirements.txt
```

## Train One Expert

```powershell
python ai_ml/models/power_expert/train.py
python ai_ml/models/motor_expert/train.py
python ai_ml/models/motor_driver_expert/train.py
python ai_ml/models/esp32_expert/train.py
python ai_ml/models/lighting_expert/train.py
```

## Train Router

First build router rows:

```powershell
python ai_ml/router_dataset_builder/build_router_dataset.py
```

Then train:

```powershell
python ai_ml/models/router/train.py
```

## Train Anomaly Detector

The first anomaly detector trains only on rows labelled `healthy`:

```powershell
python ai_ml/models/anomaly_detector/train.py
```

## Outputs

Each model writes artifacts under:

```text
ai_ml/models/<model_name>/artifacts/
```

Typical files:

```text
model.joblib
metrics.json
feature_columns.json
label_map.json
model_card.json
```

These are offline artifacts. A later export step should convert validated models
to compact C or TFLite Micro assets for ESP32-S3.

## Architecture Specs

Explicit PRD-based architecture specs are in:

```text
ai_ml/models/architectures/model_architectures.py
```

Generate a full JSON summary:

```powershell
python ai_ml/models/architectures/model_architectures.py --summary
```

The current architecture target is:

- Embedded router: small MLP, Dense 16, Dense 8, softmax over experts
- Embedded experts: small MLP, Dense 16, Dense 8, softmax over fault classes
- Embedded anomaly detector: tiny autoencoder candidate, currently baseline-trained with IsolationForest
- Pi unknown-fault analyzer: temporal sequence embedding plus clustering, similarity search, and root-cause ranking
