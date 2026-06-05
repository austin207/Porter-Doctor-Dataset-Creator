# Model Architectures

Architecture definitions for RoboMoE-Diag models.

These files describe the intended model shapes from the PRD and model
architecture context. They are not embedded inference code. They are the source
of truth for later training, validation, quantization, and export to ESP32-S3.

## Included Architectures

Embedded ESP32-S3 side:

- `anomaly_detector`
- `router`
- `power_expert`
- `motor_expert`
- `motor_driver_expert`
- `esp32_expert`
- `encoder_expert`
- `lighting_expert`

Robot computer side:

- `pi_expert`
- `unknown_fault_sequence_analyzer`

## Current Assumptions

The PRD gives suggested model families and layer sizes, but not exact final
input feature lists for every subsystem. Where exact inputs are not fully known,
the architecture uses the PRD telemetry and feature requirements as the initial
feature contract.

Most embedded experts start as small MLPs over sliding-window features:

```text
features -> Dense 32 -> ReLU -> Dense 16 -> ReLU -> fault/action heads
```

ESP32 timing health and lighting models use smaller variants where the feature
space is simpler. The router uses top-2 or top-3 routing and does not make final
fault decisions.

## Generate Summary

```powershell
python ai_ml/models/architectures/model_architectures.py --summary
```

Output:

```text
ai_ml/models/architectures/architecture_summary.json
```
