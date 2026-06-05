# Porter Doctor

Repository: Porter-Doctor-Dataset-Creator

Porter Doctor is the dataset-generation and embedded fault-diagnosis workspace
for RoboMoE-Diag.

## Goal

Build a modular robot fault diagnosis system using real hardware telemetry from
multiple expert loggers, then later train compact Mixture-of-Experts models.

No ML inference or emergency-stop control is implemented in the firmware yet.

## Project Layout

```text
Porter Doctor/
  data_collectors/
    hardware_config.json
    build_logger.ps1
    common/
    scripts/
    power_expert_logger/
    motor_expert_logger/
    motor_driver_expert_logger/
    esp32_expert_logger/
    lighting_expert_logger/

  ai_ml/
    datasets/
    dataset_tools/
    models/
    router_dataset_builder/
    training/

  docs/
    MODEL_ARCHITECTURE.md

  zephyr/
  modules/
  bootloader/
  tools/
```

`data_collectors/` contains Zephyr firmware and hardware configuration.

`ai_ml/` contains sample datasets, merge tools, router dataset tooling, baseline
model code, and future training/export scaffolds. These are offline Python
models and planning files, not embedded ESP32 inference artifacts.

`docs/MODEL_ARCHITECTURE.md` captures the current model architecture plan:
feature windows, compact MLP shapes, router behavior, anomaly handling, and
export artifact expectations.

`zephyr/`, `modules/`, `bootloader/`, and `tools/` are downloaded by `west` and
are ignored by git.

## Recommended Build Order

1. `power_expert_logger`
2. `motor_expert_logger`
3. `motor_driver_expert_logger`
4. `esp32_expert_logger`
5. `lighting_expert_logger`
6. `ai_ml/router_dataset_builder`

Start with the Power Expert because it only needs ESP32, INA226, and microSD.

## Local Zephyr Workspace

This repo is intended to be the Zephyr workspace root. From this folder:

```powershell
.\init_local_west.ps1
west update
west zephyr-export
python -m pip install -r zephyr/scripts/requirements.txt
```

Build a logger with the helper:

```powershell
.\data_collectors\build_logger.ps1 -Expert power_expert_logger
```

Build and flash:

```powershell
.\data_collectors\build_logger.ps1 -Expert power_expert_logger -Flash
```

Direct west build example:

```powershell
west build -b esp32_devkitc/esp32/procpu data_collectors/power_expert_logger -d build/power_expert_logger
```

## Hardware Pin Configuration

Edit this file instead of hand-editing Zephyr overlays:

```text
data_collectors/hardware_config.json
```

The important board fields are:

```json
{
  "active_board": "esp32_devkitc_procpu",
  "boards": {
    "esp32_devkitc_procpu": {
      "zephyr_board": "esp32_devkitc/esp32/procpu"
    }
  }
}
```

Each logger automatically generates its Zephyr overlay at CMake configure time:

```text
data_collectors/<expert_logger>/boards/generated.overlay
```

Do not edit `boards/generated.overlay` directly. It is generated from
`data_collectors/hardware_config.json`.

To change SD card pins, edit:

```json
"sd_card": {
  "sck_gpio": 18,
  "miso_gpio": 19,
  "mosi_gpio": 23,
  "cs_gpio": 25
}
```

To enable a UART telemetry link, set the UART and expert telemetry alias to
`enabled: true`. Example for the Motor Expert:

```json
"uarts": {
  "uart1": {
    "enabled": true,
    "tx_gpio": 17,
    "rx_gpio": 16,
    "baudrate": 115200
  }
},
"experts": {
  "motor": {
    "telemetry_uart": {
      "enabled": true,
      "uart": "uart1",
      "alias": "motor-tel-uart"
    }
  }
}
```

Current generator support is for ESP32 DevKitC style overlays. STM32 can be
added by adding an STM32 emitter in
`data_collectors/scripts/generate_zephyr_overlay.py` while keeping the same
`hardware_config.json` structure.

## Sample Datasets And Merging

Sample dataset files are included under:

```text
ai_ml/datasets/
```

Each expert has:

```text
raw/healthy_run_001.csv
events/healthy_run_001_events.csv
metadata/healthy_run_001.txt
features/
```

Merge all raw run files into one CSV:

```powershell
python ai_ml/dataset_tools/merge_raw_runs.py --expert all
```

Merge one expert:

```powershell
python ai_ml/dataset_tools/merge_raw_runs.py --expert motor_expert
```

Create one merged raw CSV per expert:

```powershell
python ai_ml/dataset_tools/merge_raw_runs.py --per-expert
```

Build the first router dataset:

```powershell
python ai_ml/router_dataset_builder/build_router_dataset.py
```

Train baseline models:

```powershell
python ai_ml/models/train_all_baselines.py
```

Train all currently trainable baseline models in parallel:

```powershell
.\train.ps1
```

If your PowerShell execution policy blocks local scripts, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\train.ps1
```

If training dependencies are missing, install them through the script:

```powershell
powershell -ExecutionPolicy Bypass -File .\train.ps1 -InstallDeps
```

This prepares merged datasets and router rows, then trains Power, Motor, Motor
Driver, ESP32, Lighting, Router, and Anomaly Detector models at the same time.
Artifacts are written to:

```text
ai_ml/models/<model_name>/artifacts/
```

Current artifacts are scikit-learn baseline `.joblib` models plus JSON metadata.
They are not TensorFlow Lite files yet. The embedded target architecture is
still INT8 TensorFlow Lite Micro / LiteRT Micro style MLPs for ESP32-S3, but the
TFLite export step is planned under `ai_ml/training/*/export_tflite_int8.py` and
is not implemented yet.
