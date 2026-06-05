# Porter Doctor

Porter Doctor is the dataset-generation, offline ML, and embedded inference
workspace for RoboMoE-Diag. The project collects hardware telemetry with Zephyr
loggers, trains compact TensorFlow/TensorFlow Lite models, evaluates them, and
exports INT8 TFLite models as C arrays for Zephyr/TFLite Micro integration.

No firmware should execute unsafe ML emergency-stop behavior. ML output may only
request bounded actions for later firmware handling.

## Project Layout

```text
data_collectors/                 Zephyr dataset logger applications
data_collectors/hardware_config.json
data_collectors/scripts/         Overlay generation helpers
ai_ml/datasets/                  Sample and collected datasets
ai_ml/dataset_tools/             Dataset merge tools
ai_ml/router_dataset_builder/    Router dataset builder
ai_ml/models/                    Training, tuning, evaluation, export scripts
docs/                            Architecture notes
zephyr_inference/                Zephyr-side model C-array export package
zephyr/, modules/, bootloader/   west-managed dependencies
```

Run commands from the repository root:

```powershell
cd "C:\Users\austi\OneDrive\Desktop\career\VirtusCo (Startup)\Porter Doctor"
```

## Python Environment

Install `uv`, create the virtual environment, and install dependencies:

```powershell
python -m pip install --user uv
uv venv
.\.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt
```

If `uv` is not on `PATH`:

```powershell
& "$env:APPDATA\Python\Python312\Scripts\uv.exe" venv
& "$env:APPDATA\Python\Python312\Scripts\uv.exe" pip install --python .\.venv\Scripts\python.exe -r requirements.txt
```

Run Python tools without activating the shell:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\evaluate_all_models.py --help
```

Install or refresh dependencies with pip:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
python -m pip install -r zephyr\scripts\requirements.txt
```

If `west` fails with `ModuleNotFoundError: colorama`, repair the system Python
environment used by `west.exe`:

```powershell
python -m pip install colorama
```

## Zephyr Workspace

Initialize or refresh Zephyr:

```powershell
.\init_local_west.ps1
west update
west zephyr-export
python -m pip install -r zephyr\scripts\requirements.txt
```

If `west` needs the user Python site path on Windows:

```powershell
$env:PYTHONPATH="$env:APPDATA\Python\Python312\site-packages"
west update
```

## Firmware Builds

### Windows one-time setup

The project path contains `(` from `VirtusCo (Startup)`. On Windows this
breaks the Ninja linker command line, so two things must be set up once per
machine before any firmware build:

