"""
Central path configuration for the Word-to-Markdown app.

Runtime files are ALWAYS stored in the folder that contains ``paths.py``
(i.e. the project/app folder where ``server.py`` lives). Any
``APP_DATA_ROOT`` value in ``.env`` or the process environment is
intentionally ignored to guarantee that what the user sees in the UI and
what gets written to disk are the same folder. ``.env`` is still loaded for
other settings (update-check, MSAL, etc.).

Layout:
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


PROJECT_ROOT: Path = Path(__file__).resolve().parent

# Runtime root is pinned to the project folder. We deliberately do NOT honour
# ``APP_DATA_ROOT`` from the environment so output cannot drift away from the
# folder that hosts ``server.py``.
APP_DATA_ROOT: Path = PROJECT_ROOT

_stale_env_value = (os.getenv("APP_DATA_ROOT") or "").strip()
if _stale_env_value and Path(_stale_env_value).expanduser().resolve() != PROJECT_ROOT.resolve():
    os.environ["APP_DATA_ROOT"] = str(PROJECT_ROOT)
    print(
        f"[paths] Ignoring APP_DATA_ROOT={_stale_env_value!r}; "
        f"runtime is pinned to {PROJECT_ROOT}.",
        flush=True,
    )

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
            "Check that the project folder is writable. "
            f"Underlying error: {exc}"
        ) from exc


# Run on import so any module using these constants finds the dirs ready.
ensure_runtime_dirs()
