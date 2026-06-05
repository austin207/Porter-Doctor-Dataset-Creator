#!/usr/bin/env python3
"""Shared placeholders for future training pipeline scripts."""

from __future__ import annotations

from pathlib import Path


def not_implemented_yet(step: str, model_name: str) -> None:
    message = (
        f"{model_name}: {step} is a placeholder. "
        "Implement after real labelled feature datasets are available."
    )
    raise SystemExit(message)


def model_dir_from_file(file_path: str) -> Path:
    return Path(file_path).resolve().parent