**1. Copy ESP32 ROM linker scripts to `C:\zld\`**

```powershell
New-Item -ItemType Directory -Force C:\zld
$src = "modules\hal\espressif\zephyr\esp32\blobs\linker\esp32\"
Copy-Item "$src\esp32.rom.alias.ld"        C:\zld\
Copy-Item "$src\esp32.rom.ld"              C:\zld\
Copy-Item "$src\esp32.rom.api.ld"          C:\zld\
Copy-Item "$src\esp32.rom.libgcc.ld"       C:\zld\
Copy-Item "$src\esp32.rom.newlib-data.ld"  C:\zld\
Copy-Item "$src\esp32.rom.newlib-funcs.ld" C:\zld\
Copy-Item "$src\esp32.peripherals.ld"      C:\zld\
```

Re-copy if the Espressif HAL is upgraded. All build outputs go to `C:\b\`
for the same reason.

### Build everything

Build the inference smoke app and all five data-collector loggers:

```powershell
.\build_firmware.ps1
```

Build everything from scratch (deletes existing build dirs first):

```powershell
.\build_firmware.ps1 -Rebuild
```

Build then flash each image one at a time (prompts between each):

```powershell
.\build_firmware.ps1 -Flash
```

Clean rebuild and flash:

```powershell
.\build_firmware.ps1 -Rebuild -Flash
```

Build outputs go to `C:\b\<target>`:

```text
C:\b\smoke
C:\b\power_expert_logger
C:\b\motor_expert_logger
C:\b\motor_driver_expert_logger
C:\b\esp32_expert_logger
C:\b\lighting_expert_logger
```

### Build a single logger

```powershell
.\data_collectors\build_logger.ps1 -Expert power_expert_logger
.\data_collectors\build_logger.ps1 -Expert power_expert_logger -Flash
```

### Direct west commands

```powershell
west build -b esp32_devkitc/esp32/procpu data_collectors/power_expert_logger -d C:\b\power_expert_logger
west flash -d C:\b\power_expert_logger
```

Logger board and pin settings live in:

```text
data_collectors/hardware_config.json
```

Generated overlays are created at CMake configure time and should not be edited:

```text
data_collectors/<expert_logger>/boards/generated.overlay
```

## Dataset Commands

Merge all raw runs into one combined CSV:

```powershell
.\.venv\Scripts\python.exe ai_ml\dataset_tools\merge_raw_runs.py --expert all
```

Merge one expert:

```powershell
.\.venv\Scripts\python.exe ai_ml\dataset_tools\merge_raw_runs.py --expert power_expert
.\.venv\Scripts\python.exe ai_ml\dataset_tools\merge_raw_runs.py --expert motor_expert
.\.venv\Scripts\python.exe ai_ml\dataset_tools\merge_raw_runs.py --expert motor_driver_expert
.\.venv\Scripts\python.exe ai_ml\dataset_tools\merge_raw_runs.py --expert esp32_expert
.\.venv\Scripts\python.exe ai_ml\dataset_tools\merge_raw_runs.py --expert lighting_expert
```

Create one merged CSV per expert:

```powershell
.\.venv\Scripts\python.exe ai_ml\dataset_tools\merge_raw_runs.py --per-expert
```

Use custom dataset/output directories:

```powershell
.\.venv\Scripts\python.exe ai_ml\dataset_tools\merge_raw_runs.py --dataset-root ai_ml\datasets --output-dir ai_ml\datasets\merged --expert all
```

Build the router dataset:

```powershell
.\.venv\Scripts\python.exe ai_ml\router_dataset_builder\build_router_dataset.py
```

Build the router dataset with explicit paths:

```powershell
.\.venv\Scripts\python.exe ai_ml\router_dataset_builder\build_router_dataset.py --dataset-root ai_ml\datasets --config ai_ml\router_dataset_builder\router_rules.yaml --output-dir ai_ml\datasets\router
```

Show dataset tool help:

```powershell
.\.venv\Scripts\python.exe ai_ml\dataset_tools\merge_raw_runs.py --help
.\.venv\Scripts\python.exe ai_ml\router_dataset_builder\build_router_dataset.py --help
```

## Training Commands

Prepare datasets and train all current TensorFlow models in parallel:

```powershell
powershell -ExecutionPolicy Bypass -File .\train.ps1 -Python .\.venv\Scripts\python.exe
```

Install dependencies through the training script:

```powershell
powershell -ExecutionPolicy Bypass -File .\train.ps1 -Python .\.venv\Scripts\python.exe -InstallDeps
```

Skip dataset preparation and train only:

```powershell
powershell -ExecutionPolicy Bypass -File .\train.ps1 -Python .\.venv\Scripts\python.exe -SkipPrepare
```

Include placeholder model folders:

```powershell
powershell -ExecutionPolicy Bypass -File .\train.ps1 -Python .\.venv\Scripts\python.exe -IncludePlaceholders
```

Train all models sequentially:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\train_all_baselines.py
```

Train one model:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\power_expert\train.py
.\.venv\Scripts\python.exe ai_ml\models\motor_expert\train.py
.\.venv\Scripts\python.exe ai_ml\models\motor_driver_expert\train.py
.\.venv\Scripts\python.exe ai_ml\models\esp32_expert\train.py
.\.venv\Scripts\python.exe ai_ml\models\lighting_expert\train.py
.\.venv\Scripts\python.exe ai_ml\models\router\train.py
.\.venv\Scripts\python.exe ai_ml\models\anomaly_detector\train.py
```

Current trained artifacts are written to:

```text
ai_ml/models/<model_name>/artifacts/
```

Typical artifacts:

```text
model_float32.keras
model_float32.tflite
model_int8.tflite
feature_order.json
feature_columns.json
label_map.json
action_map.json
normalization_stats.json
metrics.json
model_card.json
```

## Hyperparameter Tuning And Best Candidates

Tune all models using `ai_ml/models/hyperparameter_tuning.yaml`:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\tune_hyperparameters.py
```

