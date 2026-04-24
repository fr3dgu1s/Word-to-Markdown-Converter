import subprocess
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

HEALTH_URL = "http://127.0.0.1:8000/health"


def _can_reach_server() -> bool:
    try:
        with urlopen(HEALTH_URL, timeout=0.8) as response:
            return 200 <= response.status < 500
    except (URLError, Exception):
        return False


def _pythonw_executable() -> str:
    current = Path(sys.executable)
    pythonw = current.with_name("pythonw.exe")
    if pythonw.exists():
        return str(pythonw)
    return sys.executable


def _start_server_process(repo_root: Path) -> None:
    server_script = repo_root / "server.py"
    creation_flags = 0
    if sys.platform.startswith("win"):
        creation_flags = (
            subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NO_WINDOW
        )

    subprocess.Popen(
        [_pythonw_executable(), str(server_script)],
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
        _start_server_process(Path(__file__).resolve().parent)


if __name__ == "__main__":
    main()
