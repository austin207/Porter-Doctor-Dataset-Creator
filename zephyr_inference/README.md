# Zephyr Inference Export

This folder holds generated firmware-side model files for hardware inference
tests. It stays outside `data_collectors/` so dataset loggers and model
inference exports remain separate.

---

## Generating C files

Run from the repository root (`Porter Doctor\`).

Generate Zephyr-ready C files for every trained model:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\export_zephyr_inference.py
```

Generate one model:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\export_zephyr_inference.py --model power_expert
```

Force export source:

```powershell
.\.venv\Scripts\python.exe ai_ml\models\export_zephyr_inference.py --source best_candidate
.\.venv\Scripts\python.exe ai_ml\models\export_zephyr_inference.py --source artifacts
```

Generated files are written to `zephyr_inference/generated/`. Each model produces:

```text
<model>_model_data.h/.c    INT8 .tflite bytes as a C array
<model>_metadata.h/.c      feature order, normalization stats, labels, actions
<model>_bundle.h/.c        one porter_model_metadata struct for Zephyr code
<model>_manifest.json      source path, size, metrics, and tuning metadata
```

The shared helpers are:

```text
include/porter_inference.h
src/porter_inference.c
```

These normalize feature vectors and decode classifier outputs. They do not
execute TensorFlow Lite Micro. To run inference on ESP32, add TFLite Micro or
LiteRT Micro, create an interpreter from `metadata->model_data`, copy
normalized features into the input tensor, invoke it, then pass output tensors
to `porter_fill_classification_result()`.

The generated folder is ignored by git because it contains model artifacts.

---

## Building the smoke app

All commands run from the repository root (`Porter Doctor\`).

### Step 1 — First-time workspace setup (run once per machine)

Initialize the west workspace and pull all dependencies:

```powershell
.\init_local_west.ps1
west update
west zephyr-export
python -m pip install -r zephyr\scripts\requirements.txt
```

Install Python venv dependencies:

```powershell
python -m pip install --user uv
uv venv
.\.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt
```

### Step 2 — Windows path workaround (run once per machine)

The project path contains `(` from `VirtusCo (Startup)`. On Windows,
`cmd.exe` parses `(` as a group start inside batch strings, which breaks the
Ninja-generated linker command line for every Zephyr build in this repo.
Two things must be set up once:

**Copy ESP32 ROM linker scripts to `C:\zld\`**

```powershell
New-Item -ItemType Directory -Force C:\zld
$src = "modules\hal\espressif\zephyr\esp32\blobs\linker\esp32"
Copy-Item "$src\esp32.rom.alias.ld"        C:\zld\
Copy-Item "$src\esp32.rom.ld"              C:\zld\
Copy-Item "$src\esp32.rom.api.ld"          C:\zld\
Copy-Item "$src\esp32.rom.libgcc.ld"       C:\zld\
Copy-Item "$src\esp32.rom.newlib-data.ld"  C:\zld\
Copy-Item "$src\esp32.rom.newlib-funcs.ld" C:\zld\
Copy-Item "$src\esp32.peripherals.ld"      C:\zld\
```

Re-copy if the Espressif HAL is upgraded. All build output goes to `C:\b\`
for the same path reason — this directory is created automatically by west.

### Step 3 — Generate the C files

```powershell
.\.venv\Scripts\python.exe ai_ml\models\export_zephyr_inference.py
```

### Step 4 — Build

```powershell
west build -b esp32_devkitc/esp32/procpu zephyr_inference/smoke_app -d C:\b\smoke
```

A successful build ends with:

```
Memory region         Used Size  Region Size  %age Used
           FLASH:      ...
...
Successfully created esp32 image.
```

Subsequent builds are incremental. To force a clean rebuild:

```powershell
Remove-Item -Recurse -Force C:\b\smoke
west build -b esp32_devkitc/esp32/procpu zephyr_inference/smoke_app -d C:\b\smoke
```

### Step 5 — Flash

Connect the ESP32 via USB, then:

```powershell
west flash -d C:\b\smoke
```

### Step 6 — Monitor serial output

```powershell
west espressif monitor -d C:\b\smoke
```

Or open any serial terminal (PuTTY, Tera Term, etc.) at **115200 baud** on the
ESP32's COM port. The app prints one line per model on boot:

```
Porter Zephyr inference smoke app
power_expert: model=XXXXX bytes features=5 labels=6 actions=7 threshold=0.000000
motor_expert: model=XXXXX bytes features=6 labels=5 actions=7 threshold=0.000000
motor_driver_expert: model=XXXXX bytes features=5 labels=5 actions=7 threshold=0.000000
esp32_expert: model=XXXXX bytes features=6 labels=5 actions=7 threshold=0.000000
lighting_expert: model=XXXXX bytes features=5 labels=5 actions=7 threshold=0.000000
router: model=XXXXX bytes features=7 labels=7 actions=7 threshold=0.000000
anomaly_detector: model=XXXXX bytes features=7 labels=1 actions=3 threshold=0.000000
```

Press `Ctrl+]` to exit the west monitor.

---

## Building all firmware at once

`build_firmware.ps1` at the repo root builds the smoke app and all five
data-collector loggers in one command. See the root `README.md` for full
usage.

```powershell
.\build_firmware.ps1            # incremental build of everything
.\build_firmware.ps1 -Rebuild   # clean rebuild of everything
.\build_firmware.ps1 -Flash     # build then flash each image with prompts
```
