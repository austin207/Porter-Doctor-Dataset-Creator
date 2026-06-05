# Zephyr Inference Export

This folder holds generated firmware-side model files for hardware inference
tests. It stays outside `data_collectors/` so dataset loggers and model
inference exports remain separate.

Generate Zephyr-ready C files for every trained model:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\export_zephyr_inference.py
```

Generate one model:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\export_zephyr_inference.py --model power_expert
```

The default source mode is `auto`: use `best_candidate` artifacts when present,
otherwise use the current model `artifacts/` folder. Force a source with:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\export_zephyr_inference.py --source best_candidate
.\.venv\Scripts\python.exe ai_ml\models\export_zephyr_inference.py --source artifacts
```

Generated files are written to:

```text
zephyr_inference/generated/
```

Each model includes:

```text
<model>_model_data.h/.c    INT8 .tflite bytes as a C array
<model>_metadata.h/.c      feature order, normalization stats, labels, actions
<model>_bundle.h/.c        one porter_model_metadata struct for Zephyr code
<model>_manifest.json      source path, size, metrics, and tuning metadata
```

The shared helper files are:

```text
include/porter_inference.h
src/porter_inference.c
```

These helpers normalize feature vectors and decode classifier outputs. They do
not execute TensorFlow Lite Micro by themselves. To run inference on ESP32, add
the TFLite Micro or LiteRT Micro runtime to the Zephyr application, create an
interpreter from `<model>_metadata.model_data`, copy normalized features into the
input tensor, invoke the interpreter, then pass classifier output tensors to
`porter_fill_classification_result()`.

Example include:

```c
#include "power_expert_bundle.h"

static float raw_features[5];
static float normalized_features[5];

porter_normalize_features(raw_features, &porter_power_expert_metadata,
			  normalized_features);
```

The generated folder is ignored by git because it contains model artifacts.