Tune one or more models:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\tune_hyperparameters.py --model power_expert
.\.venv\Scripts\python.exe ai_ml\models\tune_hyperparameters.py --model power_expert --model router
```

Quick tuning smoke test:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\tune_hyperparameters.py --model power_expert --max-combinations 4 --repeats 1
```

Use a custom tuning YAML:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\tune_hyperparameters.py --config ai_ml\models\hyperparameter_tuning.yaml
```

Show tuning help:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\tune_hyperparameters.py --help
```

Check trained models against ESP32 size limits:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\check_esp32_feasibility.py
```

Build a quick best-candidate package for every model:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\build_best_candidates.py
```

Build one quick best-candidate package:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\build_best_candidates.py --model power_expert
```

Run the slower full YAML search:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\build_best_candidates.py --full
```

Override search size:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\build_best_candidates.py --model power_expert --max-combinations 8 --repeats 1
```

Tune/report without locking config:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\build_best_candidates.py --model power_expert --max-combinations 2 --repeats 1 --no-apply
```

Skip specific stages:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\build_best_candidates.py --model power_expert --skip-tune
.\.venv\Scripts\python.exe ai_ml\models\build_best_candidates.py --model power_expert --skip-train
.\.venv\Scripts\python.exe ai_ml\models\build_best_candidates.py --model power_expert --skip-evaluate
```

Keep intermediate outputs:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\build_best_candidates.py --model power_expert --keep-intermediates
.\.venv\Scripts\python.exe ai_ml\models\build_best_candidates.py --model power_expert --keep-evaluation-outputs
```

Show best-candidate help:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\build_best_candidates.py --help
```

Best-candidate outputs are local generated artifacts:

```text
ai_ml/models/<model_name>/best_candidate/candidate_report.html
ai_ml/models/<model_name>/best_candidate/selected_parameters.json
ai_ml/models/<model_name>/best_candidate/selected_parameters.yaml
```

## Python Inference Commands

Run inference with default inputs:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\power_expert\infer.py
.\.venv\Scripts\python.exe ai_ml\models\motor_expert\infer.py
.\.venv\Scripts\python.exe ai_ml\models\motor_driver_expert\infer.py
.\.venv\Scripts\python.exe ai_ml\models\esp32_expert\infer.py
.\.venv\Scripts\python.exe ai_ml\models\lighting_expert\infer.py
.\.venv\Scripts\python.exe ai_ml\models\router\infer.py
.\.venv\Scripts\python.exe ai_ml\models\anomaly_detector\infer.py
```

Run inference with explicit input/output:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\power_expert\infer.py --input ai_ml\datasets\merged\power_expert_raw_merged.csv --output ai_ml\evaluation_outputs\power_expert\predictions.csv
```

Limit rows and return top-k classes:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\power_expert\infer.py --limit 5 --top-k 3
```

Show inference help:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\power_expert\infer.py --help
```

## Evaluation And Graphs

Evaluate every trained model and generate plots:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\evaluate_all_models.py
```

Evaluate one or more models:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\evaluate_all_models.py --model power_expert
.\.venv\Scripts\python.exe ai_ml\models\evaluate_all_models.py --model power_expert --model router
```

Write evaluation outputs somewhere else:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\evaluate_all_models.py --output-dir C:\tmp\porter_doctor_eval
```

Show evaluation help:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\evaluate_all_models.py --help
```

Default outputs:

```text
ai_ml/evaluation_outputs/
```

Each model evaluation includes prediction CSVs, JSON reports, model summaries,
layer tables, confusion matrices or anomaly plots, confidence/action
distributions, and architecture diagrams.

## Zephyr Inference Export And Build

Export all trained INT8 TFLite models as Zephyr-ready C arrays and metadata:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\export_zephyr_inference.py
```

Export one model:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\export_zephyr_inference.py --model power_expert
```

Export multiple selected models:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\export_zephyr_inference.py --model power_expert --model router
```

Force export source:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\export_zephyr_inference.py --source auto
.\.venv\Scripts\python.exe ai_ml\models\export_zephyr_inference.py --source best_candidate
.\.venv\Scripts\python.exe ai_ml\models\export_zephyr_inference.py --source artifacts
```

Write generated files elsewhere:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\export_zephyr_inference.py --output-dir C:\tmp\porter_zephyr_models
```

