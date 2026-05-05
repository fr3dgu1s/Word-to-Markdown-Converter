"""
Central path configuration for the Word-to-Markdown app.

The default runtime location is the project/app folder containing this file.
Set ``APP_DATA_ROOT`` in ``.env`` or the environment to move all runtime files
elsewhere.

Layout (defaults):
    <project folder>/
        Outputs/           all converted Markdown (single + batch)
            Images/        images extracted by Docling
        Temp/              short-lived per-request scratch files
        Logs/              app.log + rotated history
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except ImportError:
    pass


def _path_from_env(name: str, default: Path) -> Path:
    raw = os.getenv(name)
    if raw and raw.strip():
        return Path(raw.strip()).expanduser()
    return default


PROJECT_ROOT: Path = Path(__file__).resolve().parent

APP_DATA_ROOT: Path = _path_from_env("APP_DATA_ROOT", PROJECT_ROOT)
OUTPUTS_ROOT: Path = APP_DATA_ROOT / "Outputs"
IMAGES_ROOT: Path = OUTPUTS_ROOT / "Images"
TEMP_ROOT: Path = APP_DATA_ROOT / "Temp"
LOGS_ROOT: Path = APP_DATA_ROOT / "Logs"


_REQUIRED_DIRS = (
    APP_DATA_ROOT,
    OUTPUTS_ROOT,
    IMAGES_ROOT,
    TEMP_ROOT,
    LOGS_ROOT,
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
