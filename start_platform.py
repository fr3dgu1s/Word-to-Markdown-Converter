import hashlib
import subprocess
import sys
import venv
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

HEALTH_URL = "http://127.0.0.1:8000/health"
REQUIRED_IMPORTS = (
    "import docling, docx, dotenv, fastapi, multipart, PIL, uvicorn, win32com"
)
REQUIREMENTS_MARKER = ".requirements.sha256"


def _can_reach_server() -> bool:
    try:
        with urlopen(HEALTH_URL, timeout=0.8) as response:
            return 200 <= response.status < 500
    except (URLError, Exception):
        return False


def _pythonw_executable(python_executable: Path) -> str:
    pythonw = python_executable.with_name("pythonw.exe")
    if pythonw.exists():
        return str(pythonw)
    return str(python_executable)


def _requirements_digest(requirements_file: Path) -> str:
    return hashlib.sha256(requirements_file.read_bytes()).hexdigest()


def _python_runs(python_executable: Path) -> bool:
    if not python_executable.exists():
        return False

    try:
        result = subprocess.run(
            [str(python_executable), "-c", "pass"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            creationflags=(
                subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0
            ),
        )
    except OSError:
        return False
    return result.returncode == 0


def _environment_is_healthy(python_executable: Path) -> bool:
    if not _python_runs(python_executable):
        return False

    result = subprocess.run(
        [str(python_executable), "-c", REQUIRED_IMPORTS],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0,
    )
    return result.returncode == 0


def _requirements_are_current(venv_root: Path, requirements_file: Path) -> bool:
    marker = venv_root / REQUIREMENTS_MARKER
    try:
        return marker.read_text(encoding="ascii").strip() == _requirements_digest(
            requirements_file
        )
    except OSError:
        return False


def _install_requirements(
    python_executable: Path, requirements_file: Path, repo_root: Path
) -> None:
    logs_root = repo_root / "Logs"
    logs_root.mkdir(parents=True, exist_ok=True)
    bootstrap_log = logs_root / "bootstrap.log"

    with bootstrap_log.open("a", encoding="utf-8") as log:
        log.write("\nInstalling or updating Python dependencies...\n")
        log.flush()
        subprocess.run(
            [
                str(python_executable),
                "-m",
                "pip",
                "install",
                "-r",
                str(requirements_file),
            ],
            cwd=str(repo_root),
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
            creationflags=(
                subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0
            ),
        )


def _ensure_runtime(repo_root: Path) -> Path:
    requirements_file = repo_root / "requirements.txt"
    venv_root = repo_root / ".venv"
    python_executable = venv_root / "Scripts" / "python.exe"

    if not _python_runs(python_executable):
        venv.EnvBuilder(with_pip=True, clear=venv_root.exists()).create(venv_root)

    if not _environment_is_healthy(
        python_executable
    ) or not _requirements_are_current(venv_root, requirements_file):
        _install_requirements(python_executable, requirements_file, repo_root)

        if not _environment_is_healthy(python_executable):
            raise RuntimeError(
                "Python dependencies could not be initialized. "
                f"See {repo_root / 'Logs' / 'bootstrap.log'}."
            )

        (venv_root / REQUIREMENTS_MARKER).write_text(
            _requirements_digest(requirements_file), encoding="ascii"
        )

    return python_executable


def _start_server_process(repo_root: Path, python_executable: Path) -> None:
    server_script = repo_root / "server.py"
    creation_flags = 0
    if sys.platform.startswith("win"):
        creation_flags = (
            subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NO_WINDOW
        )

    subprocess.Popen(
        [_pythonw_executable(python_executable), str(server_script)],
        cwd=str(repo_root),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=creation_flags,
    )


def main() -> None:
    # Only start the server if it is not already running.
    # The loading page (loading.html) polls /health and redirects when ready.
    if not _can_reach_server():
        repo_root = Path(__file__).resolve().parent
        python_executable = _ensure_runtime(repo_root)
        _start_server_process(repo_root, python_executable)


if __name__ == "__main__":
    main()