Show Zephyr export help:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\export_zephyr_inference.py --help
```

Generated model files:

```text
zephyr_inference/generated/<model>_model_data.c
zephyr_inference/generated/<model>_model_data.h
zephyr_inference/generated/<model>_metadata.c
zephyr_inference/generated/<model>_metadata.h
zephyr_inference/generated/<model>_bundle.c
zephyr_inference/generated/<model>_bundle.h
zephyr_inference/generated/<model>_manifest.json
zephyr_inference/generated/manifest.json
```

The TFLite flatbuffer is converted to a C array such as:

```c
const unsigned char porter_power_expert_model_tflite[] = { ... };
```

Build the Zephyr inference smoke app. Run the export command first so
`zephyr_inference/generated/` exists:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\export_zephyr_inference.py
west build -b esp32_devkitc/esp32/procpu zephyr_inference/smoke_app -d C:\b\smoke
```

Flash the smoke app:

```powershell
west flash -d C:\b\smoke
```

The smoke app compiles all generated model C arrays and metadata into a Zephyr
application and prints model sizes/counts. It does not invoke TFLite Micro yet.
The next embedded step is to add the TFLite Micro or LiteRT Micro runtime and
create an interpreter from `metadata->model_data`.

## End-To-End Manual Test Flows

Offline ML smoke flow:

```powershell
.\.venv\Scripts\python.exe ai_ml\dataset_tools\merge_raw_runs.py --expert all
.\.venv\Scripts\python.exe ai_ml\dataset_tools\merge_raw_runs.py --per-expert
.\.venv\Scripts\python.exe ai_ml\router_dataset_builder\build_router_dataset.py
powershell -ExecutionPolicy Bypass -File .\train.ps1 -Python .\.venv\Scripts\python.exe -SkipPrepare
.\.venv\Scripts\python.exe ai_ml\models\evaluate_all_models.py
.\.venv\Scripts\python.exe ai_ml\models\check_esp32_feasibility.py
.\.venv\Scripts\python.exe ai_ml\models\export_zephyr_inference.py
```

Best-candidate flow for one model:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\build_best_candidates.py --model power_expert
.\.venv\Scripts\python.exe ai_ml\models\export_zephyr_inference.py --model power_expert
```

Full candidate search for every model:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\build_best_candidates.py --full
.\.venv\Scripts\python.exe ai_ml\models\export_zephyr_inference.py
```

Firmware logger smoke flow:

```powershell
.\init_local_west.ps1
west update
west zephyr-export
python -m pip install -r zephyr\scripts\requirements.txt
.\build_firmware.ps1
```

Zephyr inference smoke flow:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\export_zephyr_inference.py
west build -b esp32_devkitc/esp32/procpu zephyr_inference/smoke_app -d C:\b\smoke
west flash -d C:\b\smoke
```

## Validation Commands For Development

Compile touched Python scripts:

```powershell
.\.venv\Scripts\python.exe -m py_compile ai_ml\models\export_zephyr_inference.py
.\.venv\Scripts\python.exe -m py_compile ai_ml\models\tune_hyperparameters.py ai_ml\models\build_best_candidates.py ai_ml\models\evaluate_all_models.py
```

Remove Python cache folders:

```powershell
Get-ChildItem ai_ml,data_collectors -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force
```

Check git state:

```powershell
git status --short
```

## Generated Files Not For Commit

These are generated or local-environment outputs and are ignored by git:

```text
.venv/
.west/
zephyr/
modules/
bootloader/
tools/
build/
**/boards/generated.overlay
**/artifacts/
**/best_candidate/
ai_ml/evaluation_outputs/
ai_ml/models/tuning_summary.json
ai_ml/models/*_hyperparameter_candidates.csv
zephyr_inference/generated/
__pycache__/
```

## Safety Notes

Do not add fault-generation code that can damage motors, motor drivers,
batteries, wiring, or lighting hardware. Do not add ML-controlled emergency-stop
execution. Keep board-specific pins in `data_collectors/hardware_config.json`,
not portable `src/main.c`.
