"""
Central path configuration for the Word-to-Markdown app.

All runtime locations (outputs, temp, logs, the MIP helper) are routed
through environment variables loaded from a local .env file. The defaults
keep everything portable under ``C:/temp/W2MD`` so the app never depends
on per-user paths like ``C:\\Users\\<name>\\...``.

Layout (defaults):
    C:/temp/W2MD/
        Outputs/
            Single/        single-file conversions
            Batch/         batch conversion outputs
            Images/        images extracted by Docling
        Temp/
            Cloud/         cloud-mode downloads
            Protected/     decrypted MIP working copies
        Logs/              app.log + rotated history
        MipHelper/         published MipHelper.exe
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except ImportError:
    # python-dotenv is recommended but not strictly required at import time.
    pass


def _path_from_env(name: str, default: Path) -> Path:
    raw = os.getenv(name)
    if raw and raw.strip():
        return Path(raw.strip()).expanduser()
    return default


APP_DATA_ROOT: Path = _path_from_env("APP_DATA_ROOT", Path("C:/temp/W2MD"))
OUTPUTS_ROOT: Path = _path_from_env("OUTPUTS_ROOT", APP_DATA_ROOT / "Outputs")
TEMP_ROOT: Path = _path_from_env("TEMP_ROOT", APP_DATA_ROOT / "Temp")
LOGS_ROOT: Path = _path_from_env("LOGS_ROOT", APP_DATA_ROOT / "Logs")
MIP_HELPER_ROOT: Path = _path_from_env("MIP_HELPER_ROOT", APP_DATA_ROOT / "MipHelper")
MIP_HELPER_PATH: Path = _path_from_env("MIP_HELPER_PATH", MIP_HELPER_ROOT / "MipHelper.exe")

# Conventional sub-folders.
OUTPUTS_SINGLE = OUTPUTS_ROOT / "Single"
OUTPUTS_BATCH = OUTPUTS_ROOT / "Batch"
OUTPUTS_IMAGES = OUTPUTS_ROOT / "Images"
TEMP_CLOUD = TEMP_ROOT / "Cloud"
TEMP_PROTECTED = TEMP_ROOT / "Protected"


_REQUIRED_DIRS = (
    APP_DATA_ROOT,
    OUTPUTS_ROOT,
    OUTPUTS_SINGLE,
    OUTPUTS_BATCH,
    OUTPUTS_IMAGES,
    TEMP_ROOT,
    TEMP_CLOUD,
    TEMP_PROTECTED,
    LOGS_ROOT,
    MIP_HELPER_ROOT,
)


def ensure_runtime_dirs() -> None:
    """Create all required runtime folders. Raise a friendly error on failure."""
    try:
        for folder in _REQUIRED_DIRS:
            folder.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(
            f"The app could not create {APP_DATA_ROOT}. "
            "Check local permissions or set APP_DATA_ROOT in .env. "
            f"Underlying error: {exc}"
        ) from exc


# Run on import so any module using these constants finds the dirs ready.
ensure_runtime_dirs()
